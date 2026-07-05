# Phase 1 Checklist

## Phase 1A - Local Foundation

- [x] `.env.example` has Hermes/Telegram variables.
- [x] Gateway-enabled config validates token and allowlist.
- [x] Capability Registry exists.
- [x] Initial capabilities are seeded.
- [x] Safe mock/status tools are enabled.
- [x] Write/search tools are registered but disabled.
- [x] Disabled tools are rejected.
- [x] Tool-call audit logging exists.
- [x] Local `health_check` can be dispatched.
- [x] Test suite passes.
- [x] Documentation handoff updated.

## Phase 1B - Live Hermes and Telegram

- [x] Phase 1B preflight command exists.
- [x] Preflight checks safe tools and blocked live requirements.
- [x] Local-only HTTP Core API exists (`GET /health`, `GET /tools`, `POST /tools/call`).
- [x] Core API requires bearer token and binds loopback-only.
- [x] Core API reuses dispatcher, capability checks, and audit logging.
- [x] Preflight verifies `SECOND_BRAIN_CORE_URL` is loopback (`core_url_local`).
- [x] Server tests pass (handler + live HTTP smoke).
- [x] Go-live runbook documented (`docs/GO_LIVE.md`).
- [ ] Hermes installed locally.
- [ ] `hermes doctor` passes.
- [ ] Model provider selected.
- [ ] Provider API key configured outside git.
- [ ] Telegram bot token configured outside git.
- [ ] Telegram user ID allowlist configured.
- [ ] Hermes gateway starts.
- [ ] Authorized Telegram user can send a test message.
- [ ] Unauthorized user is rejected or ignored.
- [ ] Hermes can call only safe/mock Second Brain tools.

## Blockers for Phase 1B

- `hermes` command is not installed or not in PATH.
- Hermes installer execution requires manual Terminal install or explicit approval.
- Telegram bot token is not provided yet.
- Telegram user ID is not provided yet.
- Model provider/API key is not provided yet.
- Network install permission is needed before installing Hermes.
