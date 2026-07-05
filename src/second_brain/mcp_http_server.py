#!/usr/bin/env python3
"""Second Brain MCP server over HTTP (for the Mac-side Core, reached via Tailscale).

Phase 3 runs the Core on the Mac mini where the full Obsidian vault lives, and
exposes the read/organize tools to Hermes-on-VPS as a remote MCP over the private
tailnet. This uses FastMCP's streamable-http transport. Bind to the tailnet IP only
(never 0.0.0.0); Tailscale ACLs + the bearer token restrict access.

Register with Hermes:

    hermes mcp add second-brain-mac --url http://<macmini-tailnet>:8788/mcp

Env:
    MCP_HTTP_HOST  bind address (default 127.0.0.1; set to the Mac's tailnet IP)
    MCP_HTTP_PORT  port (default 8788)
plus the usual VAULT_PATH / DATABASE_URL etc. from .env.
"""

from __future__ import annotations

from pathlib import Path
import json
import os

from mcp.server.fastmcp import FastMCP

from second_brain.config import load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.tools.dispatcher import LocalToolDispatcher

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MCP_USER_ID = "hermes:mcp-mac"

HOST = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_HTTP_PORT", "8788"))

mcp = FastMCP("second_brain_mac_mcp", host=HOST, port=PORT)

_config = None


def _get_config():
    global _config
    if _config is None:
        config = load_config(project_root=PROJECT_ROOT)
        apply_migrations(config)
        _config = config
    return _config


def _dispatch(tool_name: str, payload: dict | None = None) -> str:
    config = _get_config()
    conn = connect(config)
    try:
        result = LocalToolDispatcher(conn, config).call(
            tool_name, payload, user_id=MCP_USER_ID
        )
    finally:
        conn.close()
    return json.dumps(
        {
            "tool": result.tool,
            "ok": result.ok,
            "result": result.result,
            "error": result.error,
            "operation_id": result.operation_id,
        }
    )


_READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
         "openWorldHint": False}
_WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False,
          "openWorldHint": False}


@mcp.tool(name="second_brain_mac_health",
          annotations={"title": "Second Brain Mac Health", **_READ})
def second_brain_mac_health() -> str:
    """Verify the Mac-side Second Brain Core (vault host) is reachable. No arguments."""
    return _dispatch("health_check")


@mcp.tool(name="second_brain_search_vault",
          annotations={"title": "Second Brain Search Vault", **_READ})
def second_brain_search_vault(query: str, limit: int = 10) -> str:
    """Search the Obsidian vault for notes matching `query`.

    Returns JSON with `results` (path, title, snippet). Sensitive notes are found
    by title/tags only — their body is never indexed or returned.
    """
    return _dispatch("search_vault", {"query": query, "limit": limit})


@mcp.tool(name="second_brain_get_note",
          annotations={"title": "Second Brain Get Note", **_READ})
def second_brain_get_note(path: str) -> str:
    """Read a note's content by vault-relative path. Sensitive notes are withheld.

    Returns JSON with `content` and `content_hash` (use the hash as `expected_hash`
    when updating/moving to guard against conflicting edits).
    """
    return _dispatch("get_note", {"path": path})


@mcp.tool(name="second_brain_move_note",
          annotations={"title": "Second Brain Move Note", **_WRITE})
def second_brain_move_note(path: str, to_folder: str,
                           expected_hash: str | None = None) -> str:
    """Move a note into a PARA folder (e.g. Inbox -> '10 Projects/My Project').

    Atomic, path-safe, hash-guarded (pass `expected_hash` from get_note to refuse
    if the note changed), and undoable via the returned operation_id.
    """
    payload: dict = {"path": path, "to_folder": to_folder}
    if expected_hash is not None:
        payload["expected_hash"] = expected_hash
    return _dispatch("move_note", payload)


@mcp.tool(name="second_brain_update_note",
          annotations={"title": "Second Brain Update Note", **_WRITE})
def second_brain_update_note(path: str, text: str, mode: str = "append",
                             expected_hash: str | None = None) -> str:
    """Append to (mode='append') or replace the body of (mode='replace_body') a note.

    Hash-guarded and undoable via the returned operation_id.
    """
    payload: dict = {"path": path, "text": text, "mode": mode}
    if expected_hash is not None:
        payload["expected_hash"] = expected_hash
    return _dispatch("update_note", payload)


@mcp.tool(name="second_brain_undo",
          annotations={"title": "Second Brain Undo", "readOnlyHint": False,
                       "destructiveHint": True, "idempotentHint": True,
                       "openWorldHint": False})
def second_brain_undo(operation_id: str) -> str:
    """Reverse a previous move/update/capture by its operation_id (hash-guarded)."""
    return _dispatch("undo_operation", {"operation_id": operation_id})


def main() -> None:
    print(f"Second Brain Mac MCP (streamable-http) on http://{HOST}:{PORT}/mcp")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
