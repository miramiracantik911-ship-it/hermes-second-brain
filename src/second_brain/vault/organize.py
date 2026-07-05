"""Organize-stage vault operations for Phase 3: move and update existing notes.

Both are atomic, path-safe, hash-guarded (never clobber a note edited in Obsidian
since it was read), record DB + audit state, and produce an undo payload so the
change can be reversed. Mirrors the shape of jobs.capture.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sqlite3

from second_brain.config import AppConfig
from second_brain.vault import git_sync, reader, writer


class OrganizeError(ValueError):
    """Raised when a move/update request is invalid or would lose data."""


@dataclass(frozen=True)
class MoveResult:
    from_path: str
    to_path: str
    undo_payload: dict[str, object]
    synced: bool = False


@dataclass(frozen=True)
class UpdateResult:
    note_path: str
    undo_payload: dict[str, object]
    synced: bool = False


def _git_sync(config: AppConfig, message: str) -> bool:
    if not config.vault_git_sync:
        return False
    try:
        return git_sync.sync(config.vault_path, message).pushed
    except git_sync.GitSyncError:
        return False


def _require_note(root: Path, rel_path: str) -> Path:
    path = reader.resolve_in_vault(root, rel_path)
    if path.suffix.lower() != ".md":
        raise OrganizeError(f"Not a Markdown note: {rel_path}")
    if not path.is_file():
        raise OrganizeError(f"Note not found: {rel_path}")
    return path


def _check_hash(path: Path, expected: str | None) -> None:
    if expected and writer.file_hash(path) != expected:
        raise OrganizeError(
            "Note changed since it was read; refusing to overwrite. Re-read and retry."
        )


def move_note(
    conn: sqlite3.Connection,
    config: AppConfig,
    *,
    path: str,
    to_folder: str,
    expected_hash: str | None = None,
) -> MoveResult:
    if not path or not to_folder:
        raise OrganizeError("path and to_folder are required.")
    root = config.vault_path.expanduser().resolve()
    src = _require_note(root, path)
    _check_hash(src, expected_hash)

    dest_dir = reader.resolve_in_vault(root, to_folder)
    if dest_dir.suffix.lower() == ".md":
        raise OrganizeError("to_folder must be a folder, not a file.")
    dest_dir.mkdir(parents=True, exist_ok=True)

    target = dest_dir / src.name
    counter = 2
    while target.exists():
        target = dest_dir / f"{src.stem}-{counter}{src.suffix}"
        counter += 1

    from_rel = str(src.relative_to(root))
    os.replace(src, target)
    to_rel = str(target.resolve().relative_to(root))

    conn.execute(
        "UPDATE notes SET path = ?, code_stage = 'organize', "
        "updated_at = CURRENT_TIMESTAMP WHERE path = ?",
        (to_rel, from_rel),
    )
    synced = _git_sync(config, f"move: {from_rel} -> {to_rel}")
    return MoveResult(
        from_path=from_rel,
        to_path=to_rel,
        undo_payload={"action": "move", "from": from_rel, "to": to_rel},
        synced=synced,
    )


def update_note(
    conn: sqlite3.Connection,
    config: AppConfig,
    *,
    path: str,
    text: str,
    mode: str = "append",
    expected_hash: str | None = None,
) -> UpdateResult:
    if not text or not text.strip():
        raise OrganizeError("text is required and cannot be empty.")
    root = config.vault_path.expanduser().resolve()
    note = _require_note(root, path)
    current = note.read_text(encoding="utf-8")
    _check_hash(note, expected_hash)

    if mode == "append":
        new_content = current.rstrip("\n") + "\n\n" + text.strip() + "\n"
    elif mode == "replace_body":
        frontmatter = ""
        lines = current.splitlines()
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    frontmatter = "\n".join(lines[: i + 1])
                    break
        new_content = (
            f"{frontmatter}\n\n{text.strip()}\n" if frontmatter else text.strip() + "\n"
        )
    else:
        raise OrganizeError(f"Unknown update mode: {mode}")

    rel = str(note.relative_to(root))
    new_hash = writer.content_hash(new_content)
    writer.atomic_write(note, new_content)
    conn.execute(
        "UPDATE notes SET current_hash = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE path = ?",
        (new_hash, rel),
    )
    synced = _git_sync(config, f"update: {rel}")
    return UpdateResult(
        note_path=rel,
        undo_payload={
            "action": "update",
            "path": rel,
            "prior_content": current,
            "post_hash": new_hash,
        },
        synced=synced,
    )
