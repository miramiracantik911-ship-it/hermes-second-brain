from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Any

from second_brain.audit.tool_audit import ToolAuditEvent, record_tool_call
from second_brain.config import AppConfig
from second_brain.jobs.capture import CaptureError, capture_note
from second_brain.jobs.undo import UndoError, undo_operation
from second_brain.tools.capabilities import CapabilityError, require_enabled
from second_brain.vault import reader, search
from second_brain.vault.organize import OrganizeError, move_note, update_note
from second_brain.vault.reader import VaultReadError

# Vault-operation errors map to a stable, safe error code in the tool result.
_VAULT_ERRORS = (CaptureError, OrganizeError, UndoError, VaultReadError)
_VAULT_ERROR_CODES = {
    CaptureError: "CAPTURE_FAILED",
    OrganizeError: "ORGANIZE_FAILED",
    UndoError: "UNDO_FAILED",
    VaultReadError: "READ_FAILED",
}


@dataclass(frozen=True)
class ToolResult:
    tool: str
    ok: bool
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    operation_id: str | None = None


@dataclass(frozen=True)
class ExecOutcome:
    result: dict[str, Any]
    undo_payload: dict[str, Any] | None = None
    target_id: str | None = None
    target_type: str | None = None


class LocalToolDispatcher:
    def __init__(self, conn: sqlite3.Connection, config: AppConfig | None = None):
        self.conn = conn
        self.config = config

    def call(
        self,
        tool_name: str,
        payload: dict[str, Any] | None = None,
        *,
        user_id: str = "local:dev",
    ) -> ToolResult:
        payload = payload or {}
        try:
            capability = require_enabled(self.conn, tool_name)
        except CapabilityError as exc:
            return self._fail(
                tool_name, user_id, "unknown", "capability", tool_name,
                "rejected", "CAPABILITY_REJECTED", str(exc),
            )

        try:
            outcome = self._execute(tool_name, payload, user_id=user_id)
        except _VAULT_ERRORS as exc:
            code = _VAULT_ERROR_CODES.get(type(exc), "VAULT_OP_FAILED")
            return self._fail(
                tool_name, user_id, capability.risk_level, "note", None,
                "failed", code, str(exc),
            )

        operation_id = record_tool_call(
            self.conn,
            ToolAuditEvent(
                user_id=user_id,
                tool_name=tool_name,
                risk_level=capability.risk_level,
                target_type=outcome.target_type or capability.domain,
                target_id=outcome.target_id,
                status="success",
                undo_payload=outcome.undo_payload,
            ),
        )
        self.conn.commit()
        return ToolResult(
            tool=tool_name, ok=True, result=outcome.result, operation_id=operation_id
        )

    def _fail(
        self, tool_name, user_id, risk, target_type, target_id, status, code, message
    ) -> ToolResult:
        operation_id = record_tool_call(
            self.conn,
            ToolAuditEvent(
                user_id=user_id,
                tool_name=tool_name,
                risk_level=risk,
                target_type=target_type,
                target_id=target_id,
                status=status,
                error_code=code,
            ),
        )
        self.conn.commit()
        return ToolResult(
            tool=tool_name,
            ok=False,
            error={"code": code, "message": message, "retryable": False},
            operation_id=operation_id,
        )

    def _execute(
        self, tool_name: str, payload: dict[str, Any], *, user_id: str
    ) -> ExecOutcome:
        if tool_name == "health_check":
            return ExecOutcome(
                {"status": "ok", "service": "second-brain-core", "phase": "1A"}
            )
        if tool_name == "job_status":
            return ExecOutcome(
                {"status": "ok", "jobs": [], "message": "No job worker is running."}
            )
        if tool_name == "sync_status":
            return ExecOutcome(
                {"status": "unknown", "message": "Headless Sync is not configured."}
            )
        if tool_name == "capture_note":
            return self._capture_note(payload, user_id=user_id)
        if tool_name == "search_vault":
            return self._search_vault(payload)
        if tool_name == "get_note":
            return self._get_note(payload)
        if tool_name == "move_note":
            return self._move_note(payload)
        if tool_name == "update_note":
            return self._update_note(payload)
        if tool_name == "undo_operation":
            return self._undo_operation(payload)
        raise CapabilityError(f"No local implementation for capability: {tool_name}")

    def _require_config(self) -> AppConfig:
        if self.config is None:
            raise CaptureError(
                "Second Brain config is not available for vault operations."
            )
        return self.config

    def _capture_note(self, payload: dict[str, Any], *, user_id: str) -> ExecOutcome:
        config = self._require_config()
        result = capture_note(
            self.conn,
            config,
            text=payload.get("text", ""),
            title=payload.get("title"),
            tags=payload.get("tags"),
            source=payload.get("source", "telegram"),
            idempotency_key=payload.get("idempotency_key"),
            sensitive=payload.get("sensitive"),
            user_id=user_id,
        )
        return ExecOutcome(
            result={
                "note_path": result.note_path,
                "sensitive": result.sensitive,
                "deduped": result.deduped,
                "synced": result.synced,
            },
            undo_payload=result.undo_payload,
            target_id=result.note_path,
            target_type="note",
        )

    def _search_vault(self, payload: dict[str, Any]) -> ExecOutcome:
        query = str(payload.get("query", ""))
        limit = int(payload.get("limit", 10))
        results = search.search(self.conn, query, limit=limit)
        return ExecOutcome({"query": query, "count": len(results), "results": results})

    def _get_note(self, payload: dict[str, Any]) -> ExecOutcome:
        config = self._require_config()
        rel = payload.get("path")
        if not rel:
            raise VaultReadError("path is required.")
        content, digest = reader.read_note(config.vault_path, str(rel))
        if reader.is_sensitive(content):
            return ExecOutcome(
                {"path": rel, "sensitive": True,
                 "message": "Note is sensitive; content withheld."},
                target_id=str(rel),
                target_type="note",
            )
        return ExecOutcome(
            {"path": rel, "sensitive": False, "content": content,
             "content_hash": digest},
            target_id=str(rel),
            target_type="note",
        )

    def _move_note(self, payload: dict[str, Any]) -> ExecOutcome:
        config = self._require_config()
        result = move_note(
            self.conn,
            config,
            path=str(payload.get("path", "")),
            to_folder=str(payload.get("to_folder", "")),
            expected_hash=payload.get("expected_hash"),
        )
        return ExecOutcome(
            result={"from": result.from_path, "to": result.to_path,
                    "synced": result.synced},
            undo_payload=result.undo_payload,
            target_id=result.to_path,
            target_type="note",
        )

    def _update_note(self, payload: dict[str, Any]) -> ExecOutcome:
        config = self._require_config()
        result = update_note(
            self.conn,
            config,
            path=str(payload.get("path", "")),
            text=payload.get("text", ""),
            mode=str(payload.get("mode", "append")),
            expected_hash=payload.get("expected_hash"),
        )
        return ExecOutcome(
            result={"note_path": result.note_path, "synced": result.synced},
            undo_payload=result.undo_payload,
            target_id=result.note_path,
            target_type="note",
        )

    def _undo_operation(self, payload: dict[str, Any]) -> ExecOutcome:
        config = self._require_config()
        operation_id = payload.get("operation_id")
        if not operation_id:
            raise UndoError("operation_id is required.")
        result = undo_operation(self.conn, config, operation_id=str(operation_id))
        return ExecOutcome(
            result=result, target_id=str(operation_id), target_type="operation"
        )
