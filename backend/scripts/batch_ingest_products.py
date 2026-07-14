"""Batch-ingest sealed products for every EN set by matching TCGCSV
groups to our set records by name.

Rationale: `ingest_products.py` handles one TCGCSV group at a time and
requires --set-id + --group manually. When we launched sealed products
we only did the 7 Mega Evolution era sets by hand. To cover the rest
of the SV / SWSH / older catalog (30+ sets, ~500-1000 SKUs) we need a
batch runner.

Matching strategy: normalize both sides (lowercase, strip punctuation,
strip common prefixes like "SV: ") and score by whether both share the
distinctive set token — usually the set number ("SV01", "SWSH08") or
the printed set name ("Twilight Masquerade", "Evolving Skies").
Confirm each match in the log; skip on ambiguous / unknown mappings.

Usage:
    python -m scripts.batch_ingest_products              # ingest all matched sets
    python -m scripts.batch_ingest_products --dry-run    # just print the mapping
    python -m scripts.batch_ingest_products --only sv01,sv02  # limit to specific set ids
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.set import Set
from scripts.ingest_products import ingest_group


TCGCSV = "https://tcgcsv.com/tcgplayer/3"
UA = "PullList-Products/1.0 (+https://pulllist.org)"


# Manual overrides for sets whose auto-match is unreliable — the
# TCGCSV name and our set name diverge just enough that a fuzzy match
# would miss or pick the wrong twin (e.g. multiple Trainer Gallery
# subsets sharing a parent name).
#
# Format: our_set_id -> tcgcsv_group_id
_MANUAL_MAP: dict[str, int] = {
    # Already-seeded via prior manual ingest; kept here so a re-run
    # updates rather than skips them.
    "me1": 24451,
    "me2": 24557,
    "me3": 24747,
    "me4": 24893,
    "me5": 25023,
    "me2pt5": 24611,  # Ascended Heroes
    "me30": 25147,    # 30th Celebration
}


def _normalize(s: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace. Keeps digits
    intact so 'SV01' matches 'sv01'."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# TCGCSV names carry era-prefixes we don't ("SV09: Journey Together",
# "SWSH12: Silver Tempest", "SM - Cosmic Eclipse"). Strip them so a
# token-overlap comparison against our shorter set names ("Journey
# Together") actually scores. The era code is preserved as a separate
# token via _era_code() so it can still contribute to matching.
_ERA_PREFIX_RE = re.compile(
    r"^(?:sv\d*|swsh\d*|sm|xy|bw|hgss|dp|ex|me\d*|mee|fpic\S*)\s*[:\-]\s*",
    re.IGNORECASE,
)


def _strip_prefix(name: str) -> str:
    return _ERA_PREFIX_RE.sub("", name).strip()


def _era_code(set_id: str) -> str | None:
    """Extract the era code from our set id (sv9 → sv9, swsh12tg →
    swsh12) — used to boost matches that also mention it in the
    TCGCSV name."""
    m = re.match(r"^(sv|swsh|sm|xy|bw|hgss|dp|ex|me|mee|fpic)(\d+(?:pt\d+)?)", set_id)
    if not m:
        return None
    return (m.group(1) + m.group(2)).lower()


def _tokens(s: str) -> set[str]:
    return set(_normalize(_strip_prefix(s)).split())


def _score_match(our_set: Set, tcgcsv_group: dict) -> int:
    """Higher = more likely the same set. Uses a token overlap heuristic
    with bonus points for shared set-number-style tokens (sv01, swsh05
    etc.) and printed_total agreement."""
    our_tokens = _tokens(our_set.name)
    their_tokens = _tokens(tcgcsv_group.get("name", ""))
    # Drop generic filler tokens that don't add signal.
    stop = {"pokemon", "set", "the", "a", "and", "of"}
    our_tokens -= stop
    their_tokens -= stop
    if not our_tokens or not their_tokens:
        return 0
    overlap = our_tokens & their_tokens
    if not overlap:
        return 0

    score = len(overlap) * 10
    # Bonus for set-code tokens like sv01, swsh05, xy1 — those are
    # highly discriminative.
    code_pattern = re.compile(r"^(sv|swsh|sm|xy|bw|hgss|dp|ex|me|fpic|mee)\d+")
    for tok in overlap:
        if code_pattern.match(tok):
            score += 50
    # Era-code bonus: if our set_id encodes an era number (e.g. sv9,
    # swsh12) and the TCGCSV name mentions the same code (padded or
    # not — TCGCSV writes "SV01" while we use "sv1"), that's a
    # near-certain match.
    era = _era_code(our_set.id)
    if era:
        m = re.match(r"^([a-z]+)(\d+)(pt\d+)?$", era)
        if m:
            prefix, num, sub = m.group(1), m.group(2), m.group(3) or ""
            padded = f"{prefix}{int(num):02d}{sub}"
            haystack = tcgcsv_group.get("name", "").lower()
            if re.search(rf"\b{era}\b", haystack) or re.search(
                rf"\b{padded}\b", haystack
            ):
                score += 60
    # Small penalty if the total-token overlap ratio is low — a match
    # sharing "swsh" but no other tokens shouldn't win.
    ratio = len(overlap) / max(len(our_tokens), len(their_tokens))
    if ratio < 0.3:
        score -= 15

    return score


async def _fetch_groups(client: httpx.AsyncClient) -> list[dict]:
    r = await client.get(f"{TCGCSV}/groups", timeout=45)
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        return payload.get("results") or []
    return payload or []


async def _build_mapping(
    our_sets: list[Set],
    groups: list[dict],
    min_score: int = 30,
) -> tuple[dict[str, int], list[Set]]:
    """Returns (matched, unmatched). `matched` is our_set_id -> group_id."""
    matched: dict[str, int] = {}
    unmatched: list[Set] = []
    for s in our_sets:
        if s.id in _MANUAL_MAP:
            matched[s.id] = _MANUAL_MAP[s.id]
            continue
        best_score = 0
        best_group: Optional[dict] = None
        for g in groups:
            sc = _score_match(s, g)
            if sc > best_score:
                best_score = sc
                best_group = g
        if best_group is not None and best_score >= min_score:
            matched[s.id] = int(best_group["groupId"])
        else:
            unmatched.append(s)
    return matched, unmatched


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print mapping + would-ingest counts, don't hit the DB.",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Comma-separated set ids to limit the run (e.g. sv01,swsh12).",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=30,
        help="Minimum match score to accept an auto-mapping (default 30).",
    )
    args = parser.parse_args()

    only_filter = (
        {s.strip() for s in args.only.split(",") if s.strip()}
        if args.only
        else None
    )

    async with SessionLocal() as db:
        our_sets = (
            await db.execute(
                select(Set).where(Set.language == "en").order_by(Set.release_date.desc())
            )
        ).scalars().all()

    if only_filter is not None:
        our_sets = [s for s in our_sets if s.id in only_filter]

    print(f"loaded {len(our_sets)} EN sets from DB")

    async with httpx.AsyncClient(headers={"User-Agent": UA}) as client:
        groups = await _fetch_groups(client)
    print(f"fetched {len(groups)} TCGCSV groups")

    matched, unmatched = await _build_mapping(our_sets, groups, args.min_score)
    print(f"matched: {len(matched)}, unmatched: {len(unmatched)}")

    if unmatched:
        print("--- unmatched sets (no TCGCSV group above threshold) ---")
        for s in unmatched[:30]:
            print(f"  {s.id:20} {s.name}")
        if len(unmatched) > 30:
            print(f"  ... {len(unmatched) - 30} more")

    # Ingest each mapped group.
    totals = {"sets": 0, "added": 0, "updated": 0, "sealed": 0}
    for set_id, group_id in matched.items():
        try:
            stats = await ingest_group(
                group_id, set_id=set_id, dry_run=args.dry_run
            )
        except Exception as e:
            print(f"[err ] {set_id:20} group={group_id}: {e}")
            continue
        totals["sets"] += 1
        totals["added"] += stats.get("added", 0)
        totals["updated"] += stats.get("updated", 0)
        totals["sealed"] += stats.get("sealed", 0)
        print(
            f"[done] {set_id:20} group={group_id:5}  "
            f"sealed={stats.get('sealed', 0):3}  added={stats.get('added', 0):3}  "
            f"updated={stats.get('updated', 0):3}"
        )

    print("\n=== BATCH SUMMARY ===")
    print(f"  sets processed: {totals['sets']}")
    print(f"  sealed found  : {totals['sealed']}")
    print(f"  products added: {totals['added']}")
    print(f"  products updated: {totals['updated']}")
    print(f"  unmatched sets: {len(unmatched)}")
    print(f"  dry_run       : {args.dry_run}")


if __name__ == "__main__":
    asyncio.run(main())
