# Decisions

## 2026-06-17 - Phase 3 Runs the Core on the Mac, Reached over Tailscale

Context: `search_vault`/`move_note`/`update_note` need the whole vault, which lives on
the Macs via Obsidian Sync. The VPS only holds the Inbox. Mirroring the whole vault to
the VPS would create a second sync system fighting Obsidian Sync (conflicts, `.git`
synced) and ship sensitive notes off-device.

Decision: Run the Second Brain Core on the **Mac mini** (full vault), exposed to
Hermes-on-VPS as a remote MCP over the private **Tailscale** network
(`mcp_http_server`, FastMCP streamable-http). Capture stays on the VPS inbox courier
(**hybrid**) so it survives the Mac being offline. `move_note`/`update_note` run
**without per-op approval**, relying on hash-guard (never clobber a note edited in
Obsidian) + undo. Search indexes sensitive notes by metadata only.

Consequence: Obsidian Sync stays the single source of truth; the vault never leaves
Andri's machines; the existing dispatcher/capability/audit code is reused unchanged.

## 2026-06-17 - Phase 2 Writes Go Through Audited capture_note (Path 1)

Context: Hermes ships a bundled `obsidian` skill that can create notes directly, but
the project's whole value is the Capability Gateway, audit log, and undo. A 3-way
comparison (Path 1 custom `capture_note` / Path 2 Hermes' obsidian skill / Path 3
hybrid) was made.

Decision: Phase 2 writes use the **audited `capture_note`** in Second Brain Core
(capability check + audit + `undo_operation`, Inbox-only, append-only). Hermes'
obsidian skill is NOT used for writes; it is reserved for lower-risk read/search in
Phase 3 (the Path 3 hybrid direction).

Consequence: every capture is reversible and recorded; vault-write authority stays
in Second Brain Core, honoring the architecture boundary.

## 2026-06-17 - Vault Sync via Git Inbox Courier (keep Obsidian Sync)

Context: Andri uses paid Obsidian Sync across Mac mini, MacBook Air, and iPhone.
Obsidian Sync needs the Obsidian app running, so the always-on VPS cannot join it.
The Mac mini is currently off at night.

Decision: Keep Obsidian Sync as the device-sync layer. Bridge the VPS to the vault
with a **git "inbox" courier**: the VPS commits each note to a private GitHub inbox
repo; a Mac-side ingest job moves notes into the real vault, and Obsidian Sync
propagates. Resilient to the Mac being off. Tailscale real-time bridge is a later
upgrade once a Mac is 24/7.

Consequence: captures are never lost (queued in GitHub) and require no inbound
access to the Mac.

## 2026-06-17 - Sensitive Notes Are Quarantined, Not Blocked

Context: Some captures contain secrets (passwords, `#private`).

Decision: Detect sensitivity (whole-word hints + `#private` + explicit flag). Sensitive
notes are still saved to the vault (the user's own data) but get a non-revealing
filename and `sensitive: true` with `ai_processing`/`semantic_index`/`telegram_preview`
set to `disabled`; the tool response omits the body.

Consequence: private content is captured without being indexed, AI-processed, or
echoed back.

## 2026-06-16 - Phase 0 Uses Fake Vault Only

Context: The project will eventually write to an Obsidian vault, but real notes must not be risked during setup.

Decision: All Phase 0 tests use `tests/fixtures/vault`. Real vault audit requires a read-only copy and explicit path.

Consequence: Build can proceed safely before vault migration.

## 2026-06-16 - Python Core with Stdlib Foundation

Context: Phase 0 should run on another machine without dependency friction.

Decision: Config, migration, and audit are implemented with Python standard library only.

Consequence: Later phases can add FastAPI, Pydantic, pytest, and AI SDK dependencies when needed.

## 2026-06-16 - SQLite WAL for MVP

Context: MVP is single-user and should stay lightweight.

Decision: Use SQLite with WAL mode for Phase 0 and MVP.

Consequence: No Postgres/Redis required at the beginning.

## 2026-06-16 - Phase 1A Uses Local Dispatcher Before HTTP

Context: Hermes integration needs a tool target, but adding a web server before the registry and audit model is stable would increase moving parts.

Decision: Implement a Python local dispatcher first with `health_check`, `job_status`, and `sync_status`.

Consequence: Tool behavior can be tested without network or Telegram credentials. HTTP/FastAPI can be added later as an adapter.

## 2026-06-16 - Write Tools Registered but Disabled

Context: Hermes should know the future tool shape, but Phase 1 must not write to the vault.

Decision: Register `capture_note`, `search_vault`, `update_note`, `move_note`, and `undo_operation` as disabled capabilities.

Consequence: Calls to disabled tools are rejected and audited until their implementation phase.

## 2026-06-16 - Core HTTP API Uses Stdlib http.server, Loopback-Only

Context: Phase 1B needs an HTTP target so Hermes can call Second Brain tools over `SECOND_BRAIN_CORE_URL`, but adding FastAPI/uvicorn would break the stdlib-only foundation and the local-only safety boundary.

Decision: Implement the Core API with `http.server` (no new dependency), bind loopback-only and refuse non-loopback hosts, require a bearer `HERMES_INTERNAL_TOOL_TOKEN` on all routes except `/health`, and route every call through the existing dispatcher, capability checks, and audit logging.

Consequence: Hermes can integrate over HTTP now with zero dependencies and no public exposure. FastAPI can replace it later if richer features are needed.

## 2026-06-16 - Hermes Integration Uses an MCP Server

Context: Hermes connects external tools via MCP (stdio or HTTP MCP), not plain REST. The Phase 1B HTTP Core API cannot be called by Hermes directly.

Decision: Expose Second Brain to Hermes as a stdio MCP server (`second_brain.mcp_server`, built on FastMCP) that wraps the existing `LocalToolDispatcher`, so capability checks and audit logging are preserved. Only the safe read-only tools are registered; write tools are not exposed. This adds the optional `mcp` dependency (acceptable for this phase per the stdlib-foundation decision). The HTTP Core API is kept as a documented local interface and for non-Hermes clients.

Consequence: Hermes can use Second Brain tools through `hermes mcp add`. The dispatcher/capability/audit core remains the single source of truth across both the HTTP and MCP front ends.

## 2026-06-16 - Phase 1B Requires Preflight Before Live Gateway

Context: Starting a live Telegram gateway before checking credentials and tool permissions could expose unsafe behavior.

Decision: Add `second_brain.preflight` to check Hermes installation, gateway config, safe tools, and disabled write tools before live gateway testing.

Consequence: Phase 1B can progress safely even before credentials are available, and live gateway testing has a clear readiness gate.
