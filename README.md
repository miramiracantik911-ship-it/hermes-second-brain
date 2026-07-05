# Hermes Second Brain

Hermes Second Brain adalah fondasi personal AI hub berbasis Hermes, dengan Obsidian Second Brain sebagai kapabilitas pertama: capture, search, dan organize catatan Obsidian dari Telegram lewat Hermes Agent (MCP).

Status saat ini: **Phase 1A - Hermes Foundation Local**.

## Prasyarat

- Mesin yang menyala 24/7 (Mac mini, home server, atau VPS) untuk menjalankan Hermes + Second Brain Core.
- [Obsidian](https://obsidian.md) dengan sebuah vault Markdown.
- [Hermes Agent](https://hermes-agent.nousresearch.com) terpasang dan berjalan (lihat [docs/HERMES_SETUP.md](docs/HERMES_SETUP.md)).
- API key LLM (mis. Anthropic) untuk Hermes.
- Bot Telegram (token dari @BotFather) sebagai antarmuka chat.
- Python 3.11+.

## Install

```bash
git clone https://github.com/andrihakim146/hermes-second-brain.git
cd hermes-second-brain
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[mcp]"
cp .env.example .env   # lalu isi token & path vault kamu
python3 -m unittest discover -s tests
```

Panduan lengkap end-to-end (termasuk setup Hermes, Telegram, dan go-live ke vault
produksi) ada di [docs/REPLICATION_GUIDE.md](docs/REPLICATION_GUIDE.md).

## Architecture in One Minute

```text
Telegram -> Hermes Agent -> Capability Gateway -> Second Brain Core -> Obsidian Vault
```

- Hermes menangani percakapan, session, model routing, scheduler, dan tool selection.
- Capability Gateway membatasi akses dengan permission L0-L4.
- Second Brain Core menangani job, audit, database, konflik, index, dan operasi vault.
- Vault Markdown tetap menjadi source of truth untuk catatan.

## Safety Boundary

Phase 0 tidak menyentuh vault produksi. Semua test memakai fake vault di:

```text
tests/fixtures/vault
```

Vault asli hanya boleh diaudit dari salinan read-only setelah Andri memberi path dan izin eksplisit.

## Quick Start

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m second_brain.main
PYTHONPATH=src python3 -m second_brain.db.migrate
PYTHONPATH=src python3 -m second_brain.preflight
PYTHONPATH=src python3 -m second_brain.server
PYTHONPATH=src python3 -m second_brain.mcp_server   # needs: pip install -e ".[mcp]"
```

`second_brain.server` starts the local-only HTTP Core API on
`SECOND_BRAIN_CORE_URL` (default `http://127.0.0.1:8787`). `second_brain.mcp_server`
is the stdio MCP server that Hermes connects to (Hermes uses MCP, not REST). Both
wrap the same dispatcher with capability checks + audit. See `docs/API.md` and
`docs/GO_LIVE.md`.

## Current Phase Output

- Config loader and validation.
- SQLite migration foundation.
- Fake Obsidian vault fixture.
- Read-only vault audit module.
- Capability Registry with safe default capabilities.
- Local tool dispatcher with `health_check`, `job_status`, and `sync_status`.
- Local-only HTTP Core API (`second_brain.server`) with bearer-token auth.
- Tool-call audit logging.
- Phase documentation for programmer and AI handoff.

## Read Next

- `docs/AI_HANDOFF.md`
- `docs/ARCHITECTURE.md`
- `docs/HERMES_SETUP.md`
- `docs/SETUP.md`
- `docs/TESTING.md`
- `docs/SECURITY.md`
