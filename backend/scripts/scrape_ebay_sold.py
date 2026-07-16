"""Scrape eBay sold-listings for chase cards via Playwright + stealth.

Why this exists: our regular `snapshot_ebay.py` uses eBay's Browse
API, which returns ACTIVE (asking) listings. Sellers routinely list
graded slabs 10-30% above the clearing price ("testing the market"),
so the median of active asks overshoots true market. For chase
cards this matters — SV Prismatic Umbreon SIR PSA 10 asks at ~$7,950
median but ACTUALLY SELLS around $6,950-7,050 (12% gap).

eBay's Marketplace Insights API (which returns sold data cleanly)
was declined 2026-06-29. Direct HTTP scraping is blocked by
the site's automated-request protection at the TLS layer. Playwright + `playwright-stealth` +
warm-up navigation defeats the bot check by driving a real headless
Chromium — same TLS handshake pattern as a normal browser session.

Scope: one grade tier per invocation (matching the DOW rotation of
`snapshot_ebay`). Card selection = same chase-only filter (price
gate + rarity). Writes to `card_price_snapshots` with source
`ebay_sold` — kept distinct from `source='ebay'` (asking) so the
Graded Prices endpoint can prefer sold when both exist.

Usage:
    python -m scripts.scrape_ebay_sold --graded-tier "PSA 10" --limit 5
    python -m scripts.scrape_ebay_sold --graded-tier "CGC 10" --min-price 50
    python -m scripts.scrape_ebay_sold --dry-run --card-id sv8pt5-161
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from statistics import median as _median
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.async_api import Browser, async_playwright
from playwright_stealth import Stealth
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, init_db
from app.models import Card, CardPriceSnapshot, Set
from app.services.grade_classifier import classify_grade


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("scrape_ebay_sold")


SOURCE = "ebay_sold"
# Fallback source: same Playwright pipeline but WITHOUT the LH_Sold
# filter — pulls active-listing medians for tiers that don't clear
# MIN_LISTINGS on sold alone (thin CGC vintage etc.). Kept as a
# distinct source key so the frontend can label it "Asking" and the
# graded-prices endpoint can prefer real sold data when both exist.
SOURCE_ASKING = "ebay_asking"
VARIANT = "active"  # sold snapshots share the variant-key space with asking rows
# Bumped from 2 → 5 after the first prod run. n=3-4 buckets produced
# unstable medians (Charizard δ n=3 → $3,737 with $19,500 hi). n≥5
# tightens signal-to-noise at the cost of dropping a few thin cards
# per run — those tend to have wide asks anyway.
MIN_LISTINGS_PER_GRADE = 5

# Per-tier overrides for markets where pop is inherently thin —
# insisting on n>=5 would drop nearly all data. Black Label slabs
# in particular usually have 1-3 physical copies existing on eBay
# at any moment; any signal is better than a blank tile there.
# TAG and vintage BGS also trade thinly enough to warrant a lower
# floor.
TIER_MIN_OVERRIDES: dict[str, int] = {
    "bgs10bl": 1,   # BGS 10 Black Label — famously thin pop
    "bgs10":   2,
    "bgs9.5":  2,
    "bgs9":    2,
    "tag10":   2,
    "tag9.5":  2,
    "tag9":    2,
}


def _min_for(grade: str) -> int:
    return TIER_MIN_OVERRIDES.get(grade, MIN_LISTINGS_PER_GRADE)

# Trim the top/bottom TRIM_PCT of listings before taking the median,
# but only when the sample is large enough for a trim to make sense.
# Filters out obvious scam listings ($174k Pikachu, $85k Mewtwo) and
# ads/pop-report/raw-slipthrough on the low end ($19.99 Umbreon VMAX)
# without hurting cards that already cluster tightly.
TRIM_PCT = 0.10
TRIM_MIN_N = 10

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

# ── eBay sold-page parser ─────────────────────────────────────────

_TITLE_RE = re.compile(
    r'class="[^"]*\bs-card__title\b[^"]*"[^>]*>\s*<span[^>]*>([^<]+)</span>',
    re.IGNORECASE,
)
_PRICE_RE = re.compile(
    r'class="[^"]*\bs-card__price\b[^"]*"[^>]*>\$([0-9,]+\.[0-9]{2})',
)


def _parse_sold(html: str) -> list[tuple[str, float]]:
    """Return [(title, price_usd)] for every sold-item card block in
    the HTML. Skips eBay's "Shop on eBay" ad slots."""
    out: list[tuple[str, float]] = []
    # Split on <li class="s-card ..."> boundaries.
    blocks = re.split(
        r'<li[^>]*class="[^"]*\bs-card\b[^"]*"[^>]*>',
        html,
    )
    for block in blocks[1:]:
        t = _TITLE_RE.search(block)
        p = _PRICE_RE.search(block)
        if not t or not p:
            continue
        title = re.sub(r"\s+", " ", t.group(1).strip())
        if title.lower() in ("shop on ebay", ""):
            continue
        try:
            price = float(p.group(1).replace(",", ""))
        except ValueError:
            continue
        if price <= 0:
            continue
        out.append((title, price))
    return out


def _card_number_match(title: str, card_number: str | None) -> bool:
    """Strict card-number match — the card's number MUST appear in
    the title (word-bounded, zero-pad tolerant). Reject listings that
    reference a DIFFERENT explicit number, AND reject listings that
    have no matching number at all when the card has one.

    Tightened after the first prod run: the previous fallback ("no
    digit-slash-digit anywhere → keep") let generic bulk lots slip
    through — "Pokemon PSA 10 Gem Mint Lot" would pass even when
    scraping Shining Charizard 107. We give up a few promo-style
    hits without printed numbers, but for numbered cards this is
    the right trade — that's the vast majority of chase inventory.
    """
    if not card_number:
        return True
    num = card_number.split("/")[0].lstrip("0") or card_number.split("/")[0]
    if not num:
        return True
    # Explicit number in title (word-bounded). Zero-pad tolerant so
    # "161" matches "0161", "00161".
    return bool(re.search(rf"\b0*{re.escape(num)}\b", title))


# Words that carry so little info they don't help identify a card.
_NAME_STOPWORDS = frozenset(
    {
        "the", "of", "and", "a", "an", "de", "la", "le", "el",
        "ex", "gx", "vmax", "vstar", "v",  # too generic — thousands of listings have "ex" without being THIS ex
    }
)


def _first_content_word(card_name: str) -> str | None:
    """Pull the first substantive word from a card name — the primary
    identifier we can require in the listing title. E.g.:
        "Umbreon ex"        → "umbreon"
        "Mewtwo ★"          → "mewtwo"
        "Latias & Latios-GX"→ "latias"
    """
    for word in re.split(r"[\s\-&/]+", (card_name or "").lower()):
        clean = re.sub(r"[^a-z0-9]", "", word)
        if clean and clean not in _NAME_STOPWORDS and len(clean) >= 3:
            return clean
    return None


def _card_name_match(title: str, card_name: str) -> bool:
    """Title must contain the card's primary identifier word. Rejects
    generic "Pokemon PSA 10 Bulk Lot" listings the query returns as
    filler. Case-insensitive substring, not word-bounded — Pokémon
    listings often mangle spacing ("UmbreonEX")."""
    key = _first_content_word(card_name)
    if not key:
        return True  # No usable identifier → don't filter (rare)
    return key in title.lower()


def _trim_median(prices: list[float]) -> tuple[float, float, float, int]:
    """Sort, optionally trim the tails, then return
    (low_kept, median, high_kept, n_kept)."""
    prices = sorted(prices)
    n = len(prices)
    if n >= TRIM_MIN_N:
        drop = max(1, int(round(n * TRIM_PCT)))
        kept = prices[drop : n - drop]
        if len(kept) < 3:
            kept = prices  # too aggressive for the sample, unwind
    else:
        kept = prices
    return kept[0], float(_median(kept)), kept[-1], len(kept)


# ── Playwright driver ─────────────────────────────────────────────


async def _launch_browser(headless: bool = False) -> tuple[Browser, "async_playwright"]:
    """Chromium launch. `headless=False` is the default because
    the site's automated-request protection consistently throttle responses pure-headless Chromium — it
    returns fewer results in pure-headless mode. Visible mode works reliably on
    a real display, and works headless-ish on GH Actions when the
    workflow wraps the command in `xvfb-run` (virtual X server).
    """
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )
    return browser, p


async def _fetch_sold_html(
    browser: Browser,
    query: str,
    max_attempts: int = 2,
    ipg: int = 60,
    sold_only: bool = True,
) -> str | None:
    """One search. Returns the sold-listings HTML or None on failure.

    Retries up to `max_attempts` because the site's automated-request protection's challenge is
    stateful: the first request in a fresh context sometimes resolves
    cleanly, sometimes lands on a throttle response page with no listings.
    A fresh context on retry usually clears it.

    Warms up via ebay.com/ so the site's automated-request protection sets its challenge cookie
    inside the context first; direct navigation to /sch/ returns 403
    without the cookie.
    """
    last_html: str | None = None
    for attempt in range(1, max_attempts + 1):
        stealth = Stealth()
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            user_agent=USER_AGENT,
        )
        await stealth.apply_stealth_async(context)
        page = await context.new_page()
        try:
            await page.goto(
                "https://www.ebay.com/",
                wait_until="domcontentloaded",
                timeout=45_000,
            )
            # Longer warm-up on retries — the site's automated-request protection's challenge takes
            # 2-4s to execute; being generous keeps our success rate up.
            await page.wait_for_timeout(3500 + (attempt - 1) * 2000)
            # When sold_only=True (default), scope to actual sales.
            # When False, drop LH_Sold/LH_Complete to include active
            # asking listings — the fallback pool for tiers with too
            # few sales to meet MIN_LISTINGS (vintage CGC especially).
            # `_sacat=0` (all categories) makes eBay less likely to
            # serve a "did you mean" template — it says explicitly
            # "search across everything" which matches the URL shape
            # the site's automated-request protection expects from a real user browsing from the
            # search bar.
            base = (
                f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}"
                "&_sacat=0"
            )
            url = (
                f"{base}&LH_Sold=1&LH_Complete=1&_ipg={ipg}"
                if sold_only
                else f"{base}&_ipg={ipg}"
            )
            resp = await page.goto(
                url, wait_until="domcontentloaded", timeout=45_000
            )
            if resp is None or resp.status >= 400:
                log.warning(
                    f"attempt {attempt}: sold nav HTTP "
                    f"{resp.status if resp else '?'}"
                )
                continue
            try:
                await page.wait_for_selector(
                    'li[class*="s-card"]', timeout=12_000
                )
            except Exception:
                # No selector match — could be genuinely-empty results
                # OR a throttle response page. Try once more with a fresh
                # context before giving up.
                pass
            html = await page.content()
            last_html = html
            # Quick real-listings check: > 30 s-card hits usually means
            # a populated results page. Lower counts might still parse
            # cleanly but often mean the page redirected to a "no
            # results" template.
            if html.count("s-card") > 30:
                return html
            log.info(
                f"attempt {attempt}: only {html.count('s-card')} s-card "
                "hits, retrying"
            )
        except Exception as e:
            log.warning(f"attempt {attempt} fetch error: {e}")
        finally:
            await context.close()
    return last_html


# ── Snapshot writer ───────────────────────────────────────────────


def _conflict_insert(dialect: str):
    if dialect == "postgresql":
        return pg_insert(CardPriceSnapshot)
    return sqlite_insert(CardPriceSnapshot)


async def _flush(db: AsyncSession, rows: list[dict]) -> int:
    """Upsert snapshot rows. On (card_id, source, variant, grade,
    snapshot_date) conflict we OVERWRITE with the newer values so a
    user-triggered Refresh actually updates the tile — previously
    DO NOTHING silently dropped the second write on the same day,
    which was invisibly confusing (button "worked", tile didn't
    change). Same-day double-writes are rare outside Refresh, and
    when they do happen we prefer the fresher scrape."""
    if not rows:
        return 0
    dialect = db.bind.dialect.name
    stmt = _conflict_insert(dialect).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["card_id", "source", "variant", "grade", "snapshot_date"],
        set_={
            "market_price_usd": stmt.excluded.market_price_usd,
            "low_price_usd": stmt.excluded.low_price_usd,
            "mid_price_usd": stmt.excluded.mid_price_usd,
            "high_price_usd": stmt.excluded.high_price_usd,
            "sales_count": stmt.excluded.sales_count,
            "snapshot_at": stmt.excluded.snapshot_at,
        },
    )
    r = await db.execute(stmt)
    await db.commit()
    return r.rowcount or 0


# ── Card selection ────────────────────────────────────────────────


async def _pick_cards(
    limit: int | None,
    min_price: float,
    card_ids: list[str] | None,
    skip_if_recent_days: int,
    graded_tier: str,
    snapshot_date: str,
) -> list[tuple[Card, Set | None]]:
    """Return chase cards worth scraping.

    Default gate: EN cards priced above the floor, ranked by market
    DESC. `--card-id` overrides that with an explicit list (one-off
    testing).

    When `skip_if_recent_days > 0` we drop any card that already has
    a (source='ebay_sold', grade=WANTED, snapshot_date >= today-N)
    row. Zero means "no skip". `1` means skip cards refreshed TODAY
    (same-day gap fill). Larger values enable rolling coverage: at
    N=14 the weekly sweep never revisits a card it already got in
    the last two weeks, so week-over-week we drill deeper into the
    candidate pool instead of re-scraping the same top-300 chase.
    """
    async with SessionLocal() as db:
        from sqlalchemy.orm import selectinload
        from sqlalchemy import not_, exists
        from datetime import date, timedelta

        stmt = select(Card).options(selectinload(Card.set)).where(
            Card.language == "en"
        )
        if card_ids:
            stmt = stmt.where(Card.id.in_(card_ids))
        else:
            stmt = stmt.where(Card.market_price_usd >= min_price).order_by(
                Card.market_price_usd.desc()
            )

        if skip_if_recent_days > 0:
            wanted_grade = classify_grade(f"dummy {graded_tier}")
            cutoff = (
                date.fromisoformat(snapshot_date)
                - timedelta(days=skip_if_recent_days - 1)
            ).isoformat()
            already = select(CardPriceSnapshot.card_id).where(
                CardPriceSnapshot.card_id == Card.id,
                CardPriceSnapshot.source == SOURCE,
                CardPriceSnapshot.grade == wanted_grade,
                CardPriceSnapshot.snapshot_date >= cutoff,
            )
            stmt = stmt.where(not_(exists(already)))

        if limit:
            stmt = stmt.limit(limit)
        rows = list((await db.execute(stmt)).scalars())
    return [(c, c.set) for c in rows]


async def _scrape_pass(
    *,
    browser: Browser,
    query: str,
    card: Card,
    wanted_grade: str,
    source_tag: str,
    sold_only: bool,
    snapshot_date: str,
    dry_run: bool,
    ipg: int,
    max_attempts: int,
    stats: dict,
    idx: int,
    total: int,
    graded_tier: str,
) -> int:
    """Run one scrape pass for a card × tier at the given source tag
    (sold or asking). Returns the count of kept prices — the caller
    uses that to decide whether to trigger the asking fallback."""
    html = await _fetch_sold_html(
        browser, query, max_attempts=max_attempts, ipg=ipg, sold_only=sold_only
    )
    if not html:
        stats["errors"] += 1
        return 0
    listings = _parse_sold(html)
    stats["listings_parsed"] += len(listings)
    label = "sold" if sold_only else "ask"
    log.info(f"  [{label}] html len={len(html)}, parsed={len(listings)}")

    prices: list[float] = []
    rej = {"number": 0, "name": 0, "grade": 0}
    # Asking pass: relax the strict number match. Active listings
    # for niche vintage tiers already return few results; if the
    # seller wrote "Shining Charizard PSA 10 Neo Destiny" without
    # the "#107" in the title, we still want to count it. Name +
    # grade still filter the obvious wrong-card noise.
    strict_number = sold_only
    for title, price in listings:
        if strict_number and not _card_number_match(title, card.number):
            rej["number"] += 1
            continue
        if not _card_name_match(title, card.name):
            rej["name"] += 1
            continue
        if classify_grade(title) != wanted_grade:
            rej["grade"] += 1
            continue
        prices.append(price)

    min_needed = _min_for(wanted_grade)
    if len(prices) < min_needed:
        stats["empty_pages"] += 1
        log.info(
            f"  [{idx}/{total}] {card.id} ({card.name[:30]}) "
            f"{graded_tier} [{source_tag}]: n={len(prices)} "
            f"(rej {rej}) — below MIN({min_needed})"
        )
        return len(prices)

    stats["cards_with_data"] += 1
    stats["listings_in_bucket"] += len(prices)
    lo_raw, hi_raw = float(min(prices)), float(max(prices))
    lo, med, hi, n_kept = _trim_median(prices)
    log.info(
        f"  [{idx}/{total}] {card.id} ({card.name[:30]}) "
        f"{graded_tier} [{source_tag}]: n={len(prices)}→{n_kept} "
        f"lo=${lo:.2f} med=${med:.2f} hi=${hi:.2f} "
        f"(pre-trim ${lo_raw:.2f}-${hi_raw:.2f})"
    )
    if not dry_run:
        async with SessionLocal() as db:
            written = await _flush(
                db,
                [
                    {
                        "card_id": card.id,
                        "source": source_tag,
                        "variant": VARIANT,
                        "grade": wanted_grade,
                        "market_price_usd": med,
                        "low_price_usd": lo,
                        "mid_price_usd": med,
                        "high_price_usd": hi,
                        "sales_count": n_kept,
                        "snapshot_at": datetime.utcnow(),
                        "snapshot_date": snapshot_date,
                    }
                ],
            )
            stats["snapshots_written"] += written
    return len(prices)


# ── Main pipeline ─────────────────────────────────────────────────


async def run(
    graded_tier: str,
    snapshot_date: str,
    limit: int | None,
    min_price: float,
    throttle_ms: int,
    dry_run: bool,
    card_ids: list[str] | None,
    headless: bool,
    skip_if_recent_days: int,
    ipg: int,
    max_attempts: int,
    include_asking_fallback: bool,
) -> None:
    await init_db()

    cards = await _pick_cards(
        limit, min_price, card_ids,
        skip_if_recent_days=skip_if_recent_days,
        graded_tier=graded_tier,
        snapshot_date=snapshot_date,
    )
    log.info(
        f"scraping {len(cards)} cards for tier {graded_tier!r} "
        f"(headless={headless}, ipg={ipg}, max_attempts={max_attempts}, "
        f"skip_if_recent_days={skip_if_recent_days}, "
        f"asking_fallback={include_asking_fallback})"
    )

    stats = {
        "cards_seen": 0,
        "cards_with_data": 0,
        "listings_parsed": 0,
        "listings_in_bucket": 0,
        "snapshots_written": 0,
        "empty_pages": 0,
        "errors": 0,
    }

    browser, playwright = await _launch_browser(headless=headless)
    try:
        for card, set_obj in cards:
            stats["cards_seen"] += 1
            # Build query: card name + number + set name (cleaned) + tier.
            # eBay's search hits work best on natural language — strip
            # SET-code prefixes we use ("SV: ", "SWSH: ", "SM - ") that
            # collectors rarely type. Also drop the /Y denominator from
            # the card number so "161/131" becomes "161", matching how
            # sellers title their listings.
            parts = [card.name]
            if card.number:
                num = card.number.split("/")[0]
                parts.append(num)
            if set_obj is not None:
                set_name = re.sub(
                    r"^(?:SV|SWSH|SM|XY|BW|HGSS|DP|EX|ME)\s*[:\-]\s*",
                    "",
                    set_obj.name or "",
                    flags=re.IGNORECASE,
                )
                if set_name.strip():
                    parts.append(set_name.strip())
            parts.append(graded_tier)
            query = " ".join(str(p).strip() for p in parts if p)

            log.info(f"query: {query!r}")
            wanted_grade = classify_grade(f"dummy {graded_tier}")

            # === Sold pass ===
            n_sold = await _scrape_pass(
                browser=browser,
                query=query,
                card=card,
                wanted_grade=wanted_grade,
                source_tag=SOURCE,
                sold_only=True,
                snapshot_date=snapshot_date,
                dry_run=dry_run,
                ipg=ipg,
                max_attempts=max_attempts,
                stats=stats,
                idx=stats["cards_seen"],
                total=len(cards),
                graded_tier=graded_tier,
            )

            # === Asking fallback ===
            # Only fires when sold data didn't clear the tier's MIN and
            # the flag is enabled. Same query but without LH_Sold=1 —
            # broader pool for vintage / thin-liquidity tiers.
            wanted = classify_grade(f"dummy {graded_tier}")
            if include_asking_fallback and n_sold < _min_for(wanted):
                log.info(f"  (fallback → asking pass)")
                await _scrape_pass(
                    browser=browser,
                    query=query,
                    card=card,
                    wanted_grade=wanted_grade,
                    source_tag=SOURCE_ASKING,
                    sold_only=False,
                    snapshot_date=snapshot_date,
                    dry_run=dry_run,
                    ipg=ipg,
                    max_attempts=max_attempts,
                    stats=stats,
                    idx=stats["cards_seen"],
                    total=len(cards),
                    graded_tier=graded_tier,
                )

            if throttle_ms > 0:
                await asyncio.sleep(throttle_ms / 1000)
    finally:
        await browser.close()
        await playwright.stop()

    log.info(f"=== sold-scrape summary ({snapshot_date}, tier={graded_tier}) ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    log.info(f"  dry_run: {dry_run}")


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graded-tier",
        default="PSA 10",
        help='Grade tier to fetch this run — appended to the eBay query. '
        'Match the DOW rotation used by snapshot_ebay: "PSA 10", "CGC 10", '
        '"PSA 9", "CGC 9". Default "PSA 10".',
    )
    parser.add_argument(
        "--date",
        dest="snapshot_date",
        default=None,
        help="YYYY-MM-DD, defaults to today UTC.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--min-price",
        type=float,
        default=25.0,
        help="Skip cards with market_price_usd below this (default 25).",
    )
    parser.add_argument("--throttle-ms", type=int, default=1500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--card-id",
        dest="card_ids",
        action="append",
        help="Restrict to specific card_id (repeatable). Ignores --limit / --min-price.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help=(
            "Launch Chromium in headless mode. Default is visible because "
            "the site's automated-request protection fingerprints and throttle responses pure headless. On CI "
            "wrap the command in `xvfb-run` and leave this flag off — "
            "the browser will be visible-to-the-virtual-display and "
            "invisible-to-the-runner."
        ),
    )
    parser.add_argument(
        "--skip-if-today",
        action="store_true",
        help=(
            "Legacy alias for --skip-if-recent-days 1. Skip cards that "
            "already have an ebay_sold snapshot for the same tier today."
        ),
    )
    parser.add_argument(
        "--skip-if-recent-days",
        type=int,
        default=0,
        help=(
            "Skip cards with a snapshot in the last N days for the same "
            "tier. Zero means no skip. `1` gap-fills today's run. `14` "
            "enables rolling weekly coverage — the sweep never revisits "
            "a card it hit in the last 2 weeks, so week-over-week we "
            "drill deeper into the candidate pool instead of re-scraping "
            "the same top-300 chase."
        ),
    )
    parser.add_argument(
        "--ipg",
        type=int,
        default=60,
        help=(
            "Listings per page for the eBay sold query (_ipg). Bump to "
            "120 to widen the pool per query — helps CGC tiers where "
            "most of the 60 default slots are PSA slabs and only a "
            "handful survive the grade filter."
        ),
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=2,
        help=(
            "Retry budget per query. Each attempt uses a fresh browser "
            "context (new the site's automated-request protection cookie). Bump to 3 for gap-fill runs "
            "where throttle responses are the primary miss cause."
        ),
    )
    parser.add_argument(
        "--include-asking-fallback",
        action="store_true",
        help=(
            "When the sold pass returns n<MIN_LISTINGS for a card/tier, "
            "run a second pass on the same query WITHOUT the LH_Sold "
            "filter (active listings). Writes as source='ebay_asking' "
            "with the same tier grade. Populates tiles for thin markets "
            "(vintage CGC etc.) where sold data is sparse but active "
            "asks are plentiful. Frontend labels the tile 'Asking' so "
            "users see the source clearly."
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    snapshot_date = args.snapshot_date or date.today().isoformat()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Legacy --skip-if-today == --skip-if-recent-days 1
    skip_days = args.skip_if_recent_days
    if args.skip_if_today and skip_days <= 0:
        skip_days = 1

    asyncio.run(
        run(
            graded_tier=args.graded_tier,
            snapshot_date=snapshot_date,
            limit=args.limit,
            min_price=args.min_price,
            throttle_ms=args.throttle_ms,
            dry_run=args.dry_run,
            card_ids=args.card_ids,
            headless=args.headless,
            skip_if_recent_days=skip_days,
            ipg=args.ipg,
            max_attempts=args.max_attempts,
            include_asking_fallback=args.include_asking_fallback,
        )
    )


if __name__ == "__main__":
    main()
