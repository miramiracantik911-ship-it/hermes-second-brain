from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import hmac
import json
import sqlite3

from second_brain.config import AppConfig, ConfigError, load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.tools.dispatcher import LocalToolDispatcher

PROJECT_ROOT = Path(__file__).resolve().parents[2]

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class CoreResponse:
    status_code: int
    body: dict[str, Any]


def _error(
    code: str,
    message: str,
    *,
    retryable: bool = False,
    status_code: int = 400,
) -> CoreResponse:
    return CoreResponse(
        status_code=status_code,
        body={"error": {"code": code, "message": message, "retryable": retryable}},
    )


def authorize(config: AppConfig, auth_header: str | None) -> bool:
    """Constant-time check of the internal bearer token."""
    if not auth_header:
        return False
    expected = f"Bearer {config.hermes_internal_tool_token}"
    return hmac.compare_digest(auth_header.strip(), expected)


def list_enabled_tools(conn: sqlite3.Connection) -> list[dict[str, str]]:
    rows = conn.execute(
        "SELECT id, domain, risk_level FROM capabilities WHERE enabled = 1 ORDER BY id"
    ).fetchall()
    return [
        {"id": row["id"], "domain": row["domain"], "risk_level": row["risk_level"]}
        for row in rows
    ]


def handle_tool_call(
    conn: sqlite3.Connection,
    config: AppConfig,
    raw_body: str,
    auth_header: str | None,
) -> CoreResponse:
    """Pure handler for POST /tools/call. Returns the ToolResult shape on dispatch."""
    if not authorize(config, auth_header):
        return _error(
            "UNAUTHORIZED",
            "Missing or invalid internal tool token.",
            status_code=401,
        )

    try:
        data = json.loads(raw_body or "{}")
    except json.JSONDecodeError:
        return _error("BAD_REQUEST", "Request body must be valid JSON.")

    if not isinstance(data, dict):
        return _error("BAD_REQUEST", "Request body must be a JSON object.")

    tool = data.get("tool")
    if not tool or not isinstance(tool, str):
        return _error("BAD_REQUEST", "Field 'tool' is required and must be a string.")

    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        return _error("BAD_REQUEST", "Field 'payload' must be an object.")

    user_id = str(data.get("user_id") or "hermes:gateway")

    result = LocalToolDispatcher(conn, config).call(tool, payload, user_id=user_id)
    body = {
        "tool": result.tool,
        "ok": result.ok,
        "result": result.result,
        "error": result.error,
        "operation_id": result.operation_id,
    }
    # Tool-level failures (disabled/unknown capability) are still HTTP 200;
    # the ok/error fields carry the dispatch outcome per the tool contract.
    return CoreResponse(status_code=200, body=body)


def resolve_bind(config: AppConfig) -> tuple[str, int]:
    parsed = urlparse(config.second_brain_core_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port if parsed.port is not None else 8787
    if host not in LOOPBACK_HOSTS:
        raise ConfigError(
            f"Refusing to bind non-loopback host '{host}'. "
            "Phase 1 keeps the Second Brain Core API local-only."
        )
    return host, port


class _Handler(BaseHTTPRequestHandler):
    config: AppConfig  # bound per server via a subclass

    server_version = "second-brain-core/1B"

    def _send(self, response: CoreResponse) -> None:
        payload = json.dumps(response.body).encode("utf-8")
        self.send_response(response.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        path = urlparse(self.path).path
        if path == "/health":
            self._send(
                CoreResponse(
                    200,
                    {"status": "ok", "service": "second-brain-core", "phase": "1B"},
                )
            )
            return
        if path == "/tools":
            if not authorize(self.config, self.headers.get("Authorization")):
                self._send(
                    _error(
                        "UNAUTHORIZED",
                        "Missing or invalid internal tool token.",
                        status_code=401,
                    )
                )
                return
            conn = connect(self.config)
            try:
                tools = list_enabled_tools(conn)
            finally:
                conn.close()
            self._send(CoreResponse(200, {"tools": tools}))
            return
        self._send(_error("NOT_FOUND", "Unknown route.", status_code=404))

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        path = urlparse(self.path).path
        if path != "/tools/call":
            self._send(_error("NOT_FOUND", "Unknown route.", status_code=404))
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        conn = connect(self.config)
        try:
            response = handle_tool_call(
                conn, self.config, raw, self.headers.get("Authorization")
            )
        finally:
            conn.close()
        self._send(response)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Silence default stderr access logging to avoid leaking request data.
        return


def build_server(config: AppConfig) -> HTTPServer:
    apply_migrations(config)
    host, port = resolve_bind(config)
    handler = type("BoundHandler", (_Handler,), {"config": config})
    return HTTPServer((host, port), handler)


def serve(config: AppConfig | None = None) -> int:
    config = config or load_config(project_root=PROJECT_ROOT)
    server = build_server(config)
    host, port = server.server_address[0], server.server_address[1]
    print(f"Second Brain Core listening on http://{host}:{port}")
    print("Routes: GET /health, GET /tools, POST /tools/call")
    print("Auth: Authorization: Bearer <HERMES_INTERNAL_TOOL_TOKEN> (except /health)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0


def main() -> int:
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
