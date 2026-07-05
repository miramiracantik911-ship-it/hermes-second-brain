# Phase 3 Checklist

## Code (complete)

- [x] `vault/reader.py`: path-safe reads, frontmatter, sensitivity.
- [x] `vault/search.py`: FTS5 index; sensitive bodies excluded (metadata only).
- [x] `vault/organize.py`: `move_note` + `update_note` (atomic, hash-guarded).
- [x] `jobs/undo.py`: unified undo for capture/move/update (git-sync aware).
- [x] Capabilities enabled: `search_vault`, `get_note`, `update_note`, `move_note`.
- [x] `approve_media` (Phase 6) kept disabled for the capability-gate test.
- [x] Dispatcher routes all Phase 3 tools; READ/ORGANIZE/UNDO error codes.
- [x] `mcp_http_server.py` (FastMCP streamable-http) for the Mac-side Core.
- [x] Tests: search (incl sensitive exclusion), get (incl sensitive refusal +
      traversal), move (conflict, undo), update (conflict, undo). Full suite green (54).

## Deployment (pending)

- [ ] Tailscale on the VPS (`curl -fsSL https://tailscale.com/install.sh | sh`; `tailscale up`).
- [ ] Mac mini: venv + `mcp`, `VAULT_PATH=~/Documents/Second Brain`, build FTS index.
- [ ] Run `mcp_http_server` on the Mac as a launchd service, bound to the tailnet IP, auto-start on boot.
- [ ] `hermes mcp add second-brain-mac --url http://<macmini-tailnet>:8788/mcp`; restart gateway.
- [ ] Telegram dry run: search, move a note to a project, update a note, undo each.

## Decisions (locked)

- Architecture: Mac-side Core over Tailscale (not mirror-to-VPS).
- Capture: hybrid — VPS inbox courier retained.
- `move_note`/`update_note`: no per-op approval; hash-guard + undo are the safety net.
- Search excludes sensitive-note bodies (metadata only).

## Prerequisites being set up

- Mac mini 24/7: FileVault OFF (done), Screen Sharing ON (done); enable
  "Start up automatically after a power failure" + Automatic Login.
- Tailscale on Mac mini + iPhone (done; disable key expiry on Mac mini — done).
  MacBook Air joins later.
