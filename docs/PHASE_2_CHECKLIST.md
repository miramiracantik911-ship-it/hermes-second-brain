# Phase 2 Checklist

## Code (complete)

- [x] `TIMEZONE` + `VAULT_GIT_SYNC` config and `.env.example` entries.
- [x] `vault/sensitivity.py` detects sensitive content.
- [x] `vault/writer.py`: slug, path-safety, frontmatter, atomic write, hashing.
- [x] `jobs/capture.py`: `capture_note` + `undo_capture`.
- [x] Idempotency dedupe via `jobs.idempotency_key`.
- [x] Records `notes` and `operations` (with undo payload) rows.
- [x] Dispatcher routes capture/undo and passes config + undo payload.
- [x] `capture_note` and `undo_operation` capabilities enabled.
- [x] `update_note` / `move_note` / `search_vault` remain disabled.
- [x] MCP tools `second_brain_capture_note` + `second_brain_undo_capture`.
- [x] Sensitive notes: non-revealing filename, disabled index/AI/preview, body withheld.
- [x] Tests: create/frontmatter, title derivation, idempotency, sensitivity,
      path-safety, no temp files, undo, hash-guard, double-undo, empty text,
      no-config rejection.
- [x] Full suite green (40 tests).
- [x] Real stdio MCP capture + undo verified.

## Deployment + sync (complete — live 2026-06-17)

- [x] Private GitHub "inbox" repo `andrihakim146/hermes-inbox`; deploy keys (VPS + Mac).
- [x] Updated repo deployed to the VPS; `VAULT_PATH=/home/catatanandri/hermes-inbox`.
- [x] `VAULT_GIT_SYNC=true`: each capture commits + pushes to GitHub.
- [x] MCP re-registered with Hermes (5 tools enabled); gateway restarted.
- [x] Mac mini ingest job (launchd `com.hermes.inbox-ingest`, every 5 min) copies new
      notes into `~/Documents/Second Brain/00 Inbox`; Obsidian Sync propagates.
- [x] Telegram dry run verified: a capture appeared in GitHub and then in Obsidian.

### macOS gotcha (resolved)

`~/Documents` is TCC-protected, so the launchd job's `rsync` was denied
("Operation not permitted"). Fix: granted Full Disk Access to `/bin/bash` AND
changed the ingest to copy via bash redirection (`cat src > dst`) so the process
that opens the protected vault folder is bash (which has FDA), not a child binary.

## Notes

- Mac mini is off at night; the courier tolerates this — captures queue in GitHub
  and flush on the next ingest after a Mac wakes.
- Security note: Full Disk Access on `/bin/bash` is broad (any bash script gains it).
  Acceptable on a personal Mac; revisit if hardening.
