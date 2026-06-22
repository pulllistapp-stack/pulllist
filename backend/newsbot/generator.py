"""Article generator. Asks Claude Opus to rewrite a source item into
a PullList-voiced English news post + extract the 1-3 factual claims
the fact-checker should verify.

Output contract:
    GenerateResult(title, body_markdown, excerpt, reading_time, claims)

The model is instructed to emit a single JSON object. We parse it with
a strict schema — malformed responses raise so they get surfaced in
CI logs instead of silently producing a bad draft.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field, ValidationError

from .config import settings
from .sources import NewsItem

log = logging.getLogger("newsbot.generator")


class GenerateResult(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    body_markdown: str = Field(min_length=200)
    excerpt: str = Field(min_length=1, max_length=512)
    reading_time: int = Field(ge=1, le=30)
    claims: list[str] = Field(default_factory=list, max_length=3)


SYSTEM_PROMPT = """You are the PullList Newsbot — a daily Pokémon TCG \
news writer for the PullList collector community. Your voice is \
terse, informative, English-only, and respectful of collectors' time. \
No filler, no hype, no AI tells.

You will be given a source article. Your job:
1. Rewrite it as an original PullList news post.
2. Extract 1-3 specific factual claims a checker should verify
   (prices, dates, set names, official quotes — not opinion).

Body format (Markdown):

[Lead paragraph — 2-3 sentences. The actual news.]

## What happened

- Fact one with source attribution
- Fact two
- Fact three

## Why it matters for collectors

[1-2 paragraph analysis tied to PullList's data: pricing trends, set
context, collectibility angle.]

## Sources

- [Source name](https://...)

Target length: 400-700 words. Always end with a Sources section that
links the original article you were given.

Output a single JSON object — no prose around it, no markdown fence:

{
  "title": "short specific headline (<= 90 chars)",
  "body_markdown": "the full article body as described above",
  "excerpt": "1-2 sentence summary for the listing card (<= 220 chars)",
  "reading_time": estimated minutes as integer 1-15,
  "claims": ["specific factual claim 1", "specific factual claim 2"]
}
"""


def _build_user_prompt(item: NewsItem) -> str:
    body = item.raw_text or item.summary or ""
    # Truncate aggressively — long articles blow up token cost without
    # adding much beyond the first ~6k tokens (~24k chars).
    body = body[:24000]
    return (
        f"Source: {item.source_name}\n"
        f"URL: {item.url}\n"
        f"Original title: {item.title}\n"
        f"Original publish date: {item.published_at or 'unknown'}\n\n"
        f"Body:\n{body}\n"
    )


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    """Claude sometimes wraps the JSON in stray prose or a fence even
    when told not to. Find the outermost {...} and parse that."""
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        raise ValueError(f"no JSON object found in model output: {text[:200]!r}")
    return json.loads(match.group(0))


async def generate_article(item: NewsItem) -> GenerateResult:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Opus 4.8 / Fable 5 require adaptive thinking — the legacy
    # `{type: "enabled", budget_tokens: N}` API was removed and returns
    # 400. Depth is controlled via output_config.effort instead. We
    # leave display="omitted" (the default) so thinking blocks come
    # back as empty placeholders; the article is in the trailing text
    # block.
    resp = await client.messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(item)}],
        thinking={"type": "adaptive"},
        extra_body={"output_config": {"effort": settings.claude_effort}},
    )

    # Pull the text content out of the response. Thinking blocks come
    # first when enabled; the article is in the trailing text block(s).
    text_parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    if not text_parts:
        raise RuntimeError("Claude returned no text content")
    raw = "".join(text_parts)

    payload = _extract_json(raw)
    try:
        return GenerateResult.model_validate(payload)
    except ValidationError as exc:
        log.error("generator output failed validation: %s", exc)
        raise
