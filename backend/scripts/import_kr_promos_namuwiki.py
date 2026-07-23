"""Import KR promo card catalog from namu.wiki 「한국 프로모 카드 일람」.

Runs Playwright against
    https://namu.wiki/w/포켓몬 카드 게임/한국 프로모 카드 일람
extracts every promo row from the 7 era tables (초대 / BW / XY / SM /
소드실드 / SV / MEGA), and upserts into `sets` + `cards`.

Set granularity is one bucket per H2 era, matching how JP promos are
already modeled (see set.py's set_type docstring — PROMO_NEW year
buckets). The KR promo page groups by era via H2 sections and by the
promo-code suffix on each row's number (`/BW`, `/XY-P`, `/SM-P`, ...),
so grouping by era is what the source itself does.

Set IDs use the Option-B `ko-p-{era}` convention. Era codes taken
from the KR promo suffix (or `base` for the pre-BW `NNN PROMO` batch,
`mega` for the current `M-P` series). Card IDs are
`{set_id}-{normalized-number}`; the "번호" cell's numeric prefix is
extracted verbatim, or the row falls back to a sentinel `p{n}` id when
there's no leading number (only 1 known row: `SV-P 파라다이스 리조트`).

Notes:
  - The listing page has NO card images inline — thumbnails live only
    on individual card articles. This importer sets image_small /
    image_large to NULL and defers image sourcing to a follow-up pass
    (options: tcgdex KR feed, pokemon.com KR product pages, per-card
    namuwiki article scrape).
  - Idempotent. Existing set/card rows with the same id are UPDATED
    with new name/number/language fields but never deleted. Rows that
    disappear from namu stay in the DB (LO can prune manually if a
    row was misclassified).

Usage:
    python -m scripts.import_kr_promos_namuwiki --dry-run
    python -m scripts.import_kr_promos_namuwiki
    python -m scripts.import_kr_promos_namuwiki --era bw   # single set
    python -m scripts.import_kr_promos_namuwiki --from-html <path>  # skip Playwright
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Card, Set  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("import_kr_promos_namuwiki")


NAMU_URL = "https://namu.wiki/w/포켓몬 카드 게임/한국 프로모 카드 일람"

# Fixed set metadata. release_date is a "start of era" estimate — the
# actual first card in each bucket predates its bucket's first mainline
# expansion by up to a few months (KR uses these dates as the era
# label). Precise per-card release dates aren't in scope for a
# catalog import.
SETS_META: list[dict] = [
    {
        "era": "base",
        "id": "ko-p-base",
        "name": "포켓몬 카드 게임 프로모 (초대)",
        "series": "초대",
        "release_date": date(2010, 2, 4),
    },
    {
        "era": "bw",
        "id": "ko-p-bw",
        "name": "포켓몬 카드 게임 프로모 (BW)",
        "series": "블랙&화이트",
        "release_date": date(2011, 4, 21),
    },
    {
        "era": "xy",
        "id": "ko-p-xy",
        "name": "포켓몬 카드 게임 프로모 (XY)",
        "series": "XY",
        "release_date": date(2014, 1, 30),
    },
    {
        "era": "sm",
        "id": "ko-p-sm",
        "name": "포켓몬 카드 게임 프로모 (SM)",
        "series": "썬&문",
        "release_date": date(2017, 3, 24),
    },
    {
        "era": "ss",
        "id": "ko-p-ss",
        "name": "포켓몬 카드 게임 프로모 (소드실드)",
        "series": "소드&실드",
        "release_date": date(2020, 3, 27),
    },
    {
        "era": "sv",
        "id": "ko-p-sv",
        "name": "포켓몬 카드 게임 프로모 (SV)",
        "series": "스칼렛&바이올렛",
        "release_date": date(2023, 4, 14),
    },
    {
        "era": "mega",
        "id": "ko-p-mega",
        "name": "포켓몬 카드 게임 프로모 (MEGA)",
        "series": "MEGA",
        "release_date": date(2026, 1, 1),
    },
]
_ERA_TO_META = {m["era"]: m for m in SETS_META}


def _classify_era(sample_number: str) -> str | None:
    """Map a "번호" cell to an era code by looking at the promo suffix."""
    n = sample_number.upper()
    if " PROMO" in n:
        return "base"
    if "/BW" in n:
        return "bw"
    if "XY-P" in n:
        return "xy"
    if "SM-P" in n:
        return "sm"
    if "SV-P" in n:
        return "sv"
    if "M-P" in n:
        return "mega"
    if "S-P" in n:  # after SV/SM/MEGA checks so those don't hit
        return "ss"
    return None


_NUMBER_PREFIX_RE = re.compile(r"^\s*(\d{1,4})\b")


def _normalize_card_number(raw: str, era: str, idx: int) -> tuple[str, int | None]:
    """Extract the numeric part of a '번호' cell for id + number columns.

    Returns (number_str, number_int_or_None). "001/BW" → ("001", 1),
    "SV-P" (no leading digits) → ("p{idx}", None) so a card that has no
    canonical number still gets a stable synthetic id.
    """
    m = _NUMBER_PREFIX_RE.match(raw)
    if m:
        return m.group(1), int(m.group(1))
    return f"p{idx:03d}", None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# ────────── HTML → rows ──────────

def _table_to_grid(table) -> list[list[str]]:
    """Rowspan-aware grid rebuild. namuwiki collapses cards that share
    an acquisition event with rowspan; a naive per-tr cell read leaves
    the later rows blank in the number column. Fill down here so every
    logical row has a full [번호, 이름, 획득 경로] triple."""
    rows = table.find_all("tr")
    grid: list[list[str | None]] = [[] for _ in rows]

    def _ensure_len(r: int, c: int) -> None:
        while len(grid[r]) <= c:
            grid[r].append(None)

    for r, tr in enumerate(rows):
        cells = tr.find_all(["th", "td"])
        c = 0
        for cell in cells:
            while c < len(grid[r]) and grid[r][c] is not None:
                c += 1
            try:
                rowspan = int(cell.get("rowspan") or 1)
            except ValueError:
                rowspan = 1
            try:
                colspan = int(cell.get("colspan") or 1)
            except ValueError:
                colspan = 1
            text = _clean(cell.get_text())
            for dr in range(rowspan):
                for dc in range(colspan):
                    tr_idx = r + dr
                    col_idx = c + dc
                    if tr_idx >= len(rows):
                        continue
                    _ensure_len(tr_idx, col_idx)
                    grid[tr_idx][col_idx] = text
            c += colspan

    return [[cell or "" for cell in row] for row in grid]


def parse_html(html: str) -> dict[str, list[dict]]:
    """Return {era_code: [ {number, name, acquisition}, ... ]} covering
    every non-empty table on the page."""
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    per_era: dict[str, list[dict]] = {}
    for table in tables:
        grid = _table_to_grid(table)
        if not grid:
            continue

        cards: list[dict] = []
        for row in grid[1:]:  # skip header
            if not any(cell.strip() for cell in row):
                continue
            number = row[0] if len(row) > 0 else ""
            name = row[1] if len(row) > 1 else ""
            acquisition = row[2] if len(row) > 2 else ""
            if not number and not name:
                continue
            cards.append({"number": number, "name": name, "acquisition": acquisition})

        # Dedupe by (number, name) — SV era on namu lists many rows for
        # the same card because it was distributed at multiple events;
        # each unique card lands once in our DB.
        seen: set[tuple[str, str]] = set()
        deduped: list[dict] = []
        for c in cards:
            key = (c["number"], c["name"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)

        era = _classify_era(deduped[0]["number"]) if deduped else None
        if era:
            per_era.setdefault(era, []).extend(deduped)
        else:
            log.warning(
                "  Skipping table with unrecognised era. Sample number: %r",
                deduped[0]["number"] if deduped else "—",
            )
    return per_era


# ────────── HTML fetch ──────────

async def fetch_html_playwright() -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            viewport={"width": 1400, "height": 3000},
        )
        page = await ctx.new_page()
        log.info("loading %s", NAMU_URL)
        await page.goto(NAMU_URL, wait_until="domcontentloaded", timeout=60_000)
        # Hydration wait — namu is a React SPA and initial goto returns
        # a shell. Scrolling to bottom triggers any lazy sections.
        await page.wait_for_timeout(5000)
        for _ in range(10):
            await page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            await page.wait_for_timeout(400)
        html = await page.content()
        await browser.close()
        return html


# ────────── DB writes ──────────

async def upsert_all(
    per_era: dict[str, list[dict]],
    era_filter: str | None,
    dry_run: bool,
) -> None:
    stats = {"sets_new": 0, "sets_updated": 0, "cards_new": 0, "cards_updated": 0}

    async with SessionLocal() as db:
        for meta in SETS_META:
            era = meta["era"]
            if era_filter and era != era_filter:
                continue
            cards = per_era.get(era, [])
            if not cards:
                log.info("era %s: no cards on namu page — skip", era)
                continue

            # ── set upsert ──
            existing_set = (await db.execute(
                select(Set).where(Set.id == meta["id"])
            )).scalar_one_or_none()
            if existing_set is None:
                set_row = Set(
                    id=meta["id"],
                    name=meta["name"],
                    name_local=meta["name"],
                    series=meta["series"],
                    release_date=meta["release_date"],
                    language="ko",
                    set_type="PROMO_NEW",
                    total=len(cards),
                    printed_total=len(cards),
                )
                db.add(set_row)
                stats["sets_new"] += 1
                action = "NEW"
            else:
                existing_set.name = meta["name"]
                existing_set.name_local = meta["name"]
                existing_set.series = meta["series"]
                existing_set.release_date = meta["release_date"]
                existing_set.language = "ko"
                existing_set.set_type = "PROMO_NEW"
                existing_set.total = max(existing_set.total or 0, len(cards))
                existing_set.printed_total = existing_set.total
                stats["sets_updated"] += 1
                action = "UPDATE"
            log.info("  set %-14s %-6s  %s  (%d cards)",
                     meta["id"], action, meta["name"], len(cards))

            # ── card upserts ──
            for idx, row in enumerate(cards, start=1):
                num_str, num_int = _normalize_card_number(row["number"], era, idx)
                card_id = f"{meta['id']}-{num_str}"
                name = row["name"]
                # Skip rows with no name — namu occasionally has a numbered
                # placeholder for a card that wasn't documented yet.
                if not name:
                    continue

                existing = (await db.execute(
                    select(Card).where(Card.id == card_id)
                )).scalar_one_or_none()

                if existing is None:
                    db.add(Card(
                        id=card_id,
                        name=name,
                        name_local=name,
                        number=num_str,
                        number_int=num_int,
                        set_id=meta["id"],
                        language="ko",
                        rarity="Promo",
                    ))
                    stats["cards_new"] += 1
                else:
                    existing.name = name
                    existing.name_local = name
                    existing.number = num_str
                    existing.number_int = num_int
                    existing.set_id = meta["id"]
                    existing.language = "ko"
                    if not existing.rarity:
                        existing.rarity = "Promo"
                    stats["cards_updated"] += 1

        if dry_run:
            log.info("MODE: DRY-RUN — rolling back")
            await db.rollback()
        else:
            await db.commit()
            log.info("MODE: LIVE — committed")

    log.info("=== summary ===")
    for k, v in stats.items():
        log.info("  %-15s %d", k, v)


# ────────── CLI ──────────

async def _amain(args: argparse.Namespace) -> None:
    if args.from_html:
        html = Path(args.from_html).read_text(encoding="utf-8")
        log.info("loaded HTML from %s (%d chars)", args.from_html, len(html))
    else:
        html = await fetch_html_playwright()

    per_era = parse_html(html)
    log.info("parsed eras: %s",
             {k: len(v) for k, v in per_era.items()})

    if args.parse_only:
        # For debugging — dump extraction and exit
        out = Path(args.parse_only)
        out.write_text(json.dumps(per_era, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        log.info("wrote parse-only json to %s", out)
        return

    await init_db()
    await upsert_all(per_era, args.era, args.dry_run)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Parse + build upsert plan, roll back the DB txn.")
    p.add_argument("--era", choices=[m["era"] for m in SETS_META],
                   help="Limit to one era (base|bw|xy|sm|ss|sv|mega).")
    p.add_argument("--from-html", metavar="PATH",
                   help="Skip Playwright, read HTML from a local file.")
    p.add_argument("--parse-only", metavar="OUT",
                   help="Write parsed per-era JSON to this path and exit.")
    args = p.parse_args()
    asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
