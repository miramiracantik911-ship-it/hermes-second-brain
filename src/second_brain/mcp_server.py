#!/usr/bin/env python3
"""Second Brain MCP server (stdio).

Exposes the safe, read-only Second Brain Core tools to an MCP client such as
Hermes. It is a thin wrapper over the same ``LocalToolDispatcher`` used by the
local dispatcher and HTTP Core API, so every call still goes through the
capability registry and is written to the audit log. Exposes capture (Phase 2)
and organize — search/get/move/update (Phase 3) — plus a unified undo.

Register with Hermes (stdio):

    hermes mcp add second-brain --command "<python>" \
        --args "-m" "second_brain.mcp_server"

The launching environment must have the ``mcp`` package installed and
``second_brain`` importable (e.g. PYTHONPATH=src from the repo root).
"""

from __future__ import annotations

from pathlib import Path
import json

from mcp.server.fastmcp import FastMCP

from second_brain.config import load_config
from second_brain.db.migrate import apply_migrations, connect
from second_brain.tools.dispatcher import LocalToolDispatcher

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# MCP identity for the calling agent (used for audit attribution).
MCP_USER_ID = "hermes:mcp"

mcp = FastMCP("second_brain_mcp")

_config = None


def _get_config():
    """Load config and apply migrations once, lazily.

    Kept out of import time so importing this module has no side effects
    (no DB writes), which keeps tests and process startup clean.
    """
    global _config
    if _config is None:
        config = load_config(project_root=PROJECT_ROOT)
        apply_migrations(config)
        _config = config
    return _config


READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def _dispatch(tool_name: str, payload: dict | None = None) -> str:
    """Run a capability through the dispatcher and return a JSON string.

    Opens a fresh SQLite connection per call (FastMCP may run sync tools in a
    worker thread, and SQLite connections are not shareable across threads).
    The dispatcher enforces the capability check and records an audit row.
    """
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


@mcp.tool(
    name="second_brain_health_check",
    annotations={"title": "Second Brain Health Check", **READ_ONLY},
)
def second_brain_health_check() -> str:
    """Verify that Second Brain Core can receive a safe tool call.

    Takes no arguments. Routes through the capability registry and writes an
    audit row.

    Returns:
        str: JSON object with schema:
        {
            "tool": "health_check",
            "ok": true,
            "result": {"status": "ok", "service": "second-brain-core", "phase": str},
            "error": null,
            "operation_id": "op_..."
        }
    """
    return _dispatch("health_check")


@mcp.tool(
    name="second_brain_job_status",
    annotations={"title": "Second Brain Job Status", **READ_ONLY},
)
def second_brain_job_status() -> str:
    """Report background job status for Second Brain Core.

    Takes no arguments. In the current phase no job worker runs, so the result
    reports an empty job list.

    Returns:
        str: JSON object with schema:
        {
            "tool": "job_status",
            "ok": true,
            "result": {"status": "ok", "jobs": [], "message": str},
            "error": null,
            "operation_id": "op_..."
        }
    """
    return _dispatch("job_status")


@mcp.tool(
    name="second_brain_sync_status",
    annotations={"title": "Second Brain Sync Status", **READ_ONLY},
)
def second_brain_sync_status() -> str:
    """Report Obsidian sync status for Second Brain Core.

    Takes no arguments. Sync is not configured in the current phase, so the
    result reports an unknown/not-configured status.

    Returns:
        str: JSON object with schema:
        {
            "tool": "sync_status",
            "ok": true,
            "result": {"status": "unknown", "message": str},
            "error": null,
            "operation_id": "op_..."
        }
    """
    return _dispatch("sync_status")


@mcp.tool(
    name="second_brain_capture_note",
    annotations={
        "title": "Second Brain Capture Note",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def second_brain_capture_note(
    text: str,
    title: str | None = None,
    tags: list[str] | None = None,
    idempotency_key: str | None = None,
) -> str:
    """Capture a note into the Obsidian vault Inbox (00 Inbox).

    Creates a new Markdown note with PARA/CODE frontmatter. The write is atomic,
    path-safe, append-only (never overwrites), deduped by idempotency key, and
    reversible via `second_brain_undo_capture` (use the returned operation_id).
    Sensitive content (e.g. passwords, `#private`) is auto-detected: such notes
    get a non-revealing filename, are not indexed/AI-processed, and their body is
    not echoed back.

    Args:
        text: The note body (required, non-empty).
        title: Optional title; if omitted, derived from the first line of text.
        tags: Optional list of tags for the frontmatter.
        idempotency_key: Optional key to dedupe retries (e.g. a message id).

    Returns:
        str: JSON object with schema:
        {
            "tool": "capture_note",
            "ok": true,
            "result": {"note_path": str, "sensitive": bool, "deduped": bool},
            "error": null,
            "operation_id": "op_..."   # pass to undo to reverse this capture
        }
    """
    payload: dict = {"text": text}
    if title is not None:
        payload["title"] = title
    if tags is not None:
        payload["tags"] = tags
    if idempotency_key is not None:
        payload["idempotency_key"] = idempotency_key
    return _dispatch("capture_note", payload)


WRITE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}


@mcp.tool(
    name="second_brain_search_vault",
    annotations={"title": "Second Brain Search Vault", **READ_ONLY},
)
def second_brain_search_vault(query: str, limit: int = 10) -> str:
    """Search the Obsidian vault for notes matching `query`.

    Use this to find notes before reading, moving, or updating them. Sensitive
    notes are matched by title/tags only — their body is never indexed or returned.

    Args:
        query: Full-text search terms.
        limit: Maximum number of results (default 10).

    Returns:
        str: JSON with result.results = [{"path", "title", "snippet"}, ...].
    """
    return _dispatch("search_vault", {"query": query, "limit": limit})


@mcp.tool(
    name="second_brain_get_note",
    annotations={"title": "Second Brain Get Note", **READ_ONLY},
)
def second_brain_get_note(path: str) -> str:
    """Read a note's content by vault-relative path (e.g. '00 Inbox/My Note.md').

    Sensitive notes are withheld. The returned `content_hash` should be passed as
    `expected_hash` when moving/updating to guard against conflicting edits.

    Args:
        path: Vault-relative path to the note.

    Returns:
        str: JSON with result = {"content": str, "content_hash": str, ...}.
    """
    return _dispatch("get_note", {"path": path})


@mcp.tool(
    name="second_brain_move_note",
    annotations={"title": "Second Brain Move Note", **WRITE},
)
def second_brain_move_note(
    path: str, to_folder: str, expected_hash: str | None = None
) -> str:
    """Move a note into a PARA folder (e.g. '00 Inbox' -> '10 Projects/My Project').

    Atomic, path-safe, and reversible via the returned operation_id. Optionally pass
    `expected_hash` (from get_note) to refuse the move if the note changed meanwhile.

    Args:
        path: Current vault-relative path of the note.
        to_folder: Destination folder, vault-relative (e.g. '10 Projects').
        expected_hash: Optional content-hash guard from get_note.

    Returns:
        str: JSON with result = {"from": str, "to": str} and an undo operation_id.
    """
    payload: dict = {"path": path, "to_folder": to_folder}
    if expected_hash is not None:
        payload["expected_hash"] = expected_hash
    return _dispatch("move_note", payload)


@mcp.tool(
    name="second_brain_update_note",
    annotations={"title": "Second Brain Update Note", **WRITE},
)
def second_brain_update_note(
    path: str, text: str, mode: str = "append", expected_hash: str | None = None
) -> str:
    """Append to (mode='append') or replace the body of (mode='replace_body') a note.

    Reversible via the returned operation_id. Optionally pass `expected_hash` (from
    get_note) to refuse the update if the note changed meanwhile.

    Args:
        path: Vault-relative path of the note.
        text: Text to append, or the new body when mode='replace_body'.
        mode: 'append' (default) or 'replace_body'.
        expected_hash: Optional content-hash guard from get_note.

    Returns:
        str: JSON with result describing the update and an undo operation_id.
    """
    payload: dict = {"path": path, "text": text, "mode": mode}
    if expected_hash is not None:
        payload["expected_hash"] = expected_hash
    return _dispatch("update_note", payload)


@mcp.tool(
    name="second_brain_undo",
    annotations={
        "title": "Second Brain Undo",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def second_brain_undo(operation_id: str) -> str:
    """Reverse a previous capture, move, or update by its operation_id.

    Safe by design: it refuses if the note was edited since the operation (hash
    mismatch) and cannot undo the same operation twice.

    Args:
        operation_id: The `operation_id` returned by a prior capture/move/update.

    Returns:
        str: JSON object with schema:
        {
            "tool": "undo_operation",
            "ok": true,
            "result": {"undone": true, "note_path": str},
            "error": null,
            "operation_id": "op_..."
        }
    """
    return _dispatch("undo_operation", {"operation_id": operation_id})


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
