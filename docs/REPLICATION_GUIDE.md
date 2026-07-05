# Second Brain + Hermes — Panduan Duplikasi (Replication Guide)

> Satu dokumen untuk mereplikasi sistem "AI Second Brain via Telegram" dari nol.
> Baca bagian 1–6 untuk paham, lalu tempel **BUILD PROMPT** (bagian 8) ke coding-agent
> (Claude Code, Cursor, dsb.) untuk langsung membangun kodenya.

---

## 1. Apa yang dibangun

Asisten pribadi yang mengubah Obsidian vault menjadi "second brain" yang bisa
kamu perintah dari **Telegram** dalam bahasa natural. Kamu bisa:

- **Capture** — "catat ide ini" → tersimpan sebagai note Markdown di Inbox.
- **Search** — "cari catatan tentang X" → full-text search seluruh vault.
- **Organize** — "pindahkan catatan itu ke folder Projects", "tambahkan poin ini".
- **Undo** — membatalkan capture/move/update terakhir.

Semuanya berjalan **lokal** di satu mesin yang menyala 24/7 (mis. Mac mini),
langsung ke folder Obsidian di disk. Tidak perlu server cloud.

Prinsip metode: **PARA/CODE** (Inbox → Projects/Areas/Resources/Archives;
alur Capture → Organize → Distill → Express).

---

## 2. Arsitektur

```
Telegram  ->  Hermes Agent (LLM)  ->  MCP (stdio)  ->  Second Brain Core  ->  Obsidian Vault
                (Gemini/OpenAI/…)      tool calls        (dispatcher +           (~/Documents/…)
                                                          capability gate +
                                                          audit log)
```

- **Hermes Agent** (NousResearch) = "shell" agent: menerima chat Telegram, memanggil
  LLM, dan mengeksekusi tool lewat MCP. Ganti provider/model kapan saja (`hermes model`).
- **MCP server (stdio)** = jembatan tipis; mengekspos tool Core ke Hermes. **stdio lokal**
  dipilih karena paling stabil (MCP remote/HTTP sempat bikin gateway Hermes crash).
- **Second Brain Core** = otak logika: satu *dispatcher* yang merutekan setiap tool
  lewat *capability registry* (izin per-tool) dan menulis *audit log*, lalu menyentuh vault.
- **Obsidian Vault** = sumber kebenaran. Obsidian Sync menyebar perubahan ke device lain.

Kenapa satu mesin lokal (bukan VPS): tool search/move/update butuh **seluruh vault**,
yang hidup di disk lewat Obsidian Sync. Menaruh Hermes di mesin yang sama = Core jadi
MCP **stdio lokal** (stabil) dan tidak perlu mirror vault ke cloud (hindari konflik sync
+ tidak mengirim note sensitif keluar device).

---

## 3. Tech stack

| Bagian | Pilihan | Alasan |
|---|---|---|
| Bahasa | **Python 3.12** (stdlib saja + paket `mcp`) | minim dependensi, mudah audit |
| Penyimpanan meta | **SQLite** (WAL) + **FTS5** | zero-config, full-text search bawaan |
| MCP | **FastMCP** (`mcp.server.fastmcp`), transport **stdio** | didukung Hermes paling andal |
| Agent shell | **Hermes Agent** (NousResearch) | Telegram gateway + multi-provider LLM |
| Vault | **Obsidian** + Obsidian Sync | plain Markdown, portable |
| Host | Mesin nyala 24/7 (Mac mini) + **launchd** service | selalu on, auto-start |
| Front-end | **Telegram bot** | akses dari mana saja |

Dependensi non-stdlib **hanya** `mcp`. Semua sisanya stdlib Python.

---

## 4. Keputusan desain penting (jangan dilewati)

1. **Semua tulisan ke vault: atomik + path-safe + hash-guarded.** Tulis ke file temp
   lalu `os.replace`. Sebelum move/update, cek `content_hash` cocok (tolak kalau note
   berubah di luar). Setiap operasi menyimpan `operation_id` untuk **undo**.
2. **Capability registry.** Tiap tool punya flag enabled/disabled. Fitur fase berikutnya
   tetap *disabled* sampai gilirannya. Satu tool sengaja disabled sebagai uji "gerbang izin".
3. **Deteksi sensitif.** Note yang mengandung kata kunci rahasia (password, dsb.) atau
   marker `#private` → dapat **nama file non-revealing** (`private-<hash>.md`), body-nya
   **tidak diindeks** untuk search, dan tidak dikirim ke LLM.
4. **Audit log.** Setiap panggilan tool tercatat (tool, user, waktu, hasil) di SQLite.
5. **Idempotency.** Capture menerima `idempotency_key` (mis. message-id) untuk anti-dobel.
6. **stdio lokal, bukan MCP remote.** Satu MCP stdio lokal = konfigurasi paling stabil.

---

## 5. Struktur kode

```
second-brain/
├─ src/second_brain/
│  ├─ config.py            # AppConfig (dataclass) + load_config() + validate()
│  ├─ db/migrate.py        # connect() + apply_migrations() (skip dotfile ._*.sql)
│  ├─ audit/               # vault_audit.py (read-only scan), tool_audit.py (log)
│  ├─ tools/
│  │  ├─ capabilities.py   # registry: enable/disable per tool + seed
│  │  ├─ dispatcher.py     # LocalToolDispatcher: route + capability check + audit
│  │  └─ preflight.py      # cek keselamatan sebelum go-live
│  ├─ vault/
│  │  ├─ writer.py         # slugify, content_hash, render_frontmatter, atomic_write, write_capture
│  │  ├─ sensitivity.py    # detect_sensitive(), SENSITIVE_HINTS, marker #private
│  │  ├─ reader.py         # resolve_in_vault (anti path-traversal), read_note, list_notes
│  │  ├─ search.py         # rebuild_index() + search() pakai FTS5 (body sensitif dikosongkan)
│  │  └─ organize.py       # move_note() + update_note() (atomik, hash-guard, undo_payload)
│  ├─ jobs/
│  │  ├─ capture.py        # capture_note() -> CaptureResult (+ dedupe idempotency)
│  │  └─ undo.py           # undo_operation() (capture/move/update, hash-guard)
│  ├─ mcp_server.py        # FastMCP stdio: expose health/capture/search/get/move/update/undo
│  └─ reindex.py           # bangun ulang FTS index atas seluruh vault
├─ migrations/0001_initial.sql
├─ tests/                  # unittest: capture, organize, search, dispatcher, migrations…
└─ .env                    # VAULT_PATH, DATABASE_URL, TIMEZONE, token internal (JANGAN commit)
```

Skema SQLite inti: `jobs` (operation_id, tool, idempotency_key, undo_payload, …),
`notes`, `audit_log`, dan tabel FTS5 `search_index(note_id, title, body, tags, path)`.

---

## 6. Langkah membangun & deploy (urutan)

**Fase 0 — Fondasi:** repo, `config.py`, SQLite migration, fixture vault untuk test,
read-only vault audit. Semua write tool *disabled*.

**Fase 1 — Rangka aman:** capability registry + dispatcher + audit + preflight; MCP stdio
server yang baru expose `health_check` (belum menyentuh vault). Uji end-to-end:
Telegram → Hermes → MCP → dispatcher → audit.

**Fase 2 — Capture (write pertama):** `writer.py` + `sensitivity.py` + `jobs/capture.py`
+ `undo`. Enable `capture_note`. Tulis note ke `Inbox` secara atomik.

**Fase 3 — Organize:** `reader.py` + `search.py` (FTS5) + `organize.py` (move/update) +
undo umum. Enable `search_vault/get_note/move_note/update_note`. Bangun index (`reindex.py`).

**Deploy (mesin 24/7):**
1. Install Hermes: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`.
2. `hermes setup` → pilih provider LLM (lihat catatan biaya di bawah) → terminal **Local**
   → Telegram (bot dari @BotFather, isi allowlist user-id kamu).
3. **Uji koneksi Telegram** dari jaringan rumah dulu (`hermes gateway restart`, cek log
   `Connected to Telegram (polling mode)` tanpa 504).
4. Buat venv + install `mcp`; set `.env` `VAULT_PATH` ke folder Obsidian asli.
5. `PYTHONPATH=src python -m second_brain.reindex` (bangun index).
6. `hermes mcp add second-brain --command <python-venv> --args -m second_brain.mcp_server`.
7. **Full Disk Access** untuk proses Hermes (macOS TCC) supaya bisa baca/tulis `~/Documents`.
8. `hermes gateway restart` → uji di Telegram: capture, search, move, update, undo.
9. Hardening: aktifkan auto-start setelah mati listrik + auto-login.

**Catatan biaya LLM (penting):** model kelas atas (Opus/Sonnet, GPT besar) mahal untuk
agent yang sering memanggil tool. Untuk harian pakai model **murah/cepat** (Gemini Flash,
GPT-mini) dan naik ke model pintar hanya saat perlu. Ganti kapan saja: `hermes model`.
Hindari operasi "scan seluruh vault" yang membaca ratusan note (boros token); pakai `/new`
tiap tugas baru untuk reset context.

---

## 7. Gotchas (yang bikin pusing)

- **macOS TCC:** `~/Documents` terproteksi — proses yang menulis (Hermes/Core) butuh
  Full Disk Access, kalau tidak: "operation not permitted".
- **AppleDouble `._*.sql`:** `tar`/mac bikin file sidecar yang bikin `apply_migrations`
  gagal (UnicodeDecodeError). Migrasi harus **skip file diawali `.`**.
- **MCP remote/HTTP** cenderung bikin gateway Hermes crash → pakai **stdio lokal**.
- **Telegram: 1 poller per bot.** Jangan jalankan dua gateway dengan token yang sama.
- **Model tidak ditemukan (404)** di jalur OAuth Gemini/Code Assist → coba nama model lain
  (mis. seri `gemini-2.5-*`) atau Flash; free tier juga bisa kena **rate-limit (429)**.
- **Nama folder vault** ikut milikmu (mis. `2. Area Kerja`), bukan template `10 Projects`.

---

## 8. BUILD PROMPT (copy-paste ke coding-agent)

> Tempel blok di bawah utuh ke Claude Code / Cursor / agent lain. Sesuaikan `VAULT_PATH`.

```text
You are building "Second Brain Core" — a local, safety-first backend that lets an
AI agent (via the Hermes Agent's MCP interface) capture, search, and organize notes
in an Obsidian vault, controlled from Telegram. Build it in Python 3.12 using ONLY the
standard library plus the `mcp` package (FastMCP). Storage is SQLite (WAL + FTS5).

GOALS
- Expose these tools over an MCP stdio server (FastMCP): health_check, capture_note,
  search_vault, get_note, move_note, update_note, undo_operation.
- Every tool call is routed through ONE dispatcher that (a) checks a capability registry
  (per-tool enabled/disabled), (b) writes an audit-log row, then (c) executes.

HARD REQUIREMENTS (do not simplify away)
1. All vault writes are ATOMIC (write temp file, then os.replace), PATH-SAFE (reject any
   path escaping the vault root — no `..`), and HASH-GUARDED: move/update take an optional
   expected_hash and refuse if the note's current content hash differs.
2. Every capture/move/update returns an operation_id and stores an undo_payload so
   undo_operation can reverse it. Undo refuses if the note changed since (hash mismatch)
   and cannot run twice.
3. Sensitivity: detect_sensitive(text) flags notes containing secret-like keywords
   (password, api key, token, etc.) or a `#private` marker. Sensitive notes get a
   non-revealing filename `private-<hash8>.md`, their body is NEVER indexed for search,
   and their body is never returned by get_note.
4. capture_note supports an idempotency_key to dedupe retries (store keys in the jobs table).
5. Notes are Markdown with YAML frontmatter (title, created, tags, para, sensitive).
   Captures land in the Inbox folder.
6. Search uses an FTS5 table search_index(note_id, title, body, tags, path); sensitive
   notes are indexed by title/tags only (empty body). Provide rebuild_index(conn, vault_root)
   and a `reindex` entrypoint runnable as `python -m second_brain.reindex`.

CONFIG (config.py): a frozen dataclass AppConfig loaded from a .env file with keys
VAULT_PATH, DATABASE_URL (sqlite:///…), TIMEZONE, LOG_LEVEL, and an internal tool token.
validate() must fail if VAULT_PATH doesn't exist. Never commit secrets.

DB (db/migrate.py): connect() opens SQLite with PRAGMA journal_mode=WAL and foreign_keys=ON.
apply_migrations() runs migrations/*.sql in order, records applied versions, and MUST SKIP
files whose name starts with "." (macOS AppleDouble sidecars break decoding). Seed the
capability registry. Tables: jobs, notes, audit_log, schema_migrations, and FTS5 search_index.

MODULE LAYOUT
  src/second_brain/config.py
  src/second_brain/db/migrate.py
  src/second_brain/audit/{vault_audit.py,tool_audit.py}
  src/second_brain/tools/{capabilities.py,dispatcher.py,preflight.py}
  src/second_brain/vault/{writer.py,sensitivity.py,reader.py,search.py,organize.py}
  src/second_brain/jobs/{capture.py,undo.py}
  src/second_brain/mcp_server.py     # FastMCP stdio; one @mcp.tool per tool above
  src/second_brain/reindex.py
  migrations/0001_initial.sql
  tests/                             # unittest, stdlib only, using a fixture vault

MCP SERVER (mcp_server.py): FastMCP("second_brain_mcp"); each tool is a thin wrapper that
calls the dispatcher and returns a JSON string {tool, ok, result, error, operation_id}.
Open a fresh SQLite connection per call (FastMCP may use worker threads). Load config +
apply migrations lazily (no side effects at import). Register with Hermes via:
  hermes mcp add second-brain --command <venv-python> --args -m second_brain.mcp_server

TESTS: cover capture (incl. sensitive filename + dedupe), search (incl. sensitive body
excluded), get (incl. sensitive refusal + path traversal rejected), move/update (hash
conflict + undo), and migrations (dotfile skipped). Use a fixture vault, not a real one.

BUILD ORDER: (0) config + migrations + fixture + read-only vault audit, all write tools
disabled. (1) capability registry + dispatcher + audit + a health_check-only MCP server.
(2) writer + sensitivity + capture + undo; enable capture_note. (3) reader + search +
organize (move/update) + generalized undo; enable the read/organize tools; add reindex.
Keep future tools disabled until their phase. Deliver runnable tests at each phase.
```

---

## 9. Checklist ringkas untuk yang mereplikasi

- [ ] Punya mesin nyala 24/7 + Obsidian (+ Sync bila multi-device).
- [ ] Bangun Core pakai BUILD PROMPT di atas; semua test hijau.
- [ ] Install Hermes + `hermes setup` (provider murah, terminal Local, Telegram bot + allowlist).
- [ ] Uji koneksi Telegram dari jaringanmu (tanpa 504).
- [ ] `.env` `VAULT_PATH` → folder Obsidian asli; `reindex`.
- [ ] `hermes mcp add second-brain` (stdio) + Full Disk Access + restart.
- [ ] Uji Telegram: capture → search → move → update → undo.
- [ ] Hardening: auto-start setelah mati listrik + auto-login.
- [ ] (Opsional) tambah MCP lain, mis. Todoist, untuk to-do + reminder.
```
