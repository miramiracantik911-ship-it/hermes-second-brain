# Hermes Setup

Status: prepared, not installed by this repo yet.

## Install Status

The installer script was inspected from the official Hermes URL, but it was not executed by Codex because it is a remote shell installer that makes persistent changes in the user home directory.

To continue live Phase 1B, Andri can either run the official installer manually in Terminal or explicitly approve running it with that risk understood.

## Official Commands to Verify During Live Setup

The Hermes docs describe these commands:

```bash
hermes
hermes setup
hermes model
hermes tools
hermes gateway
hermes doctor
```

Official installer reference:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

Safer install review flow:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/hermes-install.sh
less /tmp/hermes-install.sh
bash /tmp/hermes-install.sh --skip-setup
```

Use `--skip-setup` if you want installation first and interactive configuration later.

## Local Setup Recommendation

Use local Mac dev first, then repeat a documented setup on VPS.

Phase 1A does not require live Hermes. It prepares:

- Gateway config variables.
- Capability Registry.
- Safe status/mock tools.
- Audit logging for tool calls.

## Required Secrets for Live Gateway

Do not commit these:

```text
TELEGRAM_BOT_TOKEN=
HERMES_GATEWAY_ALLOWED_USER_IDS=
AI_PROVIDER_API_KEY=
```

Keep them in `.env` or Hermes' own local secret/config storage.

## Telegram Gateway Checklist

1. Create bot with BotFather.
1. Put token in local `.env`, never in docs.
1. Get Andri's Telegram user ID.
1. Set `HERMES_GATEWAY_ENABLED=true`.
1. Set `HERMES_GATEWAY_ALLOWED_USER_IDS=<andri_user_id>`.
1. Start Hermes gateway.
1. Send test message from authorized Telegram account.
1. Confirm no write tools are enabled.

## Second Brain Core HTTP Integration

Start the local Core API in its own terminal before the gateway:

```bash
PYTHONPATH=src python3 -m second_brain.server
# Second Brain Core listening on http://127.0.0.1:8787
```

Point Hermes' Second Brain tool at the loopback endpoint:

- URL: `http://127.0.0.1:8787/tools/call`
- Header: `Authorization: Bearer <HERMES_INTERNAL_TOOL_TOKEN>`
- Body: `{ "tool": "health_check", "payload": {}, "user_id": "hermes:gateway" }`

The server is loopback-only and refuses non-loopback hosts. Only
`health_check`, `job_status`, and `sync_status` are enabled; write tools return
`CAPABILITY_REJECTED`. Full contract in `docs/API.md`.

## Phase 1B Preflight

Before starting the live gateway, run:

```bash
PYTHONPATH=src python3 -m second_brain.preflight
```

Current expected result before credentials are configured:

```text
Ready for live gateway: false
hermes_installed: blocked
gateway_enabled: blocked
telegram_token_present: blocked
telegram_allowlist_present: blocked
core_url_local: ok
health_check_tool: ok
write_tools_disabled: ok
```

The live gateway should only be started after the blocked items are fixed.

## Second Brain Tool Boundary

Allowed during Phase 1:

- `health_check`
- `job_status`
- `sync_status`

Not allowed yet:

- `capture_note`
- `search_vault`
- `update_note`
- `move_note`
- `undo_operation`

These tools are registered but disabled until their implementation phases.
