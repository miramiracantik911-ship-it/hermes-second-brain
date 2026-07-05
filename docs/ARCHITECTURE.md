# Architecture

## Current Phase

Phase 1A builds the local Hermes foundation. Hermes and Telegram are not connected live yet, but the project now has a Capability Registry, local tool dispatcher, and audit logging for tool calls. Production vault access is still disabled.

## Runtime Target

```text
Telegram
  -> Hermes Agent
  -> Capability Gateway
  -> Second Brain Core API
  -> SQLite + Obsidian Vault
```

## Boundaries

| Component | Owns | Must Not Own |
| --- | --- | --- |
| Hermes Agent | Conversation, session, tool selection. | Direct vault writes or secrets. |
| Capability Gateway | Tool validation, permission, approval, audit. | Markdown rendering or PARA judgment. |
| Second Brain Core | Jobs, vault write policy, conflict handling, index. | External actions like email sending. |
| Vault | Markdown source of truth. | Runtime secrets or API tokens. |
| Database | Jobs, audit, index, operational metadata. | Source of truth for note content. |

## Phase 0 Architecture

Phase 0 includes:

- `second_brain.config`: configuration loading and safety validation.
- `second_brain.db.migrate`: SQLite migration runner.
- `second_brain.audit.vault_audit`: read-only vault audit.
- `tests/fixtures/vault`: fake vault for tests.

## Phase 1A Additions

- `second_brain.tools.capabilities`: non-secret capability definitions and enable/disable checks.
- `second_brain.tools.dispatcher`: local tool dispatcher for mock/status tools.
- `second_brain.audit.tool_audit`: audit rows for every local tool call.

## Enabled Tools in Phase 1A

| Tool | Risk | Status |
| --- | --- | --- |
| `health_check` | L0 | Enabled |
| `job_status` | L1 | Enabled |
| `sync_status` | L1 | Enabled |
| `capture_note` | L2 | Enabled (Phase 2) |
| `undo_operation` | L2 | Enabled (Phase 2) |
| `search_vault` | L1 | Enabled (Phase 3) |
| `get_note` | L1 | Enabled (Phase 3) |
| `update_note` | L2 | Enabled (Phase 3) |
| `move_note` | L2 | Enabled (Phase 3) |
| `approve_media` | L2 | Registered but disabled (Phase 6) |

## Phase 3 Additions

- `second_brain.vault.reader`: path-safe note reads, frontmatter inspection, sensitivity.
- `second_brain.vault.search`: FTS5 index over the vault; sensitive bodies excluded.
- `second_brain.vault.organize`: `move_note` + `update_note` (atomic, hash-guarded).
- `second_brain.jobs.undo`: unified undo for capture/move/update.
- `second_brain.mcp_http_server`: FastMCP streamable-http server for the **Mac-side
  Core**, reached by Hermes-on-VPS over Tailscale (the full vault lives on the Mac).
- Capture stays on the VPS inbox courier (hybrid); read/organize run on the Mac.

## Phase 2 Additions

- `second_brain.vault.writer`: path-safe, atomic Markdown note creation under
  `00 Inbox`, with frontmatter rendering and content hashing.
- `second_brain.vault.sensitivity`: sensitive-content detection.
- `second_brain.jobs.capture`: `capture_note` (write + record `jobs`/`notes`/
  `operations`, dedupe) and `undo_capture` (hash-guarded delete).
- Dispatcher routes `capture_note`/`undo_operation`, passing config and an undo
  payload to the audit row. MCP exposes `second_brain_capture_note` and
  `second_brain_undo_capture`.
- Vault writes reach Andri's Obsidian Sync devices via a git "inbox" courier (a
  Mac-side ingest job), so the always-on VPS never needs Obsidian Sync directly.
