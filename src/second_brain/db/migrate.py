from __future__ import annotations

from pathlib import Path
import sqlite3

from second_brain.config import AppConfig, load_config
from second_brain.tools.capabilities import seed_initial_capabilities


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def connect(config: AppConfig) -> sqlite3.Connection:
    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def apply_migrations(config: AppConfig | None = None) -> list[str]:
    config = config or load_config(project_root=PROJECT_ROOT)
    applied: list[str] = []

    with connect(config) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }

        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            # Skip dotfiles such as macOS AppleDouble sidecars (._*.sql), which
            # are not real migrations and are not valid UTF-8 text.
            if migration_path.name.startswith("."):
                continue
            version = migration_path.stem
            if version in existing:
                continue
            conn.executescript(migration_path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)",
                (version,),
            )
            applied.append(version)
        seed_initial_capabilities(conn)

    return applied


def main() -> int:
    applied = apply_migrations()
    if applied:
        print("Applied migrations: " + ", ".join(applied))
    else:
        print("Database already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
