# AI Handoff

## Current Status

Phase 3 code is complete in `/Users/andri/projects/hermes-second-brain`: the Organize
tools `search_vault`, `get_note`, `move_note`, `update_note` (+ unified undo) operate
on the full vault, exposed via `mcp_http_server` (FastMCP streamable-http) for the
Mac-side Core reached over Tailscale. Phase 2 (capture) is deployed and live on the VPS
(`103.37.124.108`): Telegram → Hermes (Claude Sonnet 4.6) → MCP capture → GitHub inbox
→ Mac mini courier → Obsidian vault. Phase 3 deployment (Tailscale VPS join + Mac-side
Core launchd + remote MCP registration) is pending — see `docs/PHASE_3_PLAN.md`.

The repo contains config loading, SQLite migration, fake vault fixture, read-only vault
audit, Capability Registry, local tool dispatcher, audit logging, Phase 1B preflight,
the HTTP Core API (`second_brain.server`), the stdio MCP server (`second_brain.mcp_server`),
the Phase 2 vault writer/sensitivity/capture modules, tests, and documentation.
Verification passes (40 tests). The `mcp` package is the only non-stdlib dependency
(MCP server + Hermes client). Phase 2 is not yet deployed to the VPS, and the git
"inbox" courier (Mac mini ingest) that bridges captures to Obsidian Sync is not built
yet — see `docs/PHASE_2_PLAN.md`.

## Architecture Summary

Target architecture:

```text
Telegram -> Hermes Agent -> Capability Gateway -> Second Brain Core -> Obsidian Vault
```

Hermes is the agent shell. Second Brain Core owns vault writes. Capability Gateway enforces permissions.

## Safety Rules

- Do not write to the real Obsidian vault.
- Do not add secrets to repo.
- Use `tests/fixtures/vault` for tests.
- Treat real vault access as read-only unless Andri explicitly approves otherwise.
- Sensitive/private notes must not be sent to AI or indexed by body.
- Keep write tools disabled until their phase.
- Do not enable Hermes gateway unless Telegram token and allowlist are provided.

## How to Run

```bash
PYTHONPATH=src python3 -m second_brain.main
PYTHONPATH=src python3 -m second_brain.db.migrate
PYTHONPATH=src python3 -m second_brain.preflight
PYTHONPATH=src python3 -m second_brain.server
```

## How to Test

```bash
python3 -m unittest discover -s tests
```

## Important Files

- `src/second_brain/config.py`
- `src/second_brain/db/migrate.py`
- `src/second_brain/audit/vault_audit.py`
- `src/second_brain/audit/tool_audit.py`
- `src/second_brain/tools/capabilities.py`
- `src/second_brain/tools/dispatcher.py`
- `src/second_brain/tools/preflight.py`
- `src/second_brain/preflight.py`
- `src/second_brain/server.py`
- `src/second_brain/mcp_server.py`
- `src/second_brain/vault/writer.py`
- `src/second_brain/vault/sensitivity.py`
- `src/second_brain/vault/reader.py`
- `src/second_brain/vault/search.py`
- `src/second_brain/vault/organize.py`
- `src/second_brain/jobs/capture.py`
- `src/second_brain/jobs/undo.py`
- `src/second_brain/mcp_http_server.py`
- `migrations/0001_initial.sql`
- `tests/fixtures/vault/`
- `docs/PHASE_LOG.md`
- `docs/SECURITY.md`

## Known Gaps

- No Hermes runtime connection; `hermes` is not installed or not in PATH.
- No Telegram gateway.
- HTTP Core API exists (stdlib `http.server`, loopback-only); no FastAPI yet by design.
- No write tool implementation.
- No real vault audit report because no read-only vault copy has been provided.
- Git initialization is pending; `git init` was denied when creating `.git` in this sandbox.
- Hermes installer has not been executed. It requires manual Terminal install or explicit approval because it is a remote shell installer that changes the home directory.

## Next Recommended Step

Follow `docs/GO_LIVE.md`: install Hermes, configure Telegram credentials outside git, start the Core API (`second_brain.server`), rerun `PYTHONPATH=src python3 -m second_brain.preflight`, and start the live gateway only after preflight reports ready.

## Do Not Touch

- Do not modify any real Obsidian vault.
- Do not store Telegram tokens or AI API keys.
- Do not start live gateway until preflight passes.
- Do not enable write tools during Phase 1B.
