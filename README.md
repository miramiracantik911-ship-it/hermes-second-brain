# Hermes Second Brain

Hermes Second Brain adalah fondasi personal AI hub berbasis Hermes, dengan Obsidian Second Brain sebagai kapabilitas pertama: capture, search, dan organize catatan Obsidian dari Telegram lewat Hermes Agent (MCP).

Status saat ini: **Live — Phase 3 selesai.** Berjalan lokal di satu mesin (Mac mini) end-to-end: capture, search, dan organize (move/update/undo) langsung ke vault Obsidian, dikendalikan dari Telegram.

## Fitur

- **Capture** — simpan catatan/link ke Inbox sebagai Markdown (atomik, anti-dobel, reversible).
- **Search** — full-text search seluruh vault (SQLite FTS5); note sensitif dicari via judul/tag saja, body tidak diindeks.
- **Organize** — `move_note` (pindah antar folder PARA) & `update_note` (append/replace), atomik + hash-guarded.
- **Undo** — batalkan capture/move/update terakhir lewat `operation_id`.
- **Aman** — capability registry per-tool, audit log, deteksi note sensitif (`#private`/kata kunci rahasia), path-safe.

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

## MCP tools (live)

Terdaftar di Hermes sebagai MCP stdio lokal (`second_brain.mcp_server`):

- `health_check`, `job_status`, `sync_status`
- `capture_note` — tulis catatan ke Inbox
- `search_vault`, `get_note` — cari & baca catatan
- `move_note`, `update_note` — pindah & edit catatan
- `undo` — batalkan operasi terakhir

Bangun/refresh index pencarian kapan saja: `PYTHONPATH=src python3 -m second_brain.reindex`.

## Read Next

- `docs/AI_HANDOFF.md`
- `docs/ARCHITECTURE.md`
- `docs/HERMES_SETUP.md`
- `docs/SETUP.md`
- `docs/TESTING.md`
- `docs/SECURITY.md`
