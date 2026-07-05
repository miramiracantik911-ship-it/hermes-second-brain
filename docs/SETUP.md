# Setup

## Requirements

- Python 3.11 or newer.
- No required external Python dependency for Phase 0.

## Local Setup

From the repository root:

```bash
cp .env.example .env
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m second_brain.main
PYTHONPATH=src python3 -m second_brain.db.migrate
PYTHONPATH=src python3 -m second_brain.preflight
```

## Environment Variables

| Variable | Required | Notes |
| --- | --- | --- |
| `APP_ENV` | Yes | `development`, `test`, or `production`. |
| `AUTHORIZED_TELEGRAM_USER_IDS` | Production | Comma-separated Telegram user IDs. |
| `VAULT_PATH` | Yes | Use `tests/fixtures/vault` in Phase 0. |
| `DATABASE_URL` | Yes | Only `sqlite:///` is supported in Phase 0. |
| `ATTACHMENT_TEMP_DIR` | Yes | Temporary media path. |
| `LOG_LEVEL` | Yes | `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |
| `HERMES_INTERNAL_TOOL_TOKEN` | Production | Must not use default value in production. |
| `TELEGRAM_BOT_TOKEN` | Gateway only | Required only when Hermes gateway is enabled. |
| `HERMES_GATEWAY_ENABLED` | Yes | `false` by default in local dev. |
| `HERMES_GATEWAY_ALLOWED_USER_IDS` | Gateway only | Required when gateway is enabled. |
| `SECOND_BRAIN_CORE_URL` | Yes | Local target for future Hermes tool calls. |

## Troubleshooting

- If imports fail, run commands with `PYTHONPATH=src`.
- If config fails, confirm `VAULT_PATH` exists.
- If migration fails, remove the dev database and rerun migration.
- If gateway config fails, keep `HERMES_GATEWAY_ENABLED=false` until token and allowlist are available.
- If preflight says Hermes is missing, install Hermes before Phase 1B live gateway testing.
