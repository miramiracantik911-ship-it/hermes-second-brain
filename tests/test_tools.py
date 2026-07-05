from pathlib import Path
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from second_brain.config import load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.tools.capabilities import get_capability, require_enabled, CapabilityError
from second_brain.tools.dispatcher import LocalToolDispatcher


class ToolCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.db_path = ROOT / "data" / "test_tools.db"
        if self.db_path.exists():
            self.db_path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.db_path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        env = {
            "APP_ENV": "test",
            "VAULT_PATH": "tests/fixtures/vault",
            "DATABASE_URL": f"sqlite:///{self.db_path}",
            "ATTACHMENT_TEMP_DIR": str(ROOT / "data" / "tmp" / "test-tools"),
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "test-token",
        }
        self.config = load_config(env=env, env_file=None, project_root=ROOT)
        apply_migrations(self.config)
        self.conn = connect(self.config)

    def tearDown(self):
        self.conn.close()

    def test_initial_capabilities_are_seeded(self):
        health = require_enabled(self.conn, "health_check")
        capture = get_capability(self.conn, "capture_note")
        approve = get_capability(self.conn, "approve_media")

        self.assertEqual(health.risk_level, "L0")
        self.assertTrue(health.enabled)
        self.assertTrue(capture.enabled)  # enabled from Phase 2
        self.assertFalse(approve.enabled)  # future tool, still disabled

    def test_disabled_capability_is_rejected(self):
        with self.assertRaisesRegex(CapabilityError, "disabled"):
            require_enabled(self.conn, "approve_media")

    def test_health_check_dispatch_records_audit(self):
        dispatcher = LocalToolDispatcher(self.conn)

        result = dispatcher.call("health_check", user_id="telegram:123")

        self.assertTrue(result.ok)
        self.assertEqual(result.result["status"], "ok")
        self.assertIsNotNone(result.operation_id)

        row = self.conn.execute(
            "SELECT tool_name, risk_level, status FROM operations WHERE id = ?",
            (result.operation_id,),
        ).fetchone()
        self.assertEqual(row["tool_name"], "health_check")
        self.assertEqual(row["risk_level"], "L0")
        self.assertEqual(row["status"], "success")

    def test_disabled_tool_call_records_rejection(self):
        dispatcher = LocalToolDispatcher(self.conn)

        result = dispatcher.call("approve_media", user_id="telegram:123")

        self.assertFalse(result.ok)
        self.assertEqual(result.error["code"], "CAPABILITY_REJECTED")
        row = self.conn.execute(
            "SELECT tool_name, status FROM operations WHERE id = ?",
            (result.operation_id,),
        ).fetchone()
        self.assertEqual(row["tool_name"], "approve_media")
        self.assertEqual(row["status"], "rejected:CAPABILITY_REJECTED")


if __name__ == "__main__":
    unittest.main()
