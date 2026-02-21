#!/usr/bin/env python3
"""
One-time migration for Cowork long-term memory user IDs.

Problem this fixes:
- Old builds keyed memory by uuid5(api_key), so changing API keys fragmented memory.
- New builds use a stable `memory_user_id` in config.

What this script does:
- Ensures `memory_user_id` exists in config.
- Moves all `kg_triplets.user_id` rows from legacy IDs -> target `memory_user_id`.
- Leaves data untouched by default (dry-run). Use --apply to execute.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

from cowork.config import ConfigManager


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Migrate legacy memoria user IDs to stable memory_user_id")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag, the script runs in dry-run mode.",
    )
    p.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip DB backup before applying migration.",
    )
    return p.parse_args()


def ensure_target_user_id(cfg: ConfigManager) -> str:
    existing = str(cfg.get("memory_user_id", "") or "").strip()
    if existing:
        return existing
    generated = str(uuid.uuid4())
    cfg.set("memory_user_id", generated)
    return generated


def db_path() -> Path:
    return Path.home() / ".cowork" / "memoria" / "memoria.db"


def make_backup(src: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = src.with_name(f"{src.stem}.pre_memory_user_migration_{ts}{src.suffix}")
    shutil.copy2(src, dst)
    return dst


def main() -> int:
    args = parse_args()
    cfg = ConfigManager()
    target_user_id = ensure_target_user_id(cfg)
    path = db_path()

    if not path.exists():
        print(f"[ERROR] Memoria DB not found: {path}")
        return 1

    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row

    try:
        rows = con.execute(
            "SELECT user_id, COUNT(*) AS n FROM kg_triplets GROUP BY user_id ORDER BY n DESC"
        ).fetchall()
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to inspect DB: {e}")
        con.close()
        return 1

    if not rows:
        print("[OK] No triplets found. Nothing to migrate.")
        con.close()
        return 0

    legacy = [(r["user_id"], int(r["n"])) for r in rows if r["user_id"] != target_user_id]
    target_count = next((int(r["n"]) for r in rows if r["user_id"] == target_user_id), 0)
    total_legacy_rows = sum(n for _, n in legacy)

    print(f"Target memory_user_id: {target_user_id}")
    print(f"Current rows under target: {target_count}")
    print(f"Legacy user_id buckets: {len(legacy)}")
    for uid, n in legacy:
        print(f"  - {uid}: {n} row(s)")
    print(f"Rows to migrate: {total_legacy_rows}")

    if not legacy:
        print("[OK] All rows already use target memory_user_id.")
        con.close()
        return 0

    if not args.apply:
        print("\n[DRY-RUN] No changes written. Re-run with --apply to execute.")
        con.close()
        return 0

    if not args.no_backup:
        try:
            backup_path = make_backup(path)
            print(f"[BACKUP] Created: {backup_path}")
        except Exception as e:
            print(f"[ERROR] Could not create backup: {e}")
            con.close()
            return 1

    try:
        with con:
            for legacy_user_id, _n in legacy:
                con.execute(
                    "UPDATE kg_triplets SET user_id = ? WHERE user_id = ?",
                    (target_user_id, legacy_user_id),
                )
    except sqlite3.Error as e:
        print(f"[ERROR] Migration failed: {e}")
        con.close()
        return 1

    final_count = con.execute(
        "SELECT COUNT(*) AS n FROM kg_triplets WHERE user_id = ?",
        (target_user_id,),
    ).fetchone()["n"]
    con.close()

    print(f"[OK] Migration complete. Target now has {final_count} row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

