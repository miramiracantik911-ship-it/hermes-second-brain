# Security

## Current Safety Rules

- Do not connect Hermes to the production vault.
- Do not write to the real Obsidian vault.
- Do not commit `.env` or secrets.
- Do not process real sensitive notes with AI.
- Use only fake vault data until a read-only vault copy is explicitly provided.
- Keep `capture_note`, `search_vault`, `update_note`, `move_note`, and `undo_operation` disabled until their phases.
- Gateway tokens and AI provider keys must stay in local environment files, not docs.

## Permission Model

Future tools use levels L0-L4:

| Level | Meaning | Default |
| --- | --- | --- |
| L0 | Public read | Automatic. |
| L1 | Personal read | Automatic if authorized. |
| L2 | Reversible write | Allowed if policy passes. |
| L3 | External action | Requires approval. |
| L4 | Destructive, financial, or security action | Strong approval or forbidden. |

## Secret Handling

- Secrets stay outside the vault.
- Secrets are not logged.
- Secrets are not sent to AI prompts.
- `HERMES_INTERNAL_TOOL_TOKEN=dev-token-change-me` is forbidden in production.
- `TELEGRAM_BOT_TOKEN` is required only when `HERMES_GATEWAY_ENABLED=true`.

## Phase 1A Tool Safety

Only these local tools are enabled:

- `health_check`
- `job_status`
- `sync_status`

All write-capable tools are registered but disabled. Disabled tool calls are rejected and audited.

## Phase 1B Live Gateway Rule

Do not start `hermes gateway` until preflight confirms:

- Hermes is installed.
- Gateway is explicitly enabled.
- Telegram token is present in local config.
- Telegram allowlist is present.
- Safe tools are enabled.
- Write tools are still disabled.

## Sensitive Notes

Sensitive/private notes must not be sent to external AI, embedded, previewed, or indexed by body content.
