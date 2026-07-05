"""Remap generic 'Japanese' / 'Promos' series labels to proper era buckets.

When we bulk-imported JP sets from Limitless / TCGCSV / manual seed
scripts, ~144 sets landed with `series='Japanese'` — a catch-all that
lumps BW mainline, XY concept packs, SM sub-sets, SV starter decks, and
generic deck products together under one 144-count chip.

Same story for `series='Promos'` (23 sets, mostly JPP-U year buckets
and the vending stubs) — should live under `プロモカード` alongside the
17 already-tagged legacy promos.

This script rewrites `series` for those sets based on the set_id
prefix so they land in the proper JP-era chip:

    BW*  → ブラック＆ホワイト     (2010-2013)
    HGSS related (HS*) → ブラック＆ホワイト
    BK*, PBG, PPD, BGS, BTV, KK, KLD, SC, CS, MG, DS → BW era decks
    XY*, XYA-H → XY
    XY11* / EBB / SNPr / SNPo → XY BREAK
    HXY, MBD, MBG, MDB, MMB*, MA, GBR, X30, Y30 → XY era decks
    SM*, SMA-N, SMP*, MC, MP, SI, SN, SH → サン＆ムーン
    SA*, SB, SCr, SCd, SC2, SD, SEF, SEK, SF, SGG, SGI, SJ, SK,
    SLD, SLL, SP*, SPD, SPZ, SZD, WCS → 剣と盾
    SV*, SVA-P, WAK → ポケモンカードゲーム スカーレット＆バイオレット

    Promos (JPP-U*, JPP-VM*) → プロモカード
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.database import SessionLocal, init_db

log = logging.getLogger("remap_jp_generic_series")

BW_ERA  = "ブラック＆ホワイト"
XY_ERA  = "XY"
XY_BR   = "XY BREAK"
SM_ERA  = "サン＆ムーン"
SS_ERA  = "剣と盾"
SV_ERA  = "ポケモンカードゲーム スカーレット＆バイオレット"
PROMO   = "プロモカード"

# id prefix → target series. Longest prefix wins so SVI matches SVI
# before SV, XYA before XY, etc. Specific set_id overrides handled
# below.
_PREFIX_MAP: dict[str, str] = {
    # ── BW era ─────────────────────────────
    "BW":    BW_ERA,
    "BK":    BW_ERA,   # BK* deck products (Black Kyurem-EX etc.)
    "HS":    BW_ERA,   # HS/HSP/HSZ Starting Set BW
    "PBG":   BW_ERA,   # Team Plasma Battle Gift Set
    "PPD":   BW_ERA,   # Team Plasma Powered Deck
    "BGS":   BW_ERA,   # Thundurus VS Tornadus Battle Gift Set
    "BTV":   BW_ERA,   # Victini Deck
    "KK":    BW_ERA,   # Blastoise & Kyurem-EX Deck
    "KLD":   BW_ERA,   # Keldeo Half Deck
    "SC":    BW_ERA,   # Shiny Collection (BW era subset)
    "CS":    BW_ERA,   # Snivy/Tepig/Oshawott Collection Sheet
    "MG":    BW_ERA,   # Mewtwo/Genesect Half Decks
    "DS":    BW_ERA,   # Dragon Selection

    # ── XY BREAK era (later XY) ────────────
    "XY11":  XY_BR,    # Heat Burst Fighter / Cruel Traitor
    "EBB":   XY_BR,    # EX Battle Boost
    "SNP":   XY_BR,    # SNPr/SNPo BREAK Evolution Pack

    # ── XY era ─────────────────────────────
    "XY":    XY_ERA,   # Fallback for XY*, XY1x, XY1y, XY5g/t, XY8r, XYA-H
    "HXY":   XY_ERA,   # Starting Set XY
    "MBD":   XY_ERA,   # MEGA Starter Diancie
    "MBG":   XY_ERA,   # MEGA Starter Gengar
    "MDB":   XY_ERA,   # Master Deck Build Box EX
    "MMB":   XY_ERA,   # Master Deck Build Box MEGA Power/Speed
    "MA":    XY_ERA,   # Premium Trainer Box MEGA
    "GBR":   XY_ERA,   # Garchomp Half Deck
    "X30":   XY_ERA,   # Xerneas Half Deck
    "Y30":   XY_ERA,   # Yveltal Half Deck

    # ── SM era ─────────────────────────────
    "SM":    SM_ERA,   # SM1p-SM11, SMA-SMN, SMP*
    "MC":    SM_ERA,   # Starter Decks 100 Battle Collection
    "MP":    SM_ERA,   # Starter Decks 100 CoroCiao ver.
    "SI":    SM_ERA,   # Starter Decks 100
    "SN":    SM_ERA,   # Starter Deck 100 CoroCoro
    "SH":    SM_ERA,   # Family Pokemon Card Game

    # ── Sword & Shield era ─────────────────
    "SA":    SS_ERA,   # V Starter Sets
    "SB":    SS_ERA,   # Premium Trainer Box Sword & Shield
    "SC2":   SS_ERA,   # Charizard VMAX Starter 2
    "SCd":   SS_ERA,   # Grimmsnarl VMAX Starter
    "SCr":   SS_ERA,   # Charizard VMAX Starter
    "SD":    SS_ERA,   # V Starter Decks
    "SEF":   SS_ERA,   # Venusaur VMAX Starter
    "SEK":   SS_ERA,   # Blastoise VMAX Starter
    "SF":    SS_ERA,   # Premium Trainer Box Single/Rapid Strike
    "SGG":   SS_ERA,   # High-Class Deck Gengar VMAX
    "SGI":   SS_ERA,   # High-Class Deck Inteleon VMAX
    "SJ":    SS_ERA,   # Special Deck Set Zacian & Zamazenta vs Eternatus
    "SK":    SS_ERA,   # VSTAR Premium Trainer Box
    "SLD":   SS_ERA,   # Starter Set Darkrai VSTAR
    "SLL":   SS_ERA,   # Starter Set Lucario VSTAR
    "SO":    SS_ERA,   # Special Deck Set Charizard VSTAR vs Rayquaza VMAX
    "SP":    SS_ERA,   # SP1-SP6 various VMAX/VSTAR Special Sets
    "SPD":   SS_ERA,   # VSTAR&VMAX High-Class Deck Deoxys
    "SPZ":   SS_ERA,   # VSTAR&VMAX High-Class Deck Zeraora
    "SZD":   SS_ERA,   # Hydreigon Half Deck
    "WCS":   SS_ERA,   # World Championships 2023 Yokohama Deck

    # ── SV era ─────────────────────────────
    "SV":    SV_ERA,   # SV1a, SVA-N, SVO*, SVP*
    "WAK":   SV_ERA,   # Everyone's Exciting Battle (SV era)
}

# Explicit set_id overrides (win over prefix match)
_ID_OVERRIDE: dict[str, str] = {
    "20th": SS_ERA,   # Pokemon Card Game Starter Pack (SwSh 20th anniv)
    "XY":   XY_ERA,   # Best of XY (id is literally "XY")
    "SP1":  SS_ERA, "SP2": SS_ERA, "SP3": SS_ERA,
    "SP4":  SS_ERA, "SP5": SS_ERA, "SP6": SS_ERA,
}


def _target_series(set_id: str) -> str | None:
    if set_id in _ID_OVERRIDE:
        return _ID_OVERRIDE[set_id]
    # Longest-prefix match
    for k in sorted(_PREFIX_MAP.keys(), key=len, reverse=True):
        if set_id.startswith(k):
            return _PREFIX_MAP[k]
    return None


async def run(dry: bool) -> None:
    await init_db()

    async with SessionLocal() as db:
        rows = (await db.execute(text("""
            SELECT id, name, series FROM sets
            WHERE language='ja' AND series IN ('Japanese', 'Promos')
        """))).all()
    log.info(f"candidates: {len(rows)} sets under 'Japanese' or 'Promos'")

    updates: list[tuple[str, str, str]] = []
    unresolved: list[tuple[str, str]] = []

    for row in rows:
        # 'Promos' → プロモカード for all (JPP-U* and JPP-VM* both belong)
        if row.series == "Promos":
            updates.append((row.id, row.series, PROMO))
            continue
        # 'Japanese' → prefix lookup
        target = _target_series(row.id)
        if target is None:
            unresolved.append((row.id, row.name))
        else:
            updates.append((row.id, row.series, target))

    from collections import Counter
    dist = Counter(t for _, _, t in updates)
    log.info("=== proposed remap ===")
    for series, n in dist.most_common():
        log.info(f"  {n:4d} → {series}")
    log.info(f"  unresolved: {len(unresolved)}")
    for sid, name in unresolved:
        safe = name.encode("ascii", "replace").decode("ascii")[:40]
        log.info(f"    {sid:12s}  {safe}")

    if updates and not dry:
        async with SessionLocal() as db:
            for sid, _old, new in updates:
                await db.execute(
                    text("UPDATE sets SET series=:s, updated_at=NOW() WHERE id=:i"),
                    {"s": new, "i": sid},
                )
            await db.commit()
        log.info(f"applied {len(updates)} series remaps")
    if dry:
        log.info("MODE: DRY-RUN — no writes")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
