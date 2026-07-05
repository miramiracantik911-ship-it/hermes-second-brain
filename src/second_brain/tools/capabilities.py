from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3


class CapabilityError(ValueError):
    """Raised when a tool capability is unknown, disabled, or unsafe."""


@dataclass(frozen=True)
class Capability:
    id: str
    domain: str
    enabled: bool
    risk_level: str
    read_scope: tuple[str, ...]
    write_scope: tuple[str, ...]
    approval_required: bool
    config: dict[str, object]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Capability":
        return cls(
            id=row["id"],
            domain=row["domain"],
            enabled=bool(row["enabled"]),
            risk_level=row["risk_level"],
            read_scope=tuple(json.loads(row["read_scope"])),
            write_scope=tuple(json.loads(row["write_scope"])),
            approval_required=bool(row["approval_required"]),
            config=json.loads(row["config"]),
        )


INITIAL_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        id="health_check",
        domain="system",
        enabled=True,
        risk_level="L0",
        read_scope=("system.health",),
        write_scope=(),
        approval_required=False,
        config={},
    ),
    Capability(
        id="job_status",
        domain="obsidian",
        enabled=True,
        risk_level="L1",
        read_scope=("jobs.status",),
        write_scope=(),
        approval_required=False,
        config={},
    ),
    Capability(
        id="sync_status",
        domain="obsidian",
        enabled=True,
        risk_level="L1",
        read_scope=("sync.status",),
        write_scope=(),
        approval_required=False,
        config={},
    ),
    Capability(
        id="capture_note",
        domain="obsidian",
        enabled=True,
        risk_level="L2",
        read_scope=("vault.metadata",),
        write_scope=("vault.inbox.create",),
        approval_required=False,
        config={"phase": 2},
    ),
    Capability(
        id="search_vault",
        domain="obsidian",
        enabled=True,
        risk_level="L1",
        read_scope=("vault.search",),
        write_scope=(),
        approval_required=False,
        config={"phase": 3},
    ),
    Capability(
        id="get_note",
        domain="obsidian",
        enabled=True,
        risk_level="L1",
        read_scope=("vault.note.read",),
        write_scope=(),
        approval_required=False,
        config={"phase": 3},
    ),
    Capability(
        id="update_note",
        domain="obsidian",
        enabled=True,
        risk_level="L2",
        read_scope=("vault.note.read",),
        write_scope=("vault.note.update",),
        approval_required=False,
        config={"phase": 3},
    ),
    Capability(
        id="move_note",
        domain="obsidian",
        enabled=True,
        risk_level="L2",
        read_scope=("vault.note.read",),
        write_scope=("vault.note.move",),
        approval_required=False,
        config={"phase": 3},
    ),
    Capability(
        id="undo_operation",
        domain="obsidian",
        enabled=True,
        risk_level="L2",
        read_scope=("operations.read",),
        write_scope=("operations.undo",),
        approval_required=False,
        config={"phase": 2},
    ),
    Capability(
        id="approve_media",
        domain="obsidian",
        enabled=False,
        risk_level="L2",
        read_scope=("media.read",),
        write_scope=("media.retention.approve",),
        approval_required=True,
        config={"disabled_until_phase": 6},
    ),
)


def seed_initial_capabilities(conn: sqlite3.Connection) -> None:
    for capability in INITIAL_CAPABILITIES:
        conn.execute(
            """
            INSERT INTO capabilities (
                id, domain, enabled, risk_level, read_scope, write_scope,
                approval_required, config, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                domain = excluded.domain,
                enabled = excluded.enabled,
                risk_level = excluded.risk_level,
                read_scope = excluded.read_scope,
                write_scope = excluded.write_scope,
                approval_required = excluded.approval_required,
                config = excluded.config,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                capability.id,
                capability.domain,
                int(capability.enabled),
                capability.risk_level,
                json.dumps(list(capability.read_scope)),
                json.dumps(list(capability.write_scope)),
                int(capability.approval_required),
                json.dumps(capability.config, sort_keys=True),
            ),
        )


def get_capability(conn: sqlite3.Connection, capability_id: str) -> Capability:
    row = conn.execute(
        "SELECT * FROM capabilities WHERE id = ?",
        (capability_id,),
    ).fetchone()
    if row is None:
        raise CapabilityError(f"Unknown capability: {capability_id}")
    return Capability.from_row(row)


def require_enabled(conn: sqlite3.Connection, capability_id: str) -> Capability:
    capability = get_capability(conn, capability_id)
    if not capability.enabled:
        raise CapabilityError(f"Capability disabled: {capability_id}")
    return capability

