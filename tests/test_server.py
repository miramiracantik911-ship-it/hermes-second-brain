from pathlib import Path
from http.client import HTTPConnection
import json
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from second_brain.config import ConfigError, load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.server import (
    authorize,
    build_server,
    handle_tool_call,
    list_enabled_tools,
    resolve_bind,
)


class ServerHandlerTests(unittest.TestCase):
    def setUp(self):
        self.db_path = ROOT / "data" / "test_server.db"
        if self.db_path.exists():
            self.db_path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.db_path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        self.config = self._config()
        apply_migrations(self.config)

    def _config(self, core_url: str = "http://127.0.0.1:8787"):
        env = {
            "APP_ENV": "test",
            "VAULT_PATH": "tests/fixtures/vault",
            "DATABASE_URL": f"sqlite:///{self.db_path}",
            "ATTACHMENT_TEMP_DIR": str(ROOT / "data" / "tmp" / "test-server"),
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "test-token",
            "SECOND_BRAIN_CORE_URL": core_url,
        }
        return load_config(env=env, env_file=None, project_root=ROOT)

    def _bearer(self) -> str:
        return f"Bearer {self.config.hermes_internal_tool_token}"

    def test_authorize_rejects_missing_and_wrong_token(self):
        self.assertFalse(authorize(self.config, None))
        self.assertFalse(authorize(self.config, "Bearer wrong"))
        self.assertTrue(authorize(self.config, self._bearer()))

    def test_list_enabled_tools_excludes_disabled(self):
        with connect(self.config) as conn:
            ids = {tool["id"] for tool in list_enabled_tools(conn)}
        self.assertEqual(
            ids,
            {
                "health_check",
                "job_status",
                "sync_status",
                "capture_note",
                "undo_operation",
                "search_vault",
                "get_note",
                "update_note",
                "move_note",
            },
        )
        # approve_media (Phase 6) remains disabled.
        self.assertNotIn("approve_media", ids)

    def test_handle_tool_call_requires_token(self):
        with connect(self.config) as conn:
            response = handle_tool_call(
                conn, self.config, json.dumps({"tool": "health_check"}), None
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.body["error"]["code"], "UNAUTHORIZED")

    def test_handle_tool_call_rejects_bad_json(self):
        with connect(self.config) as conn:
            response = handle_tool_call(conn, self.config, "{not-json", self._bearer())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.body["error"]["code"], "BAD_REQUEST")

    def test_handle_tool_call_requires_tool_field(self):
        with connect(self.config) as conn:
            response = handle_tool_call(conn, self.config, "{}", self._bearer())
        self.assertEqual(response.status_code, 400)

    def test_handle_tool_call_runs_health_check(self):
        with connect(self.config) as conn:
            response = handle_tool_call(
                conn, self.config, json.dumps({"tool": "health_check"}), self._bearer()
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.body["ok"])
        self.assertEqual(response.body["result"]["service"], "second-brain-core")
        self.assertTrue(response.body["operation_id"].startswith("op_"))

    def test_handle_tool_call_rejects_disabled_tool(self):
        with connect(self.config) as conn:
            response = handle_tool_call(
                conn, self.config, json.dumps({"tool": "approve_media"}), self._bearer()
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.body["ok"])
        self.assertEqual(response.body["error"]["code"], "CAPABILITY_REJECTED")

    def test_resolve_bind_refuses_non_loopback(self):
        config = self._config(core_url="http://0.0.0.0:8787")
        with self.assertRaises(ConfigError):
            resolve_bind(config)


class ServerHttpSmokeTests(unittest.TestCase):
    def setUp(self):
        self.db_path = ROOT / "data" / "test_server_http.db"
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
            "ATTACHMENT_TEMP_DIR": str(ROOT / "data" / "tmp" / "test-server-http"),
            "LOG_LEVEL": "INFO",
            "HERMES_INTERNAL_TOOL_TOKEN": "test-token",
            # Port 0 => OS assigns an ephemeral free port.
            "SECOND_BRAIN_CORE_URL": "http://127.0.0.1:0",
        }
        self.config = load_config(env=env, env_file=None, project_root=ROOT)
        self.server = build_server(self.config)
        self.host, self.port = self.server.server_address[:2]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _request(self, method, path, body=None, token=None):
        conn = HTTPConnection(self.host, self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        conn.close()
        return resp.status, data

    def test_health_is_public(self):
        status, data = self._request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_tools_requires_token(self):
        status, data = self._request("GET", "/tools")
        self.assertEqual(status, 401)
        self.assertEqual(data["error"]["code"], "UNAUTHORIZED")

    def test_tool_call_health_check_over_http(self):
        status, data = self._request(
            "POST", "/tools/call", body=json.dumps({"tool": "health_check"}),
            token="test-token",
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["result"]["service"], "second-brain-core")

    def test_tool_call_disabled_tool_over_http(self):
        status, data = self._request(
            "POST", "/tools/call", body=json.dumps({"tool": "approve_media"}),
            token="test-token",
        )
        self.assertEqual(status, 200)
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"]["code"], "CAPABILITY_REJECTED")

    def test_unknown_route_is_404(self):
        status, _ = self._request("GET", "/nope")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
