"""Populate Set.name_ko with Korean set name translations from TCGdex.

Strategy
--------
TCGdex (https://api.tcgdex.net/v2/ko/sets) returns 95 KR-released sets
with their Korean names + release dates + total card count. We don't
get a stable foreign key back to pokemontcg.io ids, so we match each
KR set to an EN set in our DB using a weighted heuristic:

  1. Release date proximity  (strongest signal - same TCG release
     usually ships globally within 1-3 months).
  2. Total card count match.
  3. Series name proximity   (TCGdex KR serie names map roughly
     onto pokemontcg.io series).

Idempotent. Run whenever you want to refresh translations.

Usage:
    python -m scripts.import_ko_set_names              # full sync
    python -m scripts.import_ko_set_names --dry-run    # preview matches
    python -m scripts.import_ko_set_names --override   # overwrite existing name_ko
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher

import httpx
from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Set

TCGDEX_BASE = "https://api.tcgdex.net/v2"
log = logging.getLogger("import_ko_set_names")

# Hand-curated EN -> KR series mapping, verified against TCGdex /ko/sets
# detail endpoints. TCGdex's series names use slightly idiosyncratic
# transliterations (검과 방패 vs the more familiar 소드&실드, 스칼렛・
# 바이올렛 with a katakana middle dot vs &); we go with the literal
# strings TCGdex returns so the equality check works.
SERIES_EN_TO_KO = {
    "scarlet & violet": "스칼렛・바이올렛",
    "sword & shield": "검과 방패",
    "sun & moon": "썬&문",
    "xy": "XY",
    "black & white": "블랙&화이트",
    "diamond & pearl": "다이아몬드&펄",
    "heartgold & soulsilver": "하트골드&소울실버",
    "mega evolution": "메가에볼루션",
}

# Hand-curated EN-set-id -> KR set name mapping. The auto-match below
# tries TCGdex's /ko/sets feed, but EN/JP/KR release schedules don't
# 1:1 align (KR follows JP, so date-based matching collides with JP-
# exclusive sets). For the sets users actually search for - the top
# ~40 by popularity - we override with a curated KR name. The auto-
# matcher still backfills the long tail at lower confidence.
MANUAL_EN_TO_KO_NAME: dict[str, str] = {
    # Scarlet & Violet era
    "sv1":          "스칼렛&바이올렛",
    "sv2":          "패러독스 리프트",
    "sv3":          "흑염의 지배자",
    "sv3pt5":       "포켓몬 카드 151",
    "sv4":          "고대의 포효",
    "sv4pt5":       "팔데아의 운명",
    "sv5":          "템포럴 포스",
    "sv6":          "트와일라이트 마스커레이드",
    "sv6pt5":       "그림자 우화",
    "sv7":          "스텔라 크라운",
    "sv8":          "환영의 화염",
    "sv8pt5":       "프리즘 진화",
    "sv9":          "여정 동행",
    "sv10":         "운명의 라이벌",
    "zsv10pt5":     "블랙 볼트",
    "rsv10pt5":     "화이트 플레어",
    # Mega Evolution era
    "me1":          "메가에볼루션",
    "me2":          "환영의 불꽃",
    "me2pt5":       "어센디드 히어로즈",
    "me3":          "퍼펙트 오더",
    "me4":          "카오스 라이징",
    # Sword & Shield era — KR-popular subset
    "swsh1":        "소드&실드",
    "swsh4":        "찬란한 별",
    "swsh7":        "이브이 히어로즈",
    "swsh9":        "찬란한 별빛",
    "swsh10":       "은빛 폭풍",
    "swsh11":       "잃어버린 기원",
    "swsh12":       "은빛 별 같은 환상",
    "swsh12pt5":    "크라운 제니스",
    # Iconic vintage
    "base1":        "베이스 세트",
    "neo1":         "네오 제네시스",
    "neo4":         "네오 데스티니",
    "cel25":        "셀러브레이션",
    "sm115":        "히든 페이츠",
}


@dataclass
class KoSet:
    id: str
    name_ko: str
    series_ko: str | None
    release_date: date | None
    total: int | None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


async def _fetch_ko_sets(client: httpx.AsyncClient) -> list[KoSet]:
    """Two-stage fetch: the index endpoint omits releaseDate, the per-set
    detail endpoint includes it. Fan out detail fetches with bounded
    concurrency to keep TCGdex happy."""
    resp = await client.get(f"{TCGDEX_BASE}/ko/sets", timeout=30)
    resp.raise_for_status()
    index = resp.json()

    sem = asyncio.Semaphore(8)

    async def fetch_one(s: dict) -> KoSet:
        async with sem:
            sid = s.get("id", "")
            try:
                r = await client.get(f"{TCGDEX_BASE}/ko/sets/{sid}", timeout=15)
                r.raise_for_status()
                d = r.json()
            except httpx.HTTPError:
                # Fall back to index data; we just won't have a date.
                d = s
            return KoSet(
                id=sid,
                name_ko=d.get("name", s.get("name", "")),
                series_ko=(d.get("serie") or s.get("serie") or {}).get("name"),
                release_date=_parse_date(d.get("releaseDate")),
                total=(d.get("cardCount") or s.get("cardCount") or {}).get("total"),
            )

    return await asyncio.gather(*[fetch_one(s) for s in index])


def _series_matches(en_series: str | None, ko_series: str | None) -> bool:
    """Does this EN series correspond to the KR series via our mapping?"""
    if not en_series or not ko_series:
        return False
    expected_ko = SERIES_EN_TO_KO.get(en_series.lower())
    if expected_ko is None:
        # Unknown series - fall through to name similarity (handles XY etc
        # where the KR name is the same Latin letters).
        return SequenceMatcher(
            None, en_series.lower(), ko_series.lower()
        ).ratio() >= 0.6
    return expected_ko == ko_series


def _score(en_set: Set, ko: KoSet) -> float:
    """Higher = better match. Returns 0 when there's not enough signal.

    Hard gate: series must align via SERIES_EN_TO_KO (or fuzzy-match for
    Latin-letter series). Without that the (date, count) heuristics
    happily mismatch SM-era KR sets to SV-era EN sets.
    """
    if not _series_matches(en_set.series, ko.series_ko):
        return 0.0

    # Date proximity: 1.0 at 0 days, 0.0 at 365 days, linear in between.
    # KR releases generally land 1-3 months after the JP / EN cycle.
    date_score = 0.0
    if en_set.release_date and ko.release_date:
        delta_days = abs((en_set.release_date - ko.release_date).days)
        date_score = max(0.0, 1.0 - delta_days / 365.0)

    # Card-count match: hard +1 when totals tie exactly, partial when close.
    count_score = 0.0
    if en_set.total and ko.total:
        diff = abs(en_set.total - ko.total)
        if diff == 0:
            count_score = 1.0
        elif diff <= 5:
            count_score = 0.6
        elif diff <= 15:
            count_score = 0.2

    # Series match contributes a flat anchor so series-only matches
    # still clear the threshold when one signal is missing.
    return 0.5 * date_score + 0.4 * count_score + 0.1


async def run(dry: bool, override: bool, auto: bool) -> None:
    """Two passes:

      1. Manual mapping  (always trusted, overrides existing name_ko
                          when --override is set).
      2. Auto-match      (only when --auto is set; lower quality,
                          opt-in because EN/JP/KR release schedules
                          don't 1:1 align).
    """
    await init_db()

    async with SessionLocal() as db:
        en_sets = list((await db.execute(
            select(Set).where(Set.language == "en")
        )).scalars())
    en_by_id = {s.id: s for s in en_sets}
    log.info(f"Have {len(en_sets)} EN sets in DB.")

    # ── Pass 1: manual mapping ───────────────────────────────────────
    manual_updated = 0
    manual_skipped_existing = 0
    manual_unknown_id = 0

    log.info(f"\nApplying {len(MANUAL_EN_TO_KO_NAME)} manual mappings:")
    for en_id, name_ko in MANUAL_EN_TO_KO_NAME.items():
        en = en_by_id.get(en_id)
        if en is None:
            log.info(f"  [skip ] {en_id:15s} -> {name_ko:25s} (no such EN set in DB)")
            manual_unknown_id += 1
            continue
        if en.name_ko and not override:
            log.info(f"  [keep ] {en_id:15s} {en.name[:25]:25s} -> {en.name_ko:25s} (existing)")
            manual_skipped_existing += 1
            continue
        log.info(f"  [write] {en_id:15s} {en.name[:25]:25s} -> {name_ko:25s}")
        manual_updated += 1

    if not dry:
        async with SessionLocal() as db:
            for en_id, name_ko in MANUAL_EN_TO_KO_NAME.items():
                row = await db.get(Set, en_id)
                if row is None:
                    continue
                if row.name_ko and not override:
                    continue
                row.name_ko = name_ko
            await db.commit()

    # ── Pass 2: opt-in auto-match ────────────────────────────────────
    auto_pairs: list[tuple[Set, KoSet, float]] = []
    if auto:
        async with httpx.AsyncClient() as http:
            ko_sets = await _fetch_ko_sets(http)
        log.info(f"\nFetched {len(ko_sets)} KR sets from TCGdex for auto-match.")

        candidates: list[tuple[float, Set, KoSet]] = []
        manual_locked = set(MANUAL_EN_TO_KO_NAME.keys())
        for en in en_sets:
            if en.id in manual_locked:
                continue  # Manual takes precedence; never re-match these.
            for ko in ko_sets:
                s = _score(en, ko)
                if s >= 0.7:  # higher threshold than before — auto is best-effort
                    candidates.append((s, en, ko))
        candidates.sort(key=lambda t: -t[0])

        used_en_ids: set[str] = set()
        used_ko_ids: set[str] = set()
        for s, en, ko in candidates:
            if en.id in used_en_ids or ko.id in used_ko_ids:
                continue
            used_en_ids.add(en.id)
            used_ko_ids.add(ko.id)
            auto_pairs.append((en, ko, s))

        log.info(f"Auto-matched {len(auto_pairs)} additional pairs at score >= 0.7:")
        for en, ko, s in auto_pairs[:20]:
            log.info(f"  [{s:.2f}] {en.id:15s} {en.name[:25]:25s} -> {ko.name_ko:25s}")

        if not dry:
            async with SessionLocal() as db:
                for en, ko, _ in auto_pairs:
                    row = await db.get(Set, en.id)
                    if row is None or (row.name_ko and not override):
                        continue
                    row.name_ko = ko.name_ko
                await db.commit()

    log.info(f"\n=== Summary ===")
    log.info(f"  Manual write rows    : {manual_updated}")
    log.info(f"  Manual skipped       : {manual_skipped_existing} (existing)")
    log.info(f"  Manual unknown ids   : {manual_unknown_id}")
    if auto:
        log.info(f"  Auto-matched pairs   : {len(auto_pairs)}")
    if dry:
        log.info(f"  MODE                 : DRY RUN (no writes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview matches without writing")
    parser.add_argument("--override", action="store_true", help="Overwrite existing name_ko values")
    parser.add_argument(
        "--auto", action="store_true",
        help=(
            "Also run the TCGdex auto-matcher for sets not in MANUAL_EN_TO_KO_NAME. "
            "Off by default because EN/JP/KR release schedules diverge and the "
            "matcher produces some plausible-but-wrong pairs."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run, args.override, args.auto))


if __name__ == "__main__":
    main()
