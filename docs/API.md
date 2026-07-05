# API and Tool Contracts

Phase 1B exposes a minimal, local-only HTTP API (Second Brain Core) so Hermes can
call tools over `SECOND_BRAIN_CORE_URL` (default `http://127.0.0.1:8787`). It is a
thin HTTP adapter over the same `LocalToolDispatcher`, capability checks, and audit
logging used in Phase 1A. See "HTTP Core API" below.

It exposes a local dispatcher for these tools:

| Tool | Phase | Purpose |
| --- | --- | --- |
| `health_check` | Phase 1A | Verify that Second Brain Core can receive a safe tool call. |
| `job_status` | Phase 1A | Return mock/no jobs status. |
| `sync_status` | Phase 1A | Return unknown/not configured sync status. |
| `capture_note` | Phase 2 | Create a note capture job. |
| `search_vault` | Phase 3 | Search notes. |
| `get_note` | Phase 3 | Read allowed note content. |
| `update_note` | Phase 2/3 | Update a note with conflict protection. |
| `move_note` | Phase 3 | Move a note between PARA folders. |
| `approve_media` | Phase 6 | Record media retention approval. |
| `undo_operation` | Phase 2/3 | Undo reversible operations. |
| `sync_status` | Phase 4 | Report Headless Sync status. |

## Error Format Target

```json
{
  "error": {
    "code": "CONFIG_INVALID",
    "message": "Safe user-facing message.",
    "retryable": false
  }
}
```

## Phase 0 Internal Interfaces

- `load_config()` loads and validates runtime config.
- `apply_migrations()` creates or updates the SQLite database.
- `audit_vault(path)` reads vault structure without writing files.
- `LocalToolDispatcher.call("health_check")` runs the safe mock tool.
- `require_enabled(conn, capability_id)` rejects disabled tools.
- `run_phase1b_preflight(config, dispatcher)` checks readiness for live Hermes gateway.

## Local Tool Result Shape

```json
{
  "tool": "health_check",
  "ok": true,
  "result": {
    "status": "ok",
    "service": "second-brain-core",
    "phase": "1A"
  },
  "operation_id": "op_..."
}
```

## HTTP Core API (Phase 1B)

Run with:

```bash
PYTHONPATH=src python3 -m second_brain.server
```

The server binds loopback-only and refuses any non-loopback host
(`127.0.0.1`, `localhost`, `::1`). All routes except `/health` require
`Authorization: Bearer <HERMES_INTERNAL_TOOL_TOKEN>`.

| Method | Route | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | none | Liveness probe for ops/monitoring. |
| GET | `/tools` | bearer | List enabled capabilities. |
| POST | `/tools/call` | bearer | Dispatch a safe tool through the registry. |

Request body for `POST /tools/call`:

```json
{ "tool": "health_check", "payload": {}, "user_id": "hermes:gateway" }
```

Response uses the Local Tool Result Shape (HTTP 200 even when `ok` is false; the
`ok`/`error` fields carry the dispatch outcome). HTTP-level errors:

- `401 UNAUTHORIZED` - missing or invalid bearer token.
- `400 BAD_REQUEST` - body is not valid JSON / missing `tool`.
- `404 NOT_FOUND` - unknown route.

Every dispatched call (success or capability rejection) is written to the
`operations` audit table with metadata only (no prompt body, token, or note content).

## MCP Server (Phase 1B)

Hermes integrates tools over MCP, not REST, so the Second Brain Core is also
exposed as a stdio MCP server: `second_brain.mcp_server` (server name
`second_brain_mcp`). It wraps the same `LocalToolDispatcher` (capability checks +
audit) and exposes only the safe, read-only tools:

| MCP tool | Capability | Annotations |
| --- | --- | --- |
| `second_brain_health_check` | `health_check` | readOnly, non-destructive, idempotent |
| `second_brain_job_status` | `job_status` | readOnly, non-destructive, idempotent |
| `second_brain_sync_status` | `sync_status` | readOnly, non-destructive, idempotent |
| `second_brain_capture_note` | `capture_note` | write, non-destructive, idempotent (Phase 2) |
| `second_brain_undo_capture` | `undo_operation` | write, destructive, idempotent (Phase 2) |

`second_brain_capture_note(text, title?, tags?, idempotency_key?)` creates a note in
`00 Inbox` with PARA/CODE frontmatter (atomic, path-safe, append-only, deduped). It
returns `result.note_path`, `result.sensitive`, `result.deduped`, and an
`operation_id`. `second_brain_undo_capture(operation_id)` deletes the note that a
capture created (hash-guarded; refuses if the note was edited; no double-undo).
Sensitive content is auto-detected and gets a non-revealing filename plus disabled
index/AI/preview. `update_note`, `move_note`, and `search_vault` remain disabled
until Phase 3. Each tool returns the Local Tool Result Shape as a JSON string.
Run/registration in `docs/GO_LIVE.md`.

Requires the `mcp` package: `pip install -e ".[mcp]"`.

## Mac-side MCP (Phase 3)

`second_brain.mcp_http_server` runs the Core on the Mac mini (full vault) and is
reached by Hermes-on-VPS over Tailscale (FastMCP streamable-http). It exposes the
read/organize tools:

| MCP tool | Capability | Notes |
| --- | --- | --- |
| `second_brain_search_vault` | `search_vault` | FTS over the vault; sensitive bodies excluded. |
| `second_brain_get_note` | `get_note` | Returns content + `content_hash`; sensitive notes withheld. |
| `second_brain_move_note` | `move_note` | Move into a PARA folder; atomic, hash-guarded, undoable. |
| `second_brain_update_note` | `update_note` | Append/replace body; hash-guarded, undoable. |
| `second_brain_undo` | `undo_operation` | Reverse capture/move/update by operation_id. |

Use the `content_hash` from `get_note` as `expected_hash` on move/update so a note
edited in Obsidian meanwhile is never clobbered. Register:
`hermes mcp add second-brain-mac --url http://<macmini-tailnet>:8788/mcp`. Capture
stays on the VPS stdio MCP (hybrid). Run/registration in `docs/PHASE_3_PLAN.md`.

## Phase 1B Preflight Result Shape

```json
{
  "ready_for_live_gateway": false,
  "checks": [
    {
      "name": "hermes_installed",
      "ok": false,
      "message": "`hermes` command was not found in PATH."
    }
  ]
}
```
