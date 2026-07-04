"""Fill in JPP-U* card images from TCGPlayer's promo catalog via TCGCSV.

Complementary to import_bulbapedia_unnumbered_jp.py + mirror_jpp_unn_images.py:
  - Bulbapedia gave us 127/496 (CoroCoro 1996-1999 base promos, Illustrator,
    Trophy, base Pikachu/Mew).
  - TCGPlayer's Nintendo Promos / Misc / Pikachu World Collection groups
    carry a different bucket: Ancient Mew (Japanese Exclusive Print), the
    JP 10th/11th Movie Commemoration sets, Trophy Pikachu variants (Snap,
    Movie, Baby, Ivy, Jungle), Southern Islands, WoTC Black Star reprints
    of JP CoroCoro art, and various stamped/glossy JP-only releases.

Strategy:
    1) Pull products from a curated group list.
    2) Build a normalized-name -> [products] index.
    3) For each JPP-U* card with image_small IS NULL, look up its base name
       and pick the best product using flavor_text keyword overlap.
    4) Download images locally to frontend/public/jp-unn/{card_id}.jpg
       (same convention as mirror_jpp_unn_images.py so the frontend needs
       no additional remotePatterns entries).
    5) Update DB: image_small, image_large, tcgplayer_product_id, tcgplayer_url.

Idempotent: re-running skips cards that already have image_small set.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("backfill_jpp_unn_from_tcgplayer")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIRROR_DIR = REPO_ROOT / "frontend" / "public" / "jp-unn"

TCGCSV = "https://tcgcsv.com/tcgplayer/3"

# (group_id, label, prefer_flag) — prefer=True means match candidates
# from this group win ties against non-preferred groups. JP-explicit
# groups are preferred; EN Wizards / Southern Islands are fallback.
CANDIDATE_GROUPS: list[tuple[int, str, bool]] = [
    (2374, "Misc",             True),   # Ancient Mew (JP Exclusive Print), JP Movie sets
    # We intentionally DO NOT include:
    #   648 SouthernIslands  — JPP-SI is its own set, not JPP-U
    #   1418 WoTC Promo      — Neo/Rocket-era WoTC promos ≠ their JP CoroCoro
    #                          counterparts on close inspection (different
    #                          holo pattern / stamp / text panel).
    #   1423 NintendoPromos  — e-League EN cards ≠ JP e-Card series
    #   2205 PikachuWorld    — 2010 English-language re-release, not JP
    #   1938 AltArt          — XY-era EN
    #   1528 Jumbo           — mostly EN oversize reprints of unrelated cards;
    #                          Shadow Lugia (Nintendo World Promo) handled via
    #                          _MANUAL_OVERRIDES below.
]

# Hand-curated overrides for specific cards that don't come through the
# name+flavor matcher cleanly. Value = (tcgplayer_product_id, imageUrl,
# display_name, tcgplayer_url).
_MANUAL_OVERRIDES: dict[str, dict] = {
    "JPP-U1996-251": {
        "productId": 127168,
        "name":      "Shadow Lugia (Nintendo World Promo)",
        "imageUrl":  "https://tcgplayer-cdn.tcgplayer.com/product/127168_200w.jpg",
        "url":       None,
        "group":     "Manual",
        "prefer":    True,
    },
}

# Distinctive tokens we look for in BOTH flavor_text and TCGPlayer product
# name. Overlap = signal that we've got the right variant. Order matters
# for tie-breaks (earlier = more distinctive).
_DISTINCTIVE_TOKENS = [
    "japanese exclusive", "japanese", "corocoro", "coro coro",
    "snap", "movie promo", "movie", "trophy", "tropical",
    "phone card", "phone", "birthday", "glossy", "bilingual",
    "postcard", "prerelease", "poketour", "e3 stamped",
    "10th anniversary", "20th anniversary", "10th movie",
    "11th movie", "world hobby", "old school", "flying",
    "surfing", "baby", "ivy", "ancient", "jr east", "stamp rally",
    "jumbo", "oversize", "pokemon center", "space center",
]

# Names that are too generic to trust from name-only match (e.g.
# multiple Pikachu variants in TCGPlayer). Require STRONG keyword hit.
_GENERIC_NAMES = {"pikachu", "mew", "mewtwo", "eevee", "charizard",
                  "blastoise", "venusaur", "jigglypuff"}

# TCGPlayer product-name tokens that mark a MODERN EN reprint variant
# whose art doesn't match our vintage JP promo (Cosmos Holo overlays,
# modern-set stamp promos, retailer exclusives, etc.). Reject on sight.
_REJECT_TOKENS = [
    "cosmos holo", "cosmos holofoil", "cosmo holo", "sheen holo",
    "cracked ice holo", "reverse holo",
    "stamped)", "stamp)", "black bolt stamped",
    "best buy exclusive", "toys r us", "toys \"r\" us",
    "eb games", "7-eleven", "target exclusive",
    "walmart exclusive", "library exclusive", "build-a-bear",
    "poke ball tin", "poké ball tin", "warner bros",
    "collector's chest tin", "collector chest",
    "holiday calendar", "battle academy", "world championships",
    "sneak-peek tin", "poster collection", "games expo",
    "vstar premium", "vstar universe", "ex box", "premium collection",
    "international version", "dvd release", "special collection",
    "black and white tour", "tour promo",
    "raikou, entei", "entei, suicune", "reshiram, zekrom", " & suicune",
    "mega ", "-mega",  # SV Mega Evolution (2024+)
]

# Modern-era markers — any of these in the product name means it's a
# 2010s+ EN release that will not visually match a JP vintage promo.
_MODERN_ERA_MARKERS = [
    "vstar", "vmax", "v-union", " gx ", "-gx", "-vmax", "-vstar",
    "swsh", "sv0", "sv1", "sv2",
    "prismatic evolutions", "obsidian flames", "twilight masquerade",
    "paradox rift", "temporal forces", "shrouded fable",
    "team flare", "dp black star", "xy black star",
    # Modern set numbers (post-2010 reprint of vintage art)
    "/106", "/108", "/109", "/111", "/113", "/115", "/119", "/122",
    "/123", "/124", "/130", "/132", "/146", "/149", "/156", "/160",
    "/172", "/182", "/189", "/193", "/198", "/202", "/236",
    # Box products (not cards)
    " box", "box)",
]


def _is_rejected(product_name: str) -> bool:
    p = product_name.lower()
    # Whitelist bypass: "Japanese" explicit marker overrides most rejects
    if "japanese" in p and "commemoration" in p:
        return False
    if any(tok in p for tok in _REJECT_TOKENS):
        return True
    if any(tok in p for tok in _MODERN_ERA_MARKERS):
        return True
    return False


_VINTAGE_YEARS = re.compile(r"\b(199[6-9]|200[0-5])\b")


def _flavor_is_vintage(flavor: str) -> bool:
    return bool(_VINTAGE_YEARS.search(flavor or ""))


def _product_is_safe(product_name: str, flavor: str, card_id: str) -> bool:
    """Post-match quality gate. Only allow if we have real confidence
    the JP vintage flavor + EN/JP TCGPlayer product visually match."""
    p = product_name.lower()
    # Japanese-explicit products = always safe (highest signal)
    if "japanese" in p:
        return True
    # Nintendo World Promo (Shadow Lugia) — released globally with
    # identical art.
    if "nintendo world promo" in p:
        return True
    # For bare vintage promo names (no parenthetical variant), trust
    # the match if the card_id itself signals vintage era. JPP-U1996
    # is the 1996-2005 bucket; JPP-U2006 and later are 2006+.
    bare = "(" not in p and "[" not in p
    if bare and (card_id.startswith("JPP-U1996") or _flavor_is_vintage(flavor)):
        return True
    return False

_PAREN_RE = re.compile(r"\s*[\(\[][^\)\]]+[\)\]]\s*")


def _norm_name(name: str) -> str:
    """Strip [tags]/(parens), lowercase, collapse whitespace, remove
    punctuation. Compare on this normalized form."""
    s = _PAREN_RE.sub(" ", name or "")
    s = re.sub(r"[^a-z0-9\s]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    # Handle trainer no.1/no.2/no.3 variants — the TCGPlayer catalog
    # uses "No 1" formatting, ours uses "No.1". Normalize both.
    s = re.sub(r"\bno\s*(\d+)\b", r"no\1", s)
    return s


def _all_tokens_present(needle: str, haystack: str) -> bool:
    """Very loose: every space-separated token of needle appears in
    haystack. Used for name substring match."""
    return all(t in haystack for t in needle.split() if t)


def _keyword_score(product_name: str, flavor: str) -> int:
    """How many distinctive tokens overlap between product name and
    flavor_text. Signals correct variant."""
    p = product_name.lower()
    f = (flavor or "").lower()
    hits = 0
    for tok in _DISTINCTIVE_TOKENS:
        if tok in p and tok in f:
            hits += 1
    return hits


async def _fetch_products(client: httpx.AsyncClient, group_id: int) -> list[dict]:
    r = await client.get(f"{TCGCSV}/{group_id}/products", timeout=45)
    r.raise_for_status()
    return r.json().get("results", [])


async def _load_index(client: httpx.AsyncClient) -> dict[str, list[dict]]:
    """normalized-name -> [{productId, name, imageUrl, url, group_label, prefer}]"""
    index: dict[str, list[dict]] = {}
    for gid, label, prefer in CANDIDATE_GROUPS:
        products = await _fetch_products(client, gid)
        log.info(f"  [{label}] group {gid}: {len(products)} products")
        for p in products:
            raw = p.get("name") or ""
            key = _norm_name(raw)
            if not key:
                continue
            if _is_rejected(raw):
                continue
            index.setdefault(key, []).append({
                "productId":  p.get("productId"),
                "name":       raw,
                "imageUrl":   p.get("imageUrl"),
                "url":        p.get("url"),
                "group":      label,
                "prefer":     prefer,
            })
    log.info(f"  Total unique normalized names indexed: {len(index)}")
    return index


def _pick_match(
    card_id: str,
    card_name: str,
    flavor: str,
    index: dict[str, list[dict]],
) -> tuple[dict, int, str] | None:
    """Return (product_entry, score, reason) or None.

    score interpretation:
      >= 2 : strong (multi-token variant match)
      1    : single-token variant match
      0    : name-only match, single candidate
      -1   : name-only match, multi candidate w/ no variant tokens (skip)
    """
    key = _norm_name(card_name)
    candidates = index.get(key)
    if not candidates:
        # Substring fallback — for cards like "Ancient Mew" listed as
        # "Ancient Mew (Japanese Exclusive Print)". The paren stripping
        # already handles that; the substring path catches oddities
        # like "Pikachu (SNAP Promo)" vs "Pikachu" alone.
        candidates = []
        for norm, entries in index.items():
            if _all_tokens_present(key, norm) and abs(len(norm) - len(key)) < 30:
                candidates.extend(entries)
        if not candidates:
            return None

    scored = []
    for c in candidates:
        s = _keyword_score(c["name"], flavor)
        if c["prefer"]:
            s += 1  # JP-explicit group bonus
        # Bonus for bare vintage names (fewest parens = closest to raw
        # promo name, less likely to be a modern variant).
        paren_penalty = c["name"].count("(") + c["name"].count("[")
        scored.append((s, -paren_penalty, -len(c["name"]), c))
    scored.sort(key=lambda x: (-x[0], -x[1], -x[2]))

    top_score, _, _, top = scored[0]
    if len(scored) > 1:
        second_score = scored[1][0]
        if second_score == top_score and scored[1][1] == scored[0][1]:
            # True tie on both score and paren-penalty — reject
            return None

    # Generic-name guard: for common pokemon names, require score >= 2
    # to avoid mis-mapping (e.g. Pikachu with no flavor overlap could
    # be any of 8+ TCGPlayer Pikachus).
    if _norm_name(card_name) in _GENERIC_NAMES and top_score < 2:
        return None

    if top_score < 0:
        return None
    # Final safety gate: only accept if the product is a JP-explicit
    # entry OR a bare vintage-name match with vintage flavor_text.
    if not _product_is_safe(top["name"], flavor, card_id):
        return None
    return top, top_score, f"score={top_score} group={top['group']}"


async def _download_image(
    client: httpx.AsyncClient, url: str, dest: Path
) -> bool:
    try:
        r = await client.get(url, timeout=25)
    except httpx.HTTPError as e:
        log.warning(f"    ! download error: {e}")
        return False
    if r.status_code != 200 or len(r.content) < 500:
        log.warning(f"    ! HTTP {r.status_code} bytes={len(r.content)}")
        return False
    dest.write_bytes(r.content)
    return True


async def run(dry: bool, only_card: str | None) -> None:
    await init_db()
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    stats = {
        "missing_cards":     0,
        "matched":           0,
        "downloaded":        0,
        "download_failed":   0,
        "already_on_disk":   0,
        "no_match":          0,
        "generic_rejected":  0,
    }

    async with httpx.AsyncClient(
        headers={"User-Agent": "PullList-Backfill/1.0 (+https://pulllist.org)"},
        follow_redirects=True,
    ) as client:
        log.info("Loading TCGPlayer catalog…")
        index = await _load_index(client)

        async with SessionLocal() as db:
            q = """
              SELECT id, name, flavor_text FROM cards
              WHERE set_id LIKE 'JPP-U%' AND language='ja'
                AND image_small IS NULL
            """
            if only_card:
                q += f" AND id = '{only_card}'"
            rows = (await db.execute(text(q))).all()

        stats["missing_cards"] = len(rows)
        log.info(f"Missing images: {len(rows)} JPP-U cards")

        updates: list[tuple[str, str, int, str]] = []
        # (card_id, image_path, tcgplayer_product_id, tcgplayer_url)

        for card_id, name, flavor in rows:
            if card_id in _MANUAL_OVERRIDES:
                pick = (_MANUAL_OVERRIDES[card_id], 99, "manual override")
            else:
                pick = _pick_match(card_id, name or "", flavor or "", index)
            if not pick:
                stats["no_match"] += 1
                continue
            product, score, reason = pick
            stats["matched"] += 1

            dest = MIRROR_DIR / f"{card_id}.jpg"
            local_rel = f"/jp-unn/{card_id}.jpg"

            if dest.exists() and dest.stat().st_size > 0:
                stats["already_on_disk"] += 1
                updates.append((card_id, local_rel, product["productId"], product["url"] or ""))
                log.info(f"  = {card_id:20s} (on disk) -> {product['name']!r} [{reason}]")
                continue

            img_url = product.get("imageUrl")
            if not img_url:
                stats["download_failed"] += 1
                continue

            # bump 200w -> 400w for larger version
            large_url = img_url.replace("_200w.jpg", "_400w.jpg")

            log.info(f"  + {card_id:20s} <- {product['name']!r} [{reason}]")
            if dry:
                continue

            if await _download_image(client, large_url, dest):
                stats["downloaded"] += 1
                updates.append((card_id, local_rel, product["productId"], product["url"] or ""))
            else:
                stats["download_failed"] += 1

        if updates and not dry:
            async with SessionLocal() as db:
                for cid, path, pid, url in updates:
                    await db.execute(
                        text("""UPDATE cards
                                SET image_small=:p, image_large=:p,
                                    tcgplayer_product_id=:pid,
                                    tcgplayer_url=:url,
                                    updated_at=:now
                                WHERE id=:i"""),
                        {"p": path, "pid": pid, "url": url or None,
                         "now": datetime.utcnow(), "i": cid},
                    )
                await db.commit()
            log.info(f"DB rows updated: {len(updates)}")

    log.info("=== Summary ===")
    for k, v in stats.items():
        log.info(f"  {k}: {v}")
    if dry:
        log.info("MODE: DRY-RUN — no writes/downloads")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", help="Single card id to test, e.g. JPP-U1996-113")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run, args.only))


if __name__ == "__main__":
    main()
