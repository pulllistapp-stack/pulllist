"""Article generator. Asks Claude to rewrite a source item into a
PullList-voiced English news post + extract the 1-3 factual claims
the fact-checker should verify.

Output contract:
    GenerateResult(title, body_markdown, excerpt, reading_time, claims)

Uses Anthropic's **structured outputs** (`messages.parse` with our
Pydantic model as the schema) so the API guarantees the response
matches the contract — no `json.loads()` from a free-form text block,
no malformed-JSON failures. Backfill testing showed ~33% of articles
were dropped to JSON parse errors on the previous prompt-only
approach; structured outputs eliminate that loss.
"""
from __future__ import annotations

import logging

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from .config import settings
from .sources import NewsItem

log = logging.getLogger("newsbot.generator")


class GenerateResult(BaseModel):
    """Schema Claude is forced to satisfy via output_format. Constraints
    (min_length/max_length/ge/le/max_length on lists) are validated
    client-side by the SDK — the API doesn't enforce them — so we keep
    them for our own sanity checks but never depend on the API to
    reject a too-long title."""

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

# Readability rules (these matter — readers scan, they don't read)

- **Short paragraphs.** 1-3 sentences each. Never longer.
- **Blank line between every paragraph.** No walls of text.
- **One idea per paragraph.** If you switch topics, start a new one.
- **Concrete over abstract.** "Surging Sparks Pikachu hit $180 last
  week" beats "the card has seen significant price movement."
- **Use sub-headings liberally.** A 400-word post should have 2-4 H2s.
- **Lists for parallel items.** Three facts? Bulleted list, not prose.

# Body format (Markdown)

[Lead paragraph — 1-2 sentences. The single most important fact.]

[Optional second short paragraph — context, 1-2 sentences.]

## What happened

- Fact one with source attribution
- Fact two
- Fact three

## Why it matters for collectors

[Short paragraph — 2-3 sentences max — tied to PullList's data:
pricing trends, set context, collectibility angle.]

[Optional second paragraph if there's a distinct second angle.]

## Sources

- [Source name](https://...)

Target length: **350-500 words**. Shorter is better than longer.
Always end with a Sources section linking the original article.

# Reference images

If the user prompt includes a "Reference images" list, embed each
relevant one with markdown — `![caption](url)` — at the point in the
body where it's most contextually useful (e.g. right after the
paragraph that describes the card / set / product it shows).

Rules:

- Use the provided URLs **verbatim**. Never modify, abbreviate, or
  invent a URL.
- If the image has a caption, use it. If empty, write a short
  descriptive one (under 60 chars) based on context.
- Weave images inline near their relevant paragraph — do NOT dump
  them all at the end in a gallery.
- It's fine to skip an image that wouldn't add value (e.g. a banner
  that's redundant with the hero).
- Don't repeat the hero image (it already renders above the article).

# Field guidance

- **title**: short specific headline (<= 90 chars).
- **body_markdown**: the full article body as described above.
- **excerpt**: 1-2 sentence summary for the listing card (<= 220 chars).
- **reading_time**: estimated minutes as integer (1-15).
- **claims**: 1-3 specific factual claims for the verifier.
"""


def _build_user_prompt(item: NewsItem) -> str:
    body = item.raw_text or item.summary or ""
    # Truncate aggressively — long articles blow up token cost without
    # adding much beyond the first ~6k tokens (~24k chars).
    body = body[:24000]
    parts = [
        f"Source: {item.source_name}",
        f"URL: {item.url}",
        f"Original title: {item.title}",
        f"Original publish date: {item.published_at or 'unknown'}",
        "",
        f"Body:\n{body}",
    ]
    if item.inline_images:
        lines = ["", "Reference images (use exact URLs if embedding):"]
        for i, img in enumerate(item.inline_images, 1):
            cap = img.get("caption") or "(no caption)"
            lines.append(f"{i}. {img['url']} — {cap}")
        parts.append("\n".join(lines))
    return "\n".join(parts) + "\n"


async def generate_article(item: NewsItem) -> GenerateResult:
    """Calls Claude via messages.parse() — the API enforces our
    GenerateResult schema, so the response either matches or the SDK
    raises. No json.loads, no regex-extract-JSON-from-prose. Adaptive
    thinking + the configured effort stay in extra_body alongside the
    SDK-supplied output_config.format."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.parse(
        model=settings.claude_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(item)}],
        thinking={"type": "adaptive"},
        output_format=GenerateResult,
        extra_body={"output_config": {"effort": settings.claude_effort}},
    )
    return resp.parsed_output
