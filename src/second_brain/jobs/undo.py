"""Unified undo for reversible vault operations (capture / move / update).

Dispatches on the original operation's ``tool_name`` and uses the undo payload
recorded at the time. Every undo is hash-guarded: it refuses if the note has
changed since the operation, so a manual Obsidian edit is never lost.
"""

from __future__ import annotations

import json
import os
import sqlite3

from second_brain.config import AppConfig
from second_brain.vault import git_sync, reader, writer


class UndoError(ValueError):
    """Raised when an operation cannot be undone safely."""


def undo_operation(
    conn: sqlite3.Connection, config: AppConfig, *, operation_id: str
) -> dict[str, object]:
    op = conn.execute(
        "SELECT id, tool_name, undo_payload, status FROM operations WHERE id = ?",
        (operation_id,),
    ).fetchone()
    if op is None:
        raise UndoError(f"Unknown operation: {operation_id}")
    if (op["status"] or "").startswith("undone"):
        raise UndoError("Operation already undone.")

    payload = json.loads(op["undo_payload"]) if op["undo_payload"] else {}
    tool = op["tool_name"]

    if tool == "capture_note":
        result = _undo_capture(conn, config, payload)
    elif tool == "move_note":
        result = _undo_move(conn, config, payload)
    elif tool == "update_note":
        result = _undo_update(conn, config, payload)
    else:
        raise UndoError(f"Operation is not undoable: {tool}")

    conn.execute(
        "UPDATE operations SET status = 'undone' WHERE id = ?", (operation_id,)
    )
    if config.vault_git_sync:
        try:
            git_sync.sync(config.vault_path, f"undo: {result.get('note_path', '')}")
        except git_sync.GitSyncError:
            pass
    return result


def _undo_capture(conn, config: AppConfig, payload: dict) -> dict[str, object]:
    note_path = payload.get("note_path")
    if not note_path:
        raise UndoError("Operation has no note to undo.")
    abs_path = reader.resolve_in_vault(config.vault_path, note_path)
    if abs_path.exists():
        expected = payload.get("content_hash")
        if expected and writer.file_hash(abs_path) != expected:
            raise UndoError("Note was modified since capture; refusing to delete it.")
        abs_path.unlink()
    note_id = payload.get("note_id")
    if note_id:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return {"undone": True, "action": "capture", "note_path": note_path}


def _undo_move(conn, config: AppConfig, payload: dict) -> dict[str, object]:
    from_rel = payload.get("from")
    to_rel = payload.get("to")
    if not from_rel or not to_rel:
        raise UndoError("Incomplete move payload.")
    current = reader.resolve_in_vault(config.vault_path, to_rel)
    original = reader.resolve_in_vault(config.vault_path, from_rel)
    if not current.exists():
        raise UndoError("Moved note not found; cannot undo.")
    if original.exists():
        raise UndoError("Original path is now occupied; refusing to undo.")
    original.parent.mkdir(parents=True, exist_ok=True)
    os.replace(current, original)
    conn.execute("UPDATE notes SET path = ? WHERE path = ?", (from_rel, to_rel))
    return {"undone": True, "action": "move", "note_path": from_rel}


def _undo_update(conn, config: AppConfig, payload: dict) -> dict[str, object]:
    rel = payload.get("path")
    prior = payload.get("prior_content")
    if not rel or prior is None:
        raise UndoError("Incomplete update payload.")
    abs_path = reader.resolve_in_vault(config.vault_path, rel)
    if not abs_path.exists():
        raise UndoError("Note not found; cannot undo.")
    post_hash = payload.get("post_hash")
    if post_hash and writer.file_hash(abs_path) != post_hash:
        raise UndoError("Note edited since the update; refusing to revert.")
    writer.atomic_write(abs_path, prior)
    conn.execute(
        "UPDATE notes SET current_hash = ? WHERE path = ?",
        (writer.content_hash(prior), rel),
    )
    return {"undone": True, "action": "update", "note_path": rel}
