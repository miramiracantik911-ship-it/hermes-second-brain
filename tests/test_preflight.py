from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from second_brain.config import load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.tools.dispatcher import LocalToolDispatcher
from second_brain.tools.preflight import run_phase1b_preflight


class Phase1BPreflightTests(unittest.TestCase):
    def setUp(self):
        self.db_path = ROOT / "data" / "test_preflight.db"
        if self.db_path.exists():
            self.db_path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.db_path) + suffix)
            if sidecar.exists():
                sidecar.unlink()

    def _config(self, gateway_enabled: bool = False):
        env = {
            "APP_ENV": "test",
            "VAULT_PATH": "tests/fixtures/vault",
            "DATABASE_URL": f"sqlite:///{self.db_path}",
            "ATTACHMENT_TEMP_DIR": str(ROOT / "data" / "tmp" / "test-preflight"),
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "test-token",
            "HERMES_GATEWAY_ENABLED": "true" if gateway_enabled else "false",
        }
        if gateway_enabled:
            env["TELEGRAM_BOT_TOKEN"] = "123:fake"
            env["HERMES_GATEWAY_ALLOWED_USER_IDS"] = "111"
        return load_config(env=env, env_file=None, project_root=ROOT)

    def test_preflight_blocks_when_hermes_and_credentials_are_missing(self):
        config = self._config(gateway_enabled=False)
        apply_migrations(config)
        with connect(config) as conn, patch("shutil.which", return_value=None):
            report = run_phase1b_preflight(config, LocalToolDispatcher(conn))

        self.assertFalse(report.ready_for_live_gateway)
        checks = {check.name: check for check in report.checks}
        self.assertFalse(checks["hermes_installed"].ok)
        self.assertFalse(checks["gateway_enabled"].ok)
        self.assertFalse(checks["telegram_token_present"].ok)
        self.assertTrue(checks["health_check_tool"].ok)
        self.assertTrue(checks["future_write_tools_disabled"].ok)

    def test_preflight_can_pass_with_mocked_hermes_and_gateway_config(self):
        config = self._config(gateway_enabled=True)
        apply_migrations(config)
        fake_completed = type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "hermes 0.test", "stderr": ""},
        )()
        with (
            connect(config) as conn,
            patch("shutil.which", return_value="/usr/local/bin/hermes"),
            patch("subprocess.run", return_value=fake_completed),
        ):
            report = run_phase1b_preflight(config, LocalToolDispatcher(conn))

        self.assertTrue(report.ready_for_live_gateway)


if __name__ == "__main__":
    unittest.main()
