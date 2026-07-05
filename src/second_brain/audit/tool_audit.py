from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
from uuid import uuid4


@dataclass(frozen=True)
class ToolAuditEvent:
    user_id: str
    tool_name: str
    risk_level: str
    target_type: str
    target_id: str | None
    status: str
    error_code: str | None = None
    undo_payload: dict[str, object] | None = None


def record_tool_call(conn: sqlite3.Connection, event: ToolAuditEvent) -> str:
    operation_id = f"op_{uuid4().hex}"
    safe_undo_payload = (
        json.dumps(event.undo_payload, sort_keys=True) if event.undo_payload else None
    )
    conn.execute(
        """
        INSERT INTO operations (
            id, user_id, tool_name, risk_level, target_type, target_id,
            undo_payload, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            operation_id,
            event.user_id,
            event.tool_name,
            event.risk_level,
            event.target_type,
            event.target_id,
            safe_undo_payload,
            event.status if event.error_code is None else f"{event.status}:{event.error_code}",
        ),
    )
    return operation_id

