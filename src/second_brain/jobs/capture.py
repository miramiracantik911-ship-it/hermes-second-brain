"""capture_note and its undo - the first Second Brain write capability (Phase 2).

A capture writes a Markdown note into the vault `00 Inbox`, records `notes` and
`jobs` rows, and returns an undo payload so the dispatcher can log a reversible
`operations` row. `undo_capture` reverses a capture, hash-guarded so a note the
user has since edited is never deleted.

This module performs DB writes but does NOT commit; the dispatcher owns the commit
so the file write and the audit row land together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import sqlite3
from uuid import uuid4
from zoneinfo import ZoneInfo

from second_brain.config import AppConfig
from second_brain.vault import git_sync, writer
from second_brain.vault.sensitivity import detect_sensitive


class CaptureError(ValueError):
    """Raised when a capture or undo request is invalid."""


@dataclass(frozen=True)
class CaptureResult:
    note_path: str
    note_id: str | None
    content_hash: str | None
    sensitive: bool
    idempotency_key: str
    deduped: bool
    undo_payload: dict[str, object] | None
    synced: bool = False


def _git_sync(config: AppConfig, message: str) -> bool:
    """Best-effort commit/push of the inbox repo. Never raises."""
    if not config.vault_git_sync:
        return False
    try:
        return git_sync.sync(config.vault_path, message).pushed
    except git_sync.GitSyncError:
        return False


def _today(config: AppConfig) -> date:
    try:
        tz = ZoneInfo(config.timezone)
    except Exception:  # pragma: no cover - defensive for bad tz strings
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date()


def _derive_title(text: str) -> str:
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    first_line = first_line.lstrip("#").strip()
    if not first_line:
        return "Catatan Telegram"
    title = " ".join(first_line.split()[:10])
    return title[:80] if title else "Catatan Telegram"


def _idempotency_key(text: str, created: date) -> str:
    base = f"{created.isoformat()}|{text.strip()}"
    return "cap_" + writer.content_hash(base)[:24]


def capture_note(
    conn: sqlite3.Connection,
    config: AppConfig,
    *,
    text: str,
    title: str | None = None,
    tags: list[str] | None = None,
    source: str = "telegram",
    idempotency_key: str | None = None,
    sensitive: bool | None = None,
    user_id: str = "hermes:mcp",
    created_date: date | None = None,
) -> CaptureResult:
    if not text or not text.strip():
        raise CaptureError("text is required and cannot be empty.")

    tags = list(tags or [])
    created = created_date or _today(config)
    key = idempotency_key or _idempotency_key(text, created)

    existing = conn.execute(
        "SELECT id, instruction, state FROM jobs WHERE idempotency_key = ?",
        (key,),
    ).fetchone()
    if existing is not None and existing["state"] == "done" and existing["instruction"]:
        note_path = existing["instruction"]
        if (config.vault_path / note_path).exists():
            note_row = conn.execute(
                "SELECT id, sensitive, current_hash FROM notes WHERE path = ?",
                (note_path,),
            ).fetchone()
            return CaptureResult(
                note_path=note_path,
                note_id=note_row["id"] if note_row else None,
                content_hash=note_row["current_hash"] if note_row else None,
                sensitive=bool(note_row["sensitive"]) if note_row else bool(sensitive),
                idempotency_key=key,
                deduped=True,
                undo_payload=None,
            )

    is_sensitive = detect_sensitive(f"{title or ''}\n{text}", explicit=sensitive)
    final_title = (title or _derive_title(text)).strip() or "Catatan Telegram"

    result = writer.write_capture(
        config.vault_path,
        title=final_title,
        body=text,
        tags=tags,
        created_date=created,
        sensitive=is_sensitive,
        source=source,
    )

    note_id = "note_" + uuid4().hex
    conn.execute(
        """
        INSERT INTO notes (
            id, path, title, para, code_stage, distillation_level,
            sensitive, semantic_index, current_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            note_id,
            result.relative_path,
            final_title,
            "inbox",
            "capture",
            "D1",
            int(is_sensitive),
            0 if is_sensitive else 1,
            result.content_hash,
        ),
    )

    job_id = "job_" + uuid4().hex
    conn.execute(
        """
        INSERT INTO jobs (
            id, idempotency_key, user_id, input_type, state, risk_level,
            sensitive, instruction
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            key,
            user_id,
            "text",
            "done",
            "L2",
            int(is_sensitive),
            result.relative_path,  # non-sensitive reference for dedupe
        ),
    )

    synced = _git_sync(config, f"capture: {result.relative_path}")

    undo_payload = {
        "note_path": result.relative_path,
        "note_id": note_id,
        "content_hash": result.content_hash,
    }
    return CaptureResult(
        note_path=result.relative_path,
        note_id=note_id,
        content_hash=result.content_hash,
        sensitive=is_sensitive,
        idempotency_key=key,
        deduped=False,
        undo_payload=undo_payload,
        synced=synced,
    )
