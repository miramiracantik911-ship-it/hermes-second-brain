# Phase Log

## Phase 3 - Organize the Vault (search, get, move, update)

Date: 2026-06-17
Status: code complete and tested; Mac-side + Tailscale deployment pending

### Completed

- `vault/reader.py` (path-safe reads, frontmatter, sensitivity), `vault/search.py`
  (FTS5 index; sensitive bodies excluded), `vault/organize.py` (`move_note` +
  `update_note`, atomic, hash-guarded), `jobs/undo.py` (unified undo for
  capture/move/update; git-sync aware).
- Enabled `search_vault`, `get_note`, `update_note`, `move_note`. Added a disabled
  `approve_media` (Phase 6) so the capability gate still has a negative test.
- Dispatcher routes all Phase 3 tools; vault errors map to ORGANIZE/READ/UNDO codes.
- `mcp_http_server.py`: FastMCP streamable-http for the Mac-side Core (search/get/
  move/update/undo/health), bound to a tailnet IP, reached over Tailscale.
- Hybrid capture retained (VPS inbox courier). Repointed Phase-2 "disabled" tests to
  `approve_media`; undo error code is now `UNDO_FAILED`.
- Added `tests/test_organize.py` (12 tests).

### How to Verify

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -c "from second_brain import mcp_http_server"
```

### Verification Result

```text
Ran 54 tests in ~4s
OK
```

The HTTP MCP server registers 6 tools; transport `streamable-http` confirmed valid.

### Known Gaps

- Not yet deployed: Tailscale on the VPS, Mac-side Core launchd service, remote MCP
  registration with Hermes. See `docs/PHASE_3_PLAN.md` §9.
- Wikilink/backlink rewriting on move is out of scope (file move only).

## Phase 2 - First Write Capability (capture_note)

Date: 2026-06-17
Status: code complete and tested; VPS deployment + git inbox courier pending

### Completed

- Added `TIMEZONE` and `VAULT_GIT_SYNC` config + `.env.example` entries.
- `src/second_brain/vault/sensitivity.py`: sensitive-content detection.
- `src/second_brain/vault/writer.py`: slug, path-safety, frontmatter rendering
  (vault-style quoting), atomic write (temp + `os.replace`), content hashing.
- `src/second_brain/jobs/capture.py`: `capture_note` (validate, sensitivity, write,
  record `jobs`/`notes`/`operations`, idempotency dedupe) and `undo_capture`
  (hash-guarded delete, no double-undo).
- Dispatcher now takes `config`, routes `capture_note`/`undo_operation`, and passes
  an undo payload + target into the audit row (`ExecOutcome`).
- Enabled `capture_note` and `undo_operation` capabilities (Path 1). `update_note`,
  `move_note`, `search_vault` stay disabled (Phase 3).
- MCP server exposes `second_brain_capture_note` and `second_brain_undo_capture`.
- Repointed the Phase 1B preflight + the Phase 1 tests' "disabled" assertions to
  `update_note` (still disabled). Added `tests/test_capture.py` (11 tests).

### How to Verify

```bash
python3 -m unittest discover -s tests
```

### Verification Result

```text
Ran 40 tests in ~3.3s
OK
```

Real stdio MCP run confirmed: a client captured a note (got an `operation_id`),
captured a sensitive note (non-revealing `private-*.md` filename, body not echoed),
and undid the first capture (file removed).

### Known Gaps

- Not yet deployed to the VPS; the git "inbox" courier + Mac mini ingest job are not
  built yet (needs a private GitHub inbox repo).
- `VAULT_GIT_SYNC` is a config flag only; the commit/push module is a later sub-step.
- `update_note` / `move_note` / `search_vault` remain disabled (Phase 3).

### Next Steps

- Create the private inbox repo; deploy the updated repo to the VPS; point
  `VAULT_PATH` at the inbox checkout; build the Mac mini ingest job; Telegram dry run.

## Phase 0 - Discovery and Repo Setup

Date: 2026-06-16
Status: completed for local foundation; real vault audit pending read-only copy

### Completed

- Created repository skeleton.
- Added config loading and validation.
- Added SQLite migration runner and initial schema.
- Added fake Obsidian vault fixture.
- Added read-only vault audit module.
- Added initial tests.
- Added documentation handoff files.
- Ran verification successfully.
- Generated fake vault audit report.

### Changed Files

- `README.md`
- `.env.example`
- `pyproject.toml`
- `migrations/0001_initial.sql`
- `src/second_brain/`
- `tests/`
- `docs/`

### How to Verify

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m second_brain.main
PYTHONPATH=src python3 -m second_brain.db.migrate
```

### Known Gaps

- Hermes is not installed or connected yet.
- Telegram bot is not configured yet.
- Real vault audit has not been run.
- HTTP API is not implemented yet.
- Production deployment is not configured yet.
- Git repository initialization is pending because the sandbox denied creating `.git`; files are otherwise created and verified.

### Next Phase Handoff

- Ask Andri for a read-only vault copy if real vault audit is desired.
- Prepare Phase 1 Hermes Foundation after Phase 0 gate passes.
- Phase 1 needs Telegram bot token, authorized Telegram user ID, and Hermes installation approach.

## Phase 1A - Hermes Foundation Local

Date: 2026-06-16
Status: completed for local foundation; live Hermes/Telegram pending credentials and network install

### Completed

- Added Phase 1 environment variables to `.env.example`.
- Added gateway-enabled config validation.
- Added initial Capability Registry.
- Seeded safe/default capabilities through migration runner.
- Added tool-call audit logging.
- Added local tool dispatcher.
- Enabled safe mock/status tools: `health_check`, `job_status`, `sync_status`.
- Registered but disabled write/search tools for later phases.
- Added tests for config, seeded capabilities, disabled capability rejection, and audit rows.

### Changed Files

- `.env.example`
- `README.md`
- `src/second_brain/config.py`
- `src/second_brain/db/migrate.py`
- `src/second_brain/tools/`
- `src/second_brain/audit/tool_audit.py`
- `tests/`
- `docs/`

### How to Verify

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m second_brain.main
PYTHONPATH=src python3 -m second_brain.db.migrate
```

### Verification Result

```text
Ran 10 tests in 0.043s
OK
```

### Known Gaps

- Hermes is not installed or connected yet.
- Telegram bot token and Telegram user ID have not been provided.
- No live gateway test has been run.
- No HTTP API exists yet.
- Write tools are intentionally disabled.

### Next Phase Handoff

- Install Hermes after network permission and credential plan are confirmed.
- Configure Telegram gateway locally with secrets kept out of git.
- Keep enabled Second Brain tools limited to `health_check`, `job_status`, and `sync_status`.

## Phase 1B - Live Hermes and Telegram Preflight

Date: 2026-06-16
Status: preflight completed; live gateway blocked by missing Hermes install and credentials

### Completed

- Added Phase 1B preflight module.
- Added CLI entrypoint: `PYTHONPATH=src python3 -m second_brain.preflight`.
- Preflight checks Hermes command availability.
- Preflight checks gateway enabled flag, Telegram token, and allowlist.
- Preflight verifies safe tools are enabled.
- Preflight verifies write tool `capture_note` is still disabled.
- Added tests for blocked preflight and mocked ready preflight.

### Changed Files

- `src/second_brain/preflight.py`
- `src/second_brain/tools/preflight.py`
- `tests/test_preflight.py`
- `docs/`

### How to Verify

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m second_brain.preflight
```

### Verification Result

```text
Ran 12 tests in 0.044s
OK

Ready for live gateway: false
hermes_installed: blocked
gateway_enabled: blocked
telegram_token_present: blocked
telegram_allowlist_present: blocked
health_check_tool: ok
write_tools_disabled: ok
```

### Known Gaps

- Hermes is not installed locally.
- Telegram bot token is not configured.
- Telegram user ID allowlist is not configured.
- Model provider/API key is not configured.
- Live `hermes gateway` has not been run.
- Automatic Hermes installer execution was not run because it is a remote shell installer with persistent home-directory changes.

### Next Phase Handoff

- Install Hermes using official installer after network/home-write permission is approved.
- Alternatively, run the official installer manually in Terminal and then rerun preflight.
- Configure `.env` locally with Telegram token and allowlist.
- Run preflight again.
- Start `hermes gateway` only after preflight is ready.

## Phase 1B (continued) - HTTP Core API

Date: 2026-06-16
Status: code-side complete; live gateway still pending Hermes install and credentials

### Completed

- Added local-only HTTP Core API: `src/second_brain/server.py`.
- Routes: `GET /health` (public), `GET /tools` (bearer), `POST /tools/call` (bearer).
- Bearer-token auth against `HERMES_INTERNAL_TOOL_TOKEN` using constant-time compare.
- Loopback-only bind; refuses non-loopback hosts.
- Reuses `LocalToolDispatcher`, capability checks, and audit logging.
- Added `core_url_local` check to Phase 1B preflight.
- Added `tests/test_server.py` (pure handler tests + live HTTP smoke tests).
- Added `docs/GO_LIVE.md` runbook and updated API/README/Hermes setup docs.

### Changed Files

- `src/second_brain/server.py`
- `src/second_brain/tools/preflight.py`
- `tests/test_server.py`
- `docs/API.md`
- `docs/HERMES_SETUP.md`
- `docs/GO_LIVE.md`
- `README.md`
- `docs/DECISIONS.md`
- `docs/PHASE_1_CHECKLIST.md`
- `docs/AI_HANDOFF.md`

### How to Verify

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m second_brain.server
PYTHONPATH=src python3 -m second_brain.preflight
```

### Verification Result

```text
Ran 25 tests in ~2.8s
OK
```

Live curl smoke test confirmed: `/health` public, `/tools` and `/tools/call`
require the bearer token, `health_check` succeeds, `capture_note` is rejected,
and both calls are recorded in the `operations` audit table.

### Known Gaps

- Hermes is still not installed locally.
- Telegram token, user ID allowlist, and model provider/API key not yet provided.
- Live `hermes gateway` dry run not yet run.
- Write tools intentionally still disabled.

## Phase 1B (live) - Hermes installed + Telegram gateway up

Date: 2026-06-16
Status: live gateway running; Second Brain MCP integration built, pending registration

### Completed

- Installed Hermes Agent v0.16.0 (`~/.local/bin/hermes`, PATH via `~/.zprofile`).
- Quick Setup (Nous Portal free OAuth); default model `stepfun/step-3.7-flash:free`; local terminal backend.
- Telegram bot "Second Brain" connected; allowlist = user ID 291546901; home channel set.
- Telegram dry run succeeded (bot replies, language switch works).
- Discovered Hermes integrates tools via MCP (not REST), so added a stdio MCP server.
- Added `src/second_brain/mcp_server.py` (FastMCP) wrapping the dispatcher; exposes
  `second_brain_health_check`, `second_brain_job_status`, `second_brain_sync_status`.
- Lazy config/migration init so importing the module has no side effects.
- Added `tests/test_mcp_server.py`; added optional `mcp` dependency to `pyproject.toml`.
- Added Hermes MCP registration steps to `docs/GO_LIVE.md` and MCP contract to `docs/API.md`.

### How to Verify

```bash
pip install -e ".[mcp]"
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m second_brain.mcp_server
```

### Verification Result

```text
Ran 29 tests in ~2.8s
OK
```

Real stdio MCP handshake confirmed: a client initializes, lists the 3 safe tools,
and `second_brain_health_check` returns ok with an audit `operation_id`. Disabled
capabilities (e.g. `capture_note`) return `CAPABILITY_REJECTED`.

### Registration + End-to-End Verification

- Registered: `hermes mcp add second-brain --command ~/Projects/hermes-second-brain/run_mcp.sh` (3 tools enabled, saved to `~/.hermes/config.yaml`).
- Verified via `hermes` terminal chat: Hermes called `second_brain_health_check` and returned `ok` (status ok, service `second-brain-core`, audit `operation_id`). Full chain Telegram-agent → MCP → dispatcher → capability + audit works.

### Known Gaps

- `hermes gateway` (Telegram) times out on connect after 30s even though token (getMe), IPv4, and IPv6 to api.telegram.org are all healthy. `getWebhookInfo` returns `504 Gateway Timeout` — i.e. Telegram's own backend is degraded for this bot's management methods. This is a Telegram/Hermes-side runtime issue, not the Second Brain code. Workaround: use `hermes` terminal chat. To revisit: retry later or set up fresh on the VPS with a new token.
- Bot token was exposed once in chat; revoke via BotFather `/revoke` at VPS deploy time.
- Write tools intentionally still disabled.
