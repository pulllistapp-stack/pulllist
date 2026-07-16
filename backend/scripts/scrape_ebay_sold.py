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
# Universal MIN=2. The _udlo price floor added upstream now filters
# ~95% of the noise that the older MIN=5 gate was defending against
# (Booster Bundles, wrong-set Latias, fan art, unrelated cheap
# Pokemon). With that upstream filter in place, any two listings
# that pass number+name+grade are almost certainly legit signal —
# and demanding 5+ was throwing away real data on thin-market cards.
# BGS 10 Black Label kept at 1 (Pop of 3-10 globally on most SIRs).
MIN_LISTINGS_PER_GRADE = 2
TIER_MIN_OVERRIDES: dict[str, int] = {
    "bgs10bl": 1,
}


def _min_for(grade: str, card_raw_usd: float | None = None) -> int:
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


_SLASH_NUM_RE = re.compile(r"\b(\d{1,3})\s*/\s*\d{1,3}\b")


def _card_number_match(title: str, card_number: str | None) -> bool:
    """Match a listing title to the card we're scraping, using a
    two-layer check that survives common false-positive traps like
    "170 HP" (the printed HP of Latias & Latios GX) leaking into
    scrapes for card #170.

    Layer 1 — slash-format wins: if the title contains any
    `NN/TTT` card-number pattern (the format sellers use to
    disambiguate prints), then OUR number MUST appear in one of
    those slash pairs. Otherwise it's a different print of the
    same character and we reject.

    Layer 2 — bare-number fallback: if the title has no slash
    pattern anywhere, accept when our number appears as a word.
    This keeps promo listings ("Umbreon Prerelease") that never
    print a card-number format from getting dropped.

    Bulk lot / accessory titles with no number and no slash still
    have to pass the separate name filter, so pure noise still
    gets caught downstream.
    """
    if not card_number:
        return True
    num = card_number.split("/")[0].lstrip("0") or card_number.split("/")[0]
    if not num:
        return True
    try:
        our_num_int = int(num)
    except ValueError:
        our_num_int = None

    # Layer 1: does the title use slash-format card numbers?
    slash_matches = _SLASH_NUM_RE.findall(title)
    if slash_matches:
        slash_ints = [int(s) for s in slash_matches]
        # Our number MUST be one of the slash numerators.
        return our_num_int is not None and our_num_int in slash_ints

    # Layer 2: no slash pattern → fallback to word-bounded bare number.
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
    min_price: float | None = None,
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
            # Force minimum price when raw value is high. eBay silently
            # ignores our quoted card number for niche searches and
            # returns broad "trending" items (Booster Bundle, unrelated
            # Latias cards). A price floor at 30% of raw eliminates
            # 95%+ of that noise while keeping every graded slab that
            # matters (graded is almost always >= raw × 0.5).
            price_param = ""
            if min_price and min_price > 0:
                price_param = f"&_udlo={int(min_price)}"
            url = (
                f"{base}&LH_Sold=1&LH_Complete=1&_ipg={ipg}{price_param}"
                if sold_only
                else f"{base}&_ipg={ipg}{price_param}"
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
    # Price floor kills unrelated cheap noise (Booster Bundle, wrong
    # Latias, fan art). 30% of the card's raw market — graded slabs
    # basically never sell below that even in rough condition.
    raw = float(card.market_price_usd or 0)
    min_price = max(20.0, raw * 0.30) if raw >= 40 else None
    html = await _fetch_sold_html(
        browser, query, max_attempts=max_attempts, ipg=ipg,
        sold_only=sold_only, min_price=min_price,
    )
    if not html:
        stats["errors"] += 1
        return 0
    # Detect eBay's silent search-relaxation. When our query is too
    # narrow (e.g. "Latias & Latios 170 PSA 10" for a card that has
    # zero sold PSA 10 in the sample window) eBay drops tokens and
    # returns broader matches — sometimes with a banner, sometimes
    # without. If we detect the banner we still parse (the results
    # aren't for our exact card but the download wasn't free) and
    # log so a debugger can see it.
    auto_relaxed = (
        "No exact matches found" in html
        or "Results matching fewer words" in html
    )
    listings = _parse_sold(html)
    stats["listings_parsed"] += len(listings)
    label = "sold" if sold_only else "ask"
    relax_note = " AUTO-RELAXED" if auto_relaxed else ""
    log.info(f"  [{label}] html len={len(html)}, parsed={len(listings)}{relax_note}")

    prices: list[float] = []
    rej = {"number": 0, "name": 0, "grade": 0}
    rej_samples = {"number": [], "name": [], "grade": []}
    # Both passes now use the same number matcher. The matcher's
    # Layer-2 fallback (bare-number match when title has no slash
    # format) already handles the "Shining Charizard PSA 10 Neo
    # Destiny" no-slash case that the old asking-only relaxation
    # was aimed at. Meanwhile Layer-1 (slash pattern present →
    # MUST include ours) prevents wrong-print contamination we
    # discovered with Latias & Latios GX #170 pulling #116 UR
    # listings via a false "170 HP" match in the title.
    for title, price in listings:
        if not _card_number_match(title, card.number):
            rej["number"] += 1
            if len(rej_samples["number"]) < 5:
                rej_samples["number"].append(title[:100])
            continue
        if not _card_name_match(title, card.name):
            rej["name"] += 1
            if len(rej_samples["name"]) < 5:
                rej_samples["name"].append(title[:100])
            continue
        if classify_grade(title) != wanted_grade:
            rej["grade"] += 1
            if len(rej_samples["grade"]) < 5:
                rej_samples["grade"].append(title[:100])
            continue
        prices.append(price)

    # When rejection rate is >80%, log sample titles so we can
    # diagnose whether the scraper is seeing wrong-print listings
    # (eBay auto-relaxed) or its own parser is misbehaving.
    if listings and (rej["number"] + rej["name"] + rej["grade"]) / len(listings) > 0.8:
        for kind, samples in rej_samples.items():
            for i, t in enumerate(samples):
                log.info(f"    reject.{kind}[{i}]: {t}")

    min_needed = _min_for(wanted_grade, float(card.market_price_usd or 0))
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
            # collectors rarely type.
            #
            # Card number is WRAPPED IN QUOTES so eBay treats it as a
            # required phrase. Without quotes eBay silently drops the
            # number token when few results exist and returns broadly
            # matching cards of the same character — "Latias & Latios
            # GX PSA 10 170" gets relaxed to just "Latias & Latios GX
            # PSA 10" which pulls #116/181 base prints ($50) mixed
            # with our #170 alt-art SIR ($15k) and destroys the
            # median. This behavior is stronger from datacenter IPs
            # (GH Actions runners) than home IPs, so it's invisible
            # in local testing but wrecks CI runs.
            parts = [card.name]
            if card.number:
                num = card.number.split("/")[0]
                # Just the numerator quoted — allows "170", "#170",
                # and "170/181" to all match. Quoting the full
                # "170/181" would drop the ~half of listings that
                # only include "#170".
                parts.append(f'"{num}"')
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
            if include_asking_fallback and n_sold < _min_for(wanted, float(card.market_price_usd or 0)):
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
