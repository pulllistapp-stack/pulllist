"""Article generator. Asks Claude to rewrite a source item into a
PullList-voiced English news post + extract the 1-3 factual claims
the fact-checker should verify.

Output contract:
    GenerateResult(title, body_markdown, excerpt, reading_time, claims)

Defence in depth against the model misbehaving:

1. **Server-side schema enforcement** via `output_config.format` with
   a JSON-schema derived from `GenerateResult`. Tells the API "the
   response MUST match this shape" — closes off the bulk of
   "missing-comma" and "stray-prose" failures that plagued the
   prompt-only contract (33% drop rate in backfill testing).

2. **Markdown-fence stripping** as a second layer. Even with
   output_config.format, the model occasionally still wraps the
   payload in ```json…``` blocks. We pull the outermost {…} object
   out of whatever it returns before parsing.

3. **Pydantic validation** at the end catches anything that survived
   1 + 2 with the wrong field types / out-of-range values.
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
    """Schema Claude is forced to satisfy. Constraint fields
    (min_length/max_length/ge/le) drive client-side validation only —
    Claude's output_config.format only honours base types + required."""

    title: str = Field(min_length=1, max_length=256)
    body_markdown: str = Field(min_length=200)
    excerpt: str = Field(min_length=1, max_length=512)
    reading_time: int = Field(ge=1, le=30)
    claims: list[str] = Field(default_factory=list, max_length=3)


# JSON-schema sent to the API with output_config.format. Hand-rolled
# instead of `GenerateResult.model_json_schema()` so we can guarantee
# `additionalProperties: false` (required by Claude) and avoid the
# unsupported constraint keys (minLength / maxLength / etc.) that
# the API would otherwise reject.
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body_markdown": {"type": "string"},
        "excerpt": {"type": "string"},
        "reading_time": {"type": "integer"},
        "claims": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "body_markdown", "excerpt", "reading_time", "claims"],
    "additionalProperties": False,
}


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

## Paired / split images

Some images only make sense displayed adjacent — Pokémon TCG
**split-card** sets (a single illustration spread across two cards
that must be placed side-by-side), or before/after comparisons. Tell
signals from the provided captions:

- Captions ending in "Part 1" / "Part 2" or "(1)" / "(2)"
- Two consecutive captions sharing the same prefix and differing
  only by a part marker — e.g. "Legendary Summit – Part 1" and
  "Legendary Summit – Part 2"
- Captions like "Top" / "Bottom", "Left" / "Right" on cards from
  the same set
- A single combined caption mentioning both parts (e.g. "Part 1, 2")

When you're CONFIDENT two images are a paired set, wrap them in a
flex container so they render touching, instead of as two separate
paragraphs:

<div style="display:flex;gap:0;justify-content:center;max-width:560px;margin:1.5rem auto">
<img src="URL_FOR_PART_1" style="width:50%;height:auto;display:block" alt="Caption Part 1" />
<img src="URL_FOR_PART_2" style="width:50%;height:auto;display:block" alt="Caption Part 2" />
</div>

Rules for paired wrapping:

- Use the **provided URLs verbatim** inside the src="..." attributes
  — do NOT modify, abbreviate, or invent URLs. The bot wraps them
  through an image proxy in post-processing.
- Use `gap:0` for true split cards (art must touch). For related-
  but-not-split pairs (e.g. before/after comparisons), use
  `gap:0.5rem` instead.
- Don't ALSO embed the same images as separate `![](url)` — pick
  one form. Pairs go in the div, singles stay as markdown.
- If only ONE part is in the provided images, don't wrap — render
  it as a normal `![caption](url)`.

When in doubt, default to separate markdown images. Over-wrapping
unrelated images breaks the layout worse than not pairing related ones.

# Output

Your response MUST be a single JSON object matching this shape — no
prose around it, no markdown code fence, no preamble:

{
  "title": "short specific headline (<= 90 chars)",
  "body_markdown": "the full article body as described above",
  "excerpt": "1-2 sentence summary for the listing card (<= 220 chars)",
  "reading_time": estimated minutes as integer (1-15),
  "claims": ["specific factual claim 1", "specific factual claim 2"]
}
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


# Greedy match from first `{` to last `}` — handles whatever the model
# wrapped the JSON in (```json fences, "Here you go:" preamble, etc).
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        raise ValueError(
            f"no JSON object found in model output: {text[:200]!r}"
        )
    return json.loads(match.group(0))


async def generate_article(item: NewsItem) -> GenerateResult:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(item)}],
        thinking={"type": "adaptive"},
        # output_config.format = server-side schema enforcement.
        # output_config.effort = adaptive-thinking depth (low/medium/
        # high/xhigh/max). Both live under one output_config dict.
        # extra_body forwards them since older SDK versions may not
        # type these as top-level kwargs.
        extra_body={
            "output_config": {
                "format": {"type": "json_schema", "schema": _RESPONSE_SCHEMA},
                "effort": settings.claude_effort,
            }
        },
    )

    text_parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    if not text_parts:
        raise RuntimeError("Claude returned no text content")
    raw = "".join(text_parts)

    # Belt + suspenders: server-side format SHOULD give clean JSON,
    # but the model occasionally still wraps in ```json fences. The
    # greedy {…} extractor handles both shapes.
    payload = _extract_json(raw)
    try:
        return GenerateResult.model_validate(payload)
    except ValidationError as exc:
        log.error("generator output failed pydantic validation: %s", exc)
        raise
