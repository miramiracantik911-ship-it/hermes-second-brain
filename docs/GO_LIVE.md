# Go Live - Phase 1B Live Gateway

This is the one-page runbook to take Hermes + Telegram live once credentials are
ready. The code side (HTTP Core API, capability registry, audit, preflight) is
already built; the remaining steps are install + secrets + a dry run.

## Prerequisites to Collect

| Item | Where from | Notes |
| --- | --- | --- |
| Telegram bot token | BotFather | Never commit. |
| Telegram user ID | @userinfobot or similar | Your own ID for the allowlist. |
| AI model provider | Decision | e.g. the provider Hermes is configured for. |
| Provider API key | Provider dashboard | Never commit; store in Hermes/local secret. |
| Network/home-write permission | You | Needed to run the Hermes installer. |

## Step 1 - Install Hermes

Review then install (see `docs/HERMES_SETUP.md` for the safer review flow):

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/hermes-install.sh
less /tmp/hermes-install.sh
bash /tmp/hermes-install.sh
hermes doctor
```

## Step 2 - Configure Local Secrets (outside git)

Create a local `.env` (already in `.gitignore`) from `.env.example`:

```text
APP_ENV=development
HERMES_INTERNAL_TOOL_TOKEN=<generate-a-strong-random-token>
TELEGRAM_BOT_TOKEN=<from-botfather>
HERMES_GATEWAY_ENABLED=true
HERMES_GATEWAY_ALLOWED_USER_IDS=<your-telegram-user-id>
SECOND_BRAIN_CORE_URL=http://127.0.0.1:8787
```

Configure the model provider + API key in Hermes' own config (not in this repo).

## Step 3 - Start the Core API

```bash
PYTHONPATH=src python3 -m second_brain.server
```

Point the Hermes Second Brain tool at `http://127.0.0.1:8787/tools/call` with the
`Authorization: Bearer <HERMES_INTERNAL_TOOL_TOKEN>` header.

## Step 4 - Run Preflight (must be ready)

```bash
PYTHONPATH=src python3 -m second_brain.preflight
```

Proceed only when `Ready for live gateway: true` and every check is `ok`.

## Step 5 - Telegram Dry Run

```bash
hermes gateway
```

1. Send a test message from your authorized Telegram account.
2. Confirm Hermes answers with a normal model response.
3. Confirm an unauthorized account is rejected or ignored.
4. Confirm the only Second Brain tools callable are `health_check`, `job_status`,
   `sync_status`; write tools must return `CAPABILITY_REJECTED`.
5. Confirm nothing writes to the real Obsidian vault.

## Step 6 - Wire Second Brain into Hermes (MCP)

Hermes connects to external tools over **MCP**, not plain REST, so the Second
Brain Core is exposed as a stdio MCP server: `second_brain.mcp_server`. It wraps
the same dispatcher (capability checks + audit) and exposes only the safe
read-only tools (`health_check`, `job_status`, `sync_status`).

Create a venv and install just the `mcp` package (no editable install needed —
the `run_mcp.sh` launcher sets `PYTHONPATH` for you):

```bash
cd ~/Projects/hermes-second-brain
python3 -m venv .venv
source .venv/bin/activate
pip install mcp
```

Register the launcher with Hermes (stdio):

```bash
hermes mcp add second-brain --command ~/Projects/hermes-second-brain/run_mcp.sh
```

If the CLI flags differ in your Hermes version, edit `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  second-brain:
    command: /Users/andri/Projects/hermes-second-brain/run_mcp.sh
```

Then verify and restart the gateway:

```bash
hermes mcp list
hermes gateway
```

In Telegram, ask Hermes to run a Second Brain health check. It should call the
`mcp-second-brain` toolset and any write attempt must be rejected.

## Deploying to a VPS (next)

The local build is complete and the MCP integration is verified via `hermes`
terminal chat. The Telegram gateway timed out locally because Telegram's backend
returned `504` for this bot's management methods (a Telegram/Hermes-side runtime
issue, not the code). The clean path is to run the gateway on the VPS:

1. Provision the VPS and clone the repo.
2. Install Hermes on the VPS (`docs/HERMES_SETUP.md`), run `hermes setup`.
3. Recreate the venv with Python 3.11 (uv works well):
   `uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python mcp`.
4. Create `.env` with a fresh `HERMES_INTERNAL_TOOL_TOKEN`.
5. Revoke the old Telegram bot token via BotFather `/revoke`, create a new one,
   and configure it with `hermes setup gateway` (allowlist = your user ID).
6. Register the MCP server: `hermes mcp add second-brain --command <repo>/run_mcp.sh`.
7. `hermes mcp list` → confirm enabled; run `hermes gateway` (install as a launchd/
   systemd service for always-on once the dry run passes).

If the gateway still times out on the VPS, it confirms a Hermes/Telegram issue
worth reporting upstream; the Second Brain tools still work through `hermes` chat.

### Telegram webhook mode (preferred on VPS)

Long polling (`getUpdates`) is what timed out locally (Telegram returned `504`
for the bot's management methods). Webhook mode flips the direction — Telegram
**pushes** updates to a public HTTPS endpoint — so it avoids `getUpdates`
entirely and is the recommended mode for an always-on VPS.

Requirements:

1. A domain pointing at the VPS (e.g. `hermes.example.com`).
2. Valid HTTPS. Telegram only delivers webhooks on ports `443`, `80`, `88`, or
   `8443` with a trusted cert. Easiest: front Hermes with **Caddy** (automatic
   Let's Encrypt) or nginx + certbot as a reverse proxy to Hermes' Telegram
   listener.
3. Firewall open on `443`.
4. Enable webhook mode in `hermes gateway setup` (choose webhook, provide the
   public URL). Confirm the exact wizard fields/flags at setup time, then run
   `hermes gateway` and send a test message.

Fallbacks if webhook is impractical: switch the front-end to another Hermes
platform (Discord, Slack, etc. — same MCP backend), or use `hermes` over SSH.

## Safety Reminders

- Do not commit `.env`, tokens, or API keys.
- Keep write tools disabled until their phase.
- Core API stays loopback-only.
- Real Obsidian vault remains untouched in Phase 1B.
