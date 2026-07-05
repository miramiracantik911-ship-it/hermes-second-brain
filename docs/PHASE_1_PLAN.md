# Phase 1 Plan - Hermes Foundation

Status: planned  
Date: 2026-06-16  
Repo: `/Users/andri/projects/hermes-second-brain`

## 1. Goal

Phase 1 establishes Hermes as the agent shell without giving it access to the production Obsidian vault.

By the end of Phase 1:

1. Hermes installation approach is documented and verified.
1. Telegram gateway configuration is prepared safely.
1. Authorized Telegram user allowlist is defined.
1. First local custom tool path is designed.
1. Internal auth token pattern is in place.
1. Capability Registry has initial records and tests.
1. Every tool call can be audited, even if the tool is still mocked.

## 2. Safety Boundary

Phase 1 must not:

- Write to the real Obsidian vault.
- Store Telegram bot token in git.
- Store AI provider API key in git.
- Expose local tool API publicly.
- Give Hermes shell access to the production vault.
- Enable destructive, financial, email, cloud, or external action tools.

Phase 1 may:

- Install or prepare Hermes in dev.
- Configure Telegram gateway using local secrets.
- Test Hermes against mock or read-only tools.
- Store non-secret capability definitions in SQLite.
- Log safe audit metadata.

## 3. Inputs Needed from Andri

| Input | Needed for | Required now? |
| --- | --- | --- |
| Telegram bot token from BotFather | Real Telegram gateway test | Yes, before live gateway test |
| Telegram user ID | Allowlist | Yes, before live gateway test |
| Preferred AI provider for Hermes | Hermes model setup | Yes, before model test |
| API key for chosen provider | Hermes response test | Yes, but never committed |
| Decision: local Mac dev or VPS first | Installation target | Recommended before install |
| Permission to use network install | Hermes installer | Required when installation begins |

If these are not available yet, Phase 1 can still complete the code-side foundation using mock Hermes calls.

## 4. Recommended Execution Order

### Step 1.1 - Resolve Phase 0 Git Blocker

Current issue: `git init` was denied by the sandbox when creating `.git`.

Plan:

1. Ask Andri to run `git init` manually in Terminal, or retry when filesystem permission allows it.
1. Keep working even if git is pending, but mark it as an operational gap.

Verification:

```bash
git status
```

### Step 1.2 - Confirm Hermes Installation Strategy

Hermes official docs currently describe:

- CLI entrypoint with `hermes`.
- Model selection with `hermes model`.
- Tool configuration with `hermes tools`.
- Messaging gateway with `hermes gateway`.
- Setup wizard with `hermes setup`.

Decision needed:

| Option | Use when | Recommendation |
| --- | --- | --- |
| Local Mac dev first | We want quick iteration before VPS | Recommended |
| VPS dev first | We want always-on behavior immediately | Later, after local config is clear |
| Docker/systemd only | We want production-like setup | Phase 2 or deployment hardening |

Phase 1 recommendation: **local Mac dev first**, then document the same setup for VPS.

### Step 1.3 - Add Hermes Configuration Documentation

Create:

```text
docs/HERMES_SETUP.md
```

It should include:

- Install command reference.
- Expected commands: `hermes`, `hermes setup`, `hermes model`, `hermes tools`, `hermes gateway`, `hermes doctor`.
- Where local secrets should live.
- What must not be committed.
- Telegram setup checklist.
- Known security boundaries.

No real token goes into the file.

### Step 1.4 - Extend Environment Configuration

Add Phase 1 variables to `.env.example`:

```text
TELEGRAM_BOT_TOKEN=
HERMES_GATEWAY_ENABLED=false
HERMES_GATEWAY_ALLOWED_USER_IDS=
SECOND_BRAIN_CORE_URL=http://127.0.0.1:8787
```

Update config validation:

- In production, Telegram allowlist is required.
- In production, default internal token is rejected.
- In development, empty Telegram token is allowed unless gateway is enabled.
- If gateway is enabled, Telegram token and allowed user IDs are required.

Verification:

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m second_brain.main
```

### Step 1.5 - Implement Initial Capability Registry

Create a small module:

```text
src/second_brain/tools/capabilities.py
```

Initial capabilities:

| Capability | Risk | Enabled | Notes |
| --- | --- | --- | --- |
| `health_check` | L0 | true | Safe mock tool for Hermes connection test. |
| `job_status` | L1 | true | Can return mock/no jobs for now. |
| `sync_status` | L1 | true | Can return unknown/not configured. |
| `capture_note` | L2 | false | Registered but disabled until Phase 2 write logic. |
| `search_vault` | L1 | false | Registered but disabled until Phase 3. |
| `update_note` | L2 | false | Disabled. |
| `move_note` | L2 | false | Disabled. |
| `undo_operation` | L2 | false | Disabled. |

Database work:

- Seed `capabilities` table.
- Add tests that disabled capabilities cannot be called.

Verification:

```bash
python3 -m unittest discover -s tests
```

### Step 1.6 - Add Audit Logging for Tool Calls

Create:

```text
src/second_brain/audit/tool_audit.py
```

Each tool call should record:

- User ID.
- Tool name.
- Risk level.
- Target type.
- Status.
- Timestamp.
- Safe error code if failed.

No prompt body, token, or private note content should be logged.

Verification:

- Unit test inserts successful audit event.
- Unit test inserts rejected/disabled tool event.
- Database contains operation row.

### Step 1.7 - Add Minimal Local Tool API Stub

Phase 1 does not need full FastAPI yet, but we need a clear integration target.

Two acceptable approaches:

| Approach | Pros | Cons |
| --- | --- | --- |
| Python function adapter | No new dependency, fast tests | Hermes cannot call it over HTTP yet |
| Minimal HTTP API | Closer to Hermes integration | Adds FastAPI/uvicorn dependency |

Recommendation:

- Start with Python function adapter in Phase 1.
- Add FastAPI only if Hermes tool integration requires HTTP immediately.

Initial callable:

```json
{
  "tool": "health_check",
  "response": {
    "status": "ok",
    "service": "second-brain-core",
    "phase": "1"
  }
}
```

### Step 1.8 - Telegram Gateway Dry Run

Only after token and user ID are available:

1. Configure Telegram bot token locally.
1. Add Andri's Telegram user ID to allowlist.
1. Start Hermes gateway.
1. Send a test message from Andri.
1. Confirm unauthorized user is rejected or ignored.

Expected result:

- Hermes receives message.
- Hermes can answer with normal model response.
- Hermes does not yet write to vault.
- Any Second Brain tool call is limited to `health_check` or mock status.

### Step 1.9 - Documentation Gate

Update:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/SECURITY.md`
- `docs/SETUP.md`
- `docs/TESTING.md`
- `docs/DECISIONS.md`
- `docs/PHASE_LOG.md`
- `docs/AI_HANDOFF.md`

Add:

- `docs/HERMES_SETUP.md`
- `docs/PHASE_1_CHECKLIST.md`

## 5. Phase 1 Definition of Done

Phase 1 is done when:

1. Hermes installation strategy is documented.
1. Telegram gateway setup steps are documented.
1. `.env.example` contains Phase 1 variables without real secrets.
1. Config validation supports gateway-enabled checks.
1. Capability Registry exists with initial capabilities.
1. Disabled tools are rejected.
1. Tool call audit logging exists.
1. `health_check` mock tool can be called locally.
1. Test suite passes.
1. Documentation handoff is updated.
1. If token/user ID are provided, Hermes Telegram dry run succeeds.

If token/user ID are not provided, Phase 1 can be marked:

```text
completed for local foundation; live Telegram gateway pending credentials
```

## 6. Commands Expected During Phase 1

Local verification:

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m second_brain.main
PYTHONPATH=src python3 -m second_brain.db.migrate
```

Hermes verification, after installation:

```bash
hermes doctor
hermes model
hermes tools
hermes gateway
```

## 7. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Telegram token leaks | Keep token in `.env`, never docs or git. |
| Hermes gets too much access | Enable only mock/status tools in Phase 1. |
| Tool call bypasses permissions | All calls go through Capability Registry check. |
| Logs contain private data | Audit metadata only; no full prompt or note body. |
| Phase 1 drifts into Phase 2 | Do not implement vault writes yet. |
| Network installer changes behavior | Verify official Hermes docs before install and record exact version/commit if possible. |

## 8. Recommendation

We can continue to Phase 1 now, but I recommend splitting it into two passes:

1. **Phase 1A - Local foundation:** env, capability registry, audit logging, mock `health_check`, docs, tests. This can be done immediately.
1. **Phase 1B - Live Hermes/Telegram:** install Hermes, configure Telegram gateway, test allowlist. This requires Telegram token, user ID, chosen model provider, API key, and network permission.

This keeps progress moving without putting credentials or the real vault at risk.

## 9. Sources Checked

- Hermes GitHub repository: https://github.com/NousResearch/hermes-agent
- Hermes Messaging Gateway docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging
- Hermes Security docs: https://hermes-agent.nousresearch.com/docs/user-guide/security
- Hermes Programmatic Integration docs: https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
