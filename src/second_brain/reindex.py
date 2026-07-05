#!/usr/bin/env python3
"""Rebuild the FTS5 search index over the entire vault.

Run once after deployment, and any time you want search to reflect notes that
were added or edited outside of capture (e.g. directly in Obsidian, or synced
from another device). This is a full rebuild; it is safe to run repeatedly.

    PYTHONPATH=src python -m second_brain.reindex
"""

from __future__ import annotations

from pathlib import Path

from second_brain.config import load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.vault.search import rebuild_index

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    config = load_config(project_root=PROJECT_ROOT)
    apply_migrations(config)
    conn = connect(config)
    try:
        count = rebuild_index(conn, config.vault_path)
    finally:
        conn.close()
    print(f"Indexed {count} notes from {config.vault_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
