"""Copy every table from one Postgres to another via SQLAlchemy.

Built for the Neon → Render Postgres cutover but generic — anything
that matches our `app.models` schema will migrate cleanly.

Strategy:
    1. Create schema on TARGET via `Base.metadata.create_all` — the
       SQLAlchemy models ARE the schema of record.
    2. Copy every table in FK-dependency order (`Base.metadata.sorted_tables`)
       so foreign keys never dangle mid-run.
    3. Batch inserts at 500 rows / round-trip so we don't OOM the
       source read or the target write.

Usage:
    export SOURCE_URL=postgresql+asyncpg://neondb_owner:...@neon.tech/neondb?ssl=require
    export TARGET_URL=postgresql+asyncpg://user:pw@dpg-xxx.oregon-postgres.render.com/dbname?ssl=require
    python -m scripts.migrate_pg_to_pg --dry-run          # count rows, don't write
    python -m scripts.migrate_pg_to_pg                    # copy into an empty target
    python -m scripts.migrate_pg_to_pg --reset            # drop_all + create_all on target first

Safety:
    * `--reset` requires an explicit prompt confirmation. Refuses on
      any URL that contains "neon.tech" — you cannot accidentally reset
      the SOURCE.
    * Aborts with a clear error if TARGET already has non-empty tables
      unless `--reset` or `--force-append` is passed.
    * SOURCE reads are strictly SELECT; the script never mutates the
      source DB.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base
from app.models import *  # noqa: F401,F403 — trigger every Table's registration

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("migrate")

BATCH_SIZE = 500


def _sanitize_url(raw: str) -> str:
    """Strip password for log lines."""
    if "://" not in raw or "@" not in raw:
        return raw
    proto, rest = raw.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        creds = f"{user}:***"
    return f"{proto}://{creds}@{host}"


async def _table_counts(engine, tables) -> dict[str, int]:
    counts: dict[str, int] = {}
    async with engine.connect() as conn:
        for t in tables:
            n = (await conn.execute(select(func.count()).select_from(t))).scalar_one()
            counts[t.name] = int(n)
    return counts


async def _copy_table(source_engine, target_engine, table) -> int:
    """Stream rows from source, batch-insert into target. Returns
    total rows copied."""
    total = 0
    async with source_engine.connect() as src:
        result = await src.stream(select(table))
        buffer: list[dict] = []
        async for row in result.mappings():
            buffer.append(dict(row))
            if len(buffer) >= BATCH_SIZE:
                await _flush(target_engine, table, buffer)
                total += len(buffer)
                log.info(f"  {table.name}: {total} rows copied")
                buffer = []
        if buffer:
            await _flush(target_engine, table, buffer)
            total += len(buffer)
    return total


async def _flush(target_engine, table, rows: list[dict]) -> None:
    async with target_engine.begin() as tgt:
        await tgt.execute(table.insert(), rows)


async def main(
    dry_run: bool, reset: bool, force_append: bool, only: list[str] | None
) -> None:
    source_url = os.environ.get("SOURCE_URL")
    target_url = os.environ.get("TARGET_URL")
    if not source_url or not target_url:
        raise SystemExit("SOURCE_URL and TARGET_URL env vars are required")

    log.info(f"SOURCE = {_sanitize_url(source_url)}")
    log.info(f"TARGET = {_sanitize_url(target_url)}")

    if reset and "neon.tech" in target_url:
        raise SystemExit(
            "REFUSING --reset: TARGET_URL points at neon.tech. That is "
            "almost certainly the SOURCE. Double-check your env vars."
        )

    source_engine = create_async_engine(source_url, echo=False)
    target_engine = create_async_engine(target_url, echo=False)

    tables = list(Base.metadata.sorted_tables)  # FK-dependency order
    if only:
        keep = set(only)
        tables = [t for t in tables if t.name in keep]
        log.info(f"restricted to {len(tables)} tables: {[t.name for t in tables]}")

    # ── schema ────────────────────────────────────────────────
    if reset:
        answer = input(
            f"About to DROP + RECREATE every table on {_sanitize_url(target_url)}.\n"
            "Type 'yes' to proceed: "
        )
        if answer.strip().lower() != "yes":
            raise SystemExit("Aborted at reset prompt.")
        log.warning("dropping every table on TARGET")
        if not dry_run:
            async with target_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)

    if not dry_run:
        log.info("creating schema on TARGET (idempotent)")
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # ── safety: refuse to overlay onto populated tables ────────
    tgt_counts = await _table_counts(target_engine, tables)
    populated = {name: n for name, n in tgt_counts.items() if n > 0}
    if populated and not force_append:
        log.error(
            "TARGET tables already have rows: %s. Pass --reset to wipe "
            "or --force-append to duplicate on top (may violate PK).",
            populated,
        )
        raise SystemExit(1)

    src_counts = await _table_counts(source_engine, tables)
    total_source = sum(src_counts.values())
    log.info(f"SOURCE row total across {len(tables)} tables: {total_source}")
    for name, n in src_counts.items():
        log.info(f"  {name}: {n}")

    if dry_run:
        log.info("--dry-run: no writes performed")
        return

    # ── copy ──────────────────────────────────────────────────
    grand_total = 0
    for t in tables:
        n = src_counts[t.name]
        if n == 0:
            log.info(f"[{t.name}] empty on source, skipping")
            continue
        log.info(f"[{t.name}] copying {n} rows...")
        written = await _copy_table(source_engine, target_engine, t)
        if written != n:
            log.warning(
                f"[{t.name}] copied {written} rows but source reported {n}"
            )
        grand_total += written

    # ── verify ────────────────────────────────────────────────
    log.info("=== verification ===")
    tgt_after = await _table_counts(target_engine, tables)
    mismatched: list[str] = []
    for name in src_counts:
        s, t = src_counts[name], tgt_after[name]
        marker = "OK  " if s == t else "MISS"
        log.info(f"  {marker} {name}: source={s} target={t}")
        if s != t:
            mismatched.append(name)

    if mismatched:
        log.error(f"MISMATCH on {len(mismatched)} tables: {mismatched}")
        raise SystemExit(2)

    log.info(f"=== copied {grand_total} rows total, all counts match ===")


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows on SOURCE + TARGET, don't write.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop_all + create_all on TARGET before copying (interactive).",
    )
    parser.add_argument(
        "--force-append",
        action="store_true",
        help="Continue even if TARGET has existing rows. May violate PK.",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        help="Limit to specific tables (space-separated names).",
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            dry_run=args.dry_run,
            reset=args.reset,
            force_append=args.force_append,
            only=args.only,
        )
    )


if __name__ == "__main__":
    cli()
