"""Rename PullList EN image backup folders to include set names.

Before: PullList_ImageBackup/en/base1/
After:  PullList_ImageBackup/en/base1 (Base Set)/

Idempotent — folders already containing " (" are skipped so re-runs
are a no-op. Windows-illegal chars (< > : " / \\ | ? *) are stripped
from set names.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DEBUG", "false")

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Set  # noqa: E402


_ILLEGAL_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(name: str) -> str:
    """Windows-safe folder name: strip illegal chars, collapse spaces,
    trim trailing dots (Explorer strips them anyway which breaks
    open-in-explorer)."""
    cleaned = _ILLEGAL_RE.sub("", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.rstrip(". ")


async def main(root: Path, dry_run: bool) -> None:
    en_root = root / "en"
    if not en_root.is_dir():
        print(f"Not a directory: {en_root}")
        return

    async with SessionLocal() as db:
        sets = (
            await db.execute(
                select(Set.id, Set.name).where(Set.language == "en")
            )
        ).all()
    id_to_name = {sid: name for sid, name in sets if name}
    print(f"Loaded {len(id_to_name)} EN set names from DB.")

    renamed = 0
    already = 0
    missing_meta = 0
    skipped_special = 0

    for folder in sorted(en_root.iterdir()):
        if not folder.is_dir():
            continue
        # Skip internal reserved (_failures.jsonl parent, etc.)
        if folder.name.startswith("_"):
            skipped_special += 1
            continue
        # Already renamed?
        if " (" in folder.name and folder.name.endswith(")"):
            already += 1
            continue

        sid = folder.name
        set_name = id_to_name.get(sid)
        if not set_name:
            print(f"  no DB metadata for id={sid!r} — leaving as-is")
            missing_meta += 1
            continue

        new_name = f"{sid} ({_sanitize(set_name)})"
        new_path = folder.parent / new_name
        if new_path.exists():
            print(f"  target exists, skipping: {new_name}")
            already += 1
            continue

        print(f"  {sid}  →  {new_name}")
        if not dry_run:
            folder.rename(new_path)
        renamed += 1

    print()
    print(f"=== summary ===")
    print(f"  renamed:         {renamed}")
    print(f"  already renamed: {already}")
    print(f"  missing meta:    {missing_meta}")
    print(f"  reserved skip:   {skipped_special}")
    print(f"  dry_run:         {dry_run}")


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dest",
        default=r"C:\Users\Jinwon\Desktop\PullList_ImageBackup",
        help="Backup root (folder that contains the 'en/' subdir).",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    asyncio.run(main(Path(args.dest), args.dry_run))


if __name__ == "__main__":
    cli()
