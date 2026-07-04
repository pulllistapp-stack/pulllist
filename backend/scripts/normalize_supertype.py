"""Normalize Card.supertype so 'Pokemon' (ASCII e) collapses into
'Pokémon' (U+00E9). Two different byte strings were living in the same
column because different upstream sources spelled it differently — the
FilterSidebar rendered them as two separate 'Pokémon' chips (screenshot
that started this diff).

Reversible via a follow-up SQL if we ever regret it, but there's no
reason to prefer the ASCII variant — pokemontcg.io, official press,
Bulbapedia, TCGdex all use é.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402


log = logging.getLogger("normalize_supertype")


async def main() -> None:
    async with engine.begin() as conn:
        before = (await conn.execute(text(
            "SELECT supertype, COUNT(*) FROM cards "
            "WHERE supertype ILIKE 'pok%' GROUP BY supertype"
        ))).all()
        log.info("before:")
        for st, cnt in before:
            log.info("  %r  %d", st, cnt)

        result = await conn.execute(text(
            "UPDATE cards SET supertype = 'Pokémon' WHERE supertype = 'Pokemon'"
        ))
        log.info("rows updated: %s", result.rowcount)

        after = (await conn.execute(text(
            "SELECT supertype, COUNT(*) FROM cards "
            "WHERE supertype ILIKE 'pok%' GROUP BY supertype"
        ))).all()
        log.info("after:")
        for st, cnt in after:
            log.info("  %r  %d", st, cnt)


if __name__ == "__main__":
    asyncio.run(main())
