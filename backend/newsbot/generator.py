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
writer for the PullList collector community. Your voice is \
warm, curious, and specific — like an editor talking to another \
collector, not a press release. English-only. No filler, no hype, \
no AI tells. Never say "in this article" or "let's dive in".

You will be given a source article. Your job:
1. Rewrite it as an original PullList post that a scrolling collector
   would actually stop for.
2. Extract 1-3 specific factual claims a checker should verify
   (prices, dates, set names, official quotes — not opinion).

# Voice

Think editorial notebook, not press wire. A great opening earns the
click; a great section header earns the scroll. Concrete numbers
over adjectives, one clear image per idea, dry humor when it fits
(never forced). Address the reader as another collector who already
knows the basics — no "as you may know" hand-holding, no
explainer preambles.

# Readability rules (these matter — readers scan, they don't read)

- **Short paragraphs.** 1-3 sentences each. Never longer.
- **Blank line between every paragraph.** No walls of text.
- **One idea per paragraph.** If you switch topics, start a new one.
- **Concrete over abstract.** "Surging Sparks Pikachu hit $180 last
  week" beats "the card has seen significant price movement."
- **Emoji section markers** — every H2 opens with a single relevant
  emoji + space (📅 release info, 💎 rare cards, 🔥 hot movers,
  🎨 illustrator/art, 📊 data/prices, 🛒 where to buy, 👑 top tier,
  💡 summary, 🎯 collector angle, ⚠️ caveat). One emoji per header,
  not decorative sprays inside paragraphs. Pick the emoji that
  actually maps to the section content — never generic.
- **Lists for parallel items.** Three facts? Bulleted list, not prose.

# Opening hook

The first sentence must earn attention. Pick ONE of these shapes,
based on what the source actually offers — not a template:

- **Surprising stat** — "PSA10 Umbreon just crossed $8,400 at
  auction. That's a 3× jump from six months ago."
- **Direct question** — "Which Sam's Club exclusive is the only
  place to grab N's Zekrom this year?"
- **Concrete scene** — "Sam's Club's back-end system just loaded
  a Pokémon collection nobody had seen before."
- **Sharp fact** — "The new 30th Celebration lineup lands over
  four release dates and twelve SKUs. Here's the breakdown."

Never open with "Today we…" / "Let's look at…" / "The Pokémon
Company has announced…" — those are wire-service defaults; you're
writing a post, not filing copy.

# Body format (Markdown)

[Opening hook — 1-2 sentences. Earns the click.]

[Optional second short paragraph — establishing context.]

## 📌 What happened

- Fact one with source attribution
- Fact two
- Fact three

## 🎯 Why it matters for collectors

[Short paragraph — 2-3 sentences max — tied to real data:
pricing trends, set context, collectibility angle.]

[Optional second paragraph if there's a distinct second angle.]

## 💡 The takeaway

Bulleted summary of the 2-4 things a busy collector should remember
from this post. Same format every time — the reader learns to
scroll here for the tl;dr. Keep bullets to ~10 words each.

Close with a one-liner CTA pointing readers back into PullList
(no link needed, just the phrase — the frontend renders it as a
soft catalog nudge): _"Track the full set on PullList."_ Vary the
exact wording per post so it doesn't read like a canned footer:
_"See live prices on PullList."_ / _"Compare rarities on PullList."_
/ _"All grades tracked on PullList."_

## Sources

- [Source name](https://...)

**Length scales with content depth — don't undersell big news:**

- Standard editorial post: **350-500 words**
- Set reveal / full product lineup / multi-SKU announcement:
  **800-1500 words** with one H2 per product or per release date.
  These articles MUST cover every SKU mentioned in the source, with
  its date, contents, and any unique promo. A 30+ product lineup
  rendered as a 6-bullet summary is a failure mode — readers came
  to find out about THIS product, and the post must mention it.
- Drop post: 150-250 words (see drop branch below).

Always end with a Sources section linking the original article.

**Source attribution is non-negotiable.** Even drop posts must end
with a `## Sources` section. When the source article itself cites
something further (manufacturer announcement, official tweet,
press release), include that secondary link too — readers should
always be able to trace any claim back to its origin. Bullets
under `## Sources` are formatted as `- [Publisher / what it is](URL)`.

# Source type — editorial vs product/drop

The user prompt starts with `Source type: …`. Adjust shape to match:

- **editorial article** (default — PokeBeach posts, set reveals,
  meta analyses, official announcements treated as news): full
  350-500 word post per the body format above.
- **product / drop page** (retailer announcement, store listing,
  preorder page from BestBuy, Pokemon Center, Target, Walmart,
  TCGPlayer, Amazon, etc.): much tighter — **150-250 words**, fact-
  density over editorialising. Lead with the retailer + product +
  price + drop date. Structure:

    [Hook — 1 sentence: retailer + product + price + drop date/status.
    Same hook rules as editorial — no wire-service open.]

    ## 🛒 Details

    - **Price:** $X
    - **SKU / item #:** 12345 (if visible on the source)
    - **Limit:** N per order (if mentioned)
    - **Status:** live / pre-order / waitlist / sold out
    - **Link:** [Retailer name](URL)

    [Optional 1-sentence collector context if there's a real angle —
    e.g. "These tins reprint the Mega Box promos from January at
    half the cost." Skip if nothing to add.]

    ## 💡 The takeaway

    - 2-3 bullets, ~10 words each. Same "busy collector remembers
      these" pattern as editorial. Close with a one-liner catalog
      nudge like _"Track pricing on PullList."_

    ## Sources
    - [Source name](URL)

  Reference images: drop pages SHOULD embed any provided product/
  gallery images — retailer pages often expose a SKU shot, packaging
  back, and bundled-cards reveal that all give the reader the same
  signal they'd see browsing the listing themselves. Same `![](url)`
  rules apply; just keep image count proportional to the tight body
  length (1-2 inline images typical for a drop post).

# Reference images

If the user prompt includes a "Reference images" list, you MUST
embed every single one of them in the body as `![caption](url)` —
the user spent crawl budget extracting these and a body with no
images reads as broken/lazy. Skip only TRUE duplicates (identical
URL) or images that visibly contradict the article's subject.

A set-reveal article with 20+ provided card / product images
should render with 20+ inline embeds — one per H2 section, beside
the product or card it depicts. Do not "summarise" the image list
into a single hero — every image is its own data point for the
reader. Dropping images is the same kind of information loss as
dropping product SKUs from the body text.

Placement rules:

- Use the provided URLs **verbatim**. Never modify, abbreviate, or
  invent a URL.
- If the image has a caption, use it. If empty, write a short
  descriptive one (under 60 chars) based on context.
- Weave images inline near their relevant paragraph — do NOT dump
  them all at the end in a gallery.
- Don't repeat the hero image (it already renders above the article).
- Treat the embedded image count as a body-quality signal — a 4-image
  reference list should produce ~4 inline images, not 1.

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


# Hosts that indicate a retailer / store / product page — the
# "product/drop" prompt branch fires when item.url matches one.
# Substring match against the lowercased URL, so subdomains + slugs
# still hit (e.g. "bestbuy" matches "www.bestbuy.com/site/...").
_DROP_HOSTS = (
    "bestbuy.com",
    "pokemoncenter.com",
    "target.com",
    "walmart.com",
    "tcgplayer.com",
    "amazon.com",
    "gamestop.com",
)


def _is_drop_source(url: str) -> bool:
    u = url.lower()
    return any(h in u for h in _DROP_HOSTS)


def _is_market_report(item: NewsItem) -> bool:
    """market_report source packages structured JSON payload into
    raw_text and uses a synthetic pulllist:// URL. Detect by the
    URL scheme so we don't misfire on any real article that
    happens to include the word 'market' in its source_name."""
    return item.url.startswith("pulllist://market-report/")


def _is_set_overview(item: NewsItem) -> bool:
    """set_overview source uses pulllist://set-overview/<set_id>."""
    return item.url.startswith("pulllist://set-overview/")


def _build_set_overview_prompt(item: NewsItem) -> str:
    """Payload -> Collectory-style set overview prompt. Every card
    row carries id + image so the generator can render an inline
    ![](image) followed by [Name](/cards/{id}) link."""
    try:
        payload = json.loads(item.raw_text)
    except Exception:
        payload = {}
    s = payload.get("set", {})
    top_cards = payload.get("top_cards", []) or []
    lines = [
        "Source type: new-set overview (data-driven, our own catalog)",
        "",
        "SET METADATA:",
        f"- id: {s.get('id')}",
        f"- name: {s.get('name')}",
        f"- series: {s.get('series')}",
        f"- release_date: {s.get('release_date')}",
        f"- card_count: {s.get('card_count')}",
        f"- printed_total: {s.get('printed_total')}",
        f"- total: {s.get('total')}",
        f"- logo_url: {s.get('logo_url')}",
        f"- total_value_usd: {s.get('total_value_usd')}",
        "",
        "You MUST link the set name in the body to /sets/{id} once "
        "using [Set Name](/sets/{id}). Every card mention MUST link "
        "to /cards/{card_id}. No external URLs for cards or sets — "
        "the whole point of this post is to funnel readers into our "
        "own catalog. Never invent slugs; use the ids given below.",
        "",
        f"TOP {len(top_cards)} CARDS BY MARKET PRICE:",
    ]
    for c in top_cards:
        price = c.get("market_price_usd")
        price_str = f"${price:.2f}" if isinstance(price, (int, float)) else "n/a"
        lines.append(
            f"- card_id={c.get('id')} name={c.get('name')} "
            f"#{c.get('number')} rarity={c.get('rarity')} "
            f"artist={c.get('artist') or 'unknown'} "
            f"market={price_str} image={c.get('image_small', '') or c.get('image_large', '')}"
        )
    lines.append("")
    lines.append(
        "Frame the post based on release_date relative to today: if the "
        "date is in the past, this is a REVIEW ('what actually shipped, "
        "what's holding value'); if the date is in the future, this is "
        "a PREVIEW ('what to watch when it drops, based on card list "
        "we've already indexed'). Title reflects that framing — e.g. "
        "'Set Name: <angle>' for reviews, 'Set Name Preview — <angle>' "
        "for previews. Angle = the notable thing (chase card / price "
        "band / art / promo), never generic 'Overview of X'."
    )
    lines.append("")
    lines.append(
        "Structure the post as: hook (name-drops the marquee card + a "
        "concrete price number) -> ## 📅 Release info (release date, "
        "series, card count, notable format context) -> ## 💎 Top cards "
        "(each card = inline image THEN a linked name + rarity + price, "
        "1-2 sentence 'why it matters' per card for the top 3-5, then "
        "quicker one-liners for the rest — don't just dump the list) "
        "-> ## 🎯 Set snapshot (2-3 sentence takeaway on what defines "
        "this set — chase concentration, price band, art style) -> "
        "## 💡 The takeaway (2-4 bullets) -> one-line PullList catalog "
        "CTA -> ## Sources (just '- PullList catalog snapshot')."
    )
    return "\n".join(lines) + "\n"


def _build_market_report_prompt(item: NewsItem) -> str:
    """Turn the JSON payload the market_report source packed into
    raw_text into a prompt Claude can reason about. Everything the
    generator needs is in the payload: week id, period, sources,
    per-card gainer/loser rows with card_id + name + set + prices."""
    try:
        payload = json.loads(item.raw_text)
    except Exception:
        payload = {}
    gainers = payload.get("gainers", []) or []
    losers = payload.get("losers", []) or []
    lines = [
        "Source type: weekly market report (data-driven, our own dataset)",
        f"Week: {payload.get('week_id', '')}",
        f"Window: last {payload.get('period_days', 7)} days",
        f"Price source: {payload.get('source', 'ebay')}",
        "",
        "Every card row below carries card_id — you MUST link the card "
        "name to /cards/{card_id} in markdown ([Name](/cards/id)) every "
        "time you mention it. That's how readers click through to our "
        "own catalog page for the card. Do NOT invent slugs or use "
        "external URLs for card names.",
        "",
        "TOP GAINERS (last 7 days):",
    ]
    for m in gainers:
        lines.append(
            f"- card_id={m.get('card_id')} name={m.get('name')} "
            f"set={m.get('set_name')} #{m.get('number')} "
            f"rarity={m.get('rarity')} "
            f"latest=${m.get('latest_price'):.2f} "
            f"oldest=${m.get('oldest_price'):.2f} "
            f"delta={m.get('delta_pct'):+.1f}% "
            f"image={m.get('image_small', '')}"
        )
    lines.append("")
    lines.append("TOP LOSERS (last 7 days):")
    for m in losers:
        lines.append(
            f"- card_id={m.get('card_id')} name={m.get('name')} "
            f"set={m.get('set_name')} #{m.get('number')} "
            f"rarity={m.get('rarity')} "
            f"latest=${m.get('latest_price'):.2f} "
            f"oldest=${m.get('oldest_price'):.2f} "
            f"delta={m.get('delta_pct'):+.1f}% "
            f"image={m.get('image_small', '')}"
        )
    lines.append("")
    lines.append(
        "Structure the post as: hook -> ## 🔥 Top Gainers (with each "
        "card as an inline image + linked name + delta) -> ## ❄️ Top "
        "Losers (same shape) -> ## 🎯 What's driving it (one or two "
        "sentences on any pattern you see — set overlap, rarity "
        "concentration, etc.) -> ## 💡 The takeaway (2-3 bullets) -> "
        "one-line PullList catalog CTA -> ## Sources (just: '- PullList "
        "eBay snapshot pipeline'). Title should be something like "
        "'This Week: <most notable mover>' — concrete, not generic."
    )
    return "\n".join(lines) + "\n"


def _build_user_prompt(item: NewsItem) -> str:
    if _is_market_report(item):
        return _build_market_report_prompt(item)
    if _is_set_overview(item):
        return _build_set_overview_prompt(item)
    body = item.raw_text or item.summary or ""
    # 50k chars (~12k tokens) is enough to fit the longest editorial
    # articles we've seen end-to-end (30th Celebration set lineup
    # type with 10+ products described). Earlier 24k truncation was
    # dropping the second half of long lineup posts, which made the
    # generated draft skip half the SKUs. Sonnet 4.6's 200k window
    # has plenty of room; the cost delta on a worst-case article is
    # under \$0.02.
    body = body[:50000]
    source_type = (
        "product/drop page (retailer announcement)"
        if _is_drop_source(item.url)
        else "editorial article"
    )
    parts = [
        f"Source type: {source_type}",
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
        # 4096 was clipping long editorials (LEGO Pokémon feature +
        # Pitch Black deck strategy both truncated mid-JSON on the
        # 2026-07-14 run — no closing brace, generator raised 'no
        # JSON object found'). 16k is roughly 12k output words —
        # comfortably above the 800-1500 word set-lineup ceiling
        # from the prompt, with headroom for the JSON envelope and
        # the takeaway block. max_tokens is only a cap: short posts
        # still bill for their actual output length, so bumping this
        # doesn't raise cost on normal drop / news posts.
        max_tokens=16000,
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
