from pathlib import Path
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from second_brain.config import load_config
from second_brain.db.migrate import apply_migrations


class MigrationTests(unittest.TestCase):
    def test_initial_migration_creates_expected_tables(self):
        db_path = ROOT / "data" / "test_phase0.db"
        if db_path.exists():
            db_path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(db_path) + suffix)
            if sidecar.exists():
                sidecar.unlink()

        env = {
            "APP_ENV": "test",
            "VAULT_PATH": "tests/fixtures/vault",
            "DATABASE_URL": f"sqlite:///{db_path}",
            "ATTACHMENT_TEMP_DIR": str(ROOT / "data" / "tmp" / "test-attachments"),
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "test-token",
        }
        config = load_config(env=env, env_file=None, project_root=ROOT)

        applied = apply_migrations(config)

        self.assertIn("0001_initial", applied)
        with sqlite3.connect(db_path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')"
                ).fetchall()
            }
        self.assertIn("jobs", tables)
        self.assertIn("notes", tables)
        self.assertIn("capabilities", tables)
        self.assertIn("search_index", tables)

        with sqlite3.connect(db_path) as conn:
            health = conn.execute(
                "SELECT enabled FROM capabilities WHERE id = 'health_check'"
            ).fetchone()
            capture = conn.execute(
                "SELECT enabled FROM capabilities WHERE id = 'capture_note'"
            ).fetchone()
            approve = conn.execute(
                "SELECT enabled FROM capabilities WHERE id = 'approve_media'"
            ).fetchone()
        self.assertEqual(health[0], 1)
        self.assertEqual(capture[0], 1)  # enabled from Phase 2
        self.assertEqual(approve[0], 0)  # future tool, still disabled


if __name__ == "__main__":
    unittest.main()
