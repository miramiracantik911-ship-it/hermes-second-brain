# Phase 3 Plan - Organize the Vault (search, move, update)

Status: IN PROGRESS — decisions locked, building code-side first (local + fixture).
Date: 2026-06-17

Decisions locked: (1) Architecture = **Mac-side Core over Tailscale** (not mirror).
(2) Capture = **hybrid** — keep the VPS inbox courier; add read/organize on the Mac.
(3) `move_note`/`update_note` run **without per-op approval**, relying on hash-guard
(never clobber a note edited in Obsidian) + undo as the safety net.
(4) Search index excludes sensitive-note bodies (metadata only).
Repo: `/Users/andri/Projects/hermes-second-brain`
Live: Phase 2 deployed — Telegram → Hermes (VPS) → MCP capture → GitHub inbox →
Mac mini courier → Obsidian vault `~/Documents/Second Brain/00 Inbox` → Obsidian Sync.

## 1. Goal

Phase 2 captures everything into `00 Inbox`. Phase 3 lets the agent **organize and
retrieve** across the whole vault — the CODE stages after *Capture*:

1. `search_vault` — find notes by text/tags across the vault.
2. `get_note` — read an allowed note's content.
3. `move_note` — move a note from Inbox into a PARA folder (Projects/Areas/Resources/Archives).
4. `update_note` — edit/append to an existing note, with conflict protection.

By the end of Phase 3, from Telegram you can say "pindahkan catatan X ke project Y",
"cari catatan tentang Z", or "tambahkan poin ini ke catatan W" — and Hermes does it,
audited and undoable.

## 2. The Architecture Decision (the crux)

Today the VPS Second Brain only holds the **Inbox** (the git inbox repo). `move`,
`search`, and `update` need the **whole vault**, which lives on the Macs via Obsidian
Sync. Two ways to give the agent full-vault access:

| Approach | How | Verdict |
| --- | --- | --- |
| **Mac-side Core over Tailscale (recommended)** | Run Second Brain Core on the Mac mini, pointed at the full Obsidian-Synced vault. Expose it over the private tailnet. Hermes-on-VPS calls it as a remote MCP. | Keeps Obsidian Sync; vault never leaves your machines; no dual-sync. Needs Mac mini 24/7 + Tailscale (being set up now). |
| Mirror whole vault to VPS | Make the entire vault a git repo mirrored to the VPS. | Rejected: creates a second sync system fighting Obsidian Sync (conflicts, `.git` synced), or forces dropping paid Obsidian Sync; whole vault (incl sensitive notes) leaves your devices. |

**Decision: Mac-side Core over Tailscale.** It resolves the "VPS only has the Inbox"
limit without the dual-sync mess, and reuses the exact code we already built — just
pointed at the full vault and reached over the tailnet.

### Resulting topology

```text
Telegram → Hermes (VPS, always-on)
              │  (MCP over Tailscale, private)
              ▼
        Second Brain Core on Mac mini  →  full Obsidian vault (~/Documents/Second Brain)
                                          →  Obsidian Sync → MacBook Air + iPhone
```

Capture consolidation (decision point §3): once the Mac mini is reliably 24/7, the
Mac-side Core can own **capture too** (writing straight into the vault), which retires
the GitHub inbox courier. Until we trust the 24/7 setup, we keep the Phase 2 inbox
courier as an offline fallback and add only the read/organize tools on the Mac.

## 3. Prerequisites (foundation, being set up now)

1. Mac mini 24/7: "Start up automatically after a power failure" + Automatic Login +
   FileVault OFF (done) so it self-recovers after an outage. Optional UPS for short cuts.
2. Tailscale on Mac mini + MacBook Air + iPhone (same account); **disable key expiry**
   on the Mac mini node so it never needs re-auth.
3. Decision from Andri: **migrate capture to the Mac-side Core** (retire the inbox
   courier) or **keep the hybrid** (VPS inbox for capture + Mac for read/organize)?
   Recommended: hybrid first, then migrate capture once the 24/7 setup is proven.

## 4. Exposing the Core over Tailscale (MCP transport)

The Phase 2 MCP server is stdio (local to Hermes). For a remote Core on the Mac mini,
add an HTTP-transport MCP server (FastMCP `streamable_http`) bound to the Mac's tailnet
interface only, then register it with Hermes:

```bash
hermes mcp add second-brain-mac --url http://<macmini-tailnet-name>:8788/mcp
```

Auth: require the `HERMES_INTERNAL_TOOL_TOKEN` bearer (already in config); bind to the
tailnet IP, never `0.0.0.0`. Tailscale ACLs restrict who can reach it.

## 5. Tool Contracts

| Tool | Risk | Notes |
| --- | --- | --- |
| `search_vault(query, limit?)` | L1 | FTS over the vault; returns paths, titles, snippets. Excludes `sensitive` note bodies (titles/paths only, or omit entirely per policy). |
| `get_note(path)` | L1 | Returns a note's content. Refuses sensitive notes unless explicitly allowed. |
| `move_note(path, to_para)` | L2 | Moves a note from Inbox into a PARA folder. Atomic, conflict-guarded, undoable. Updates the `notes` row + `code_stage` → `organize`. |
| `update_note(path, ...)` | L2 | Append or edit body, hash-guarded (refuse if changed since read), undoable. |

Search index: populate the existing `search_index` FTS5 table from a vault scan;
refresh on capture/update and on a periodic sweep. Sensitive notes are indexed by
metadata only (never body) so they never surface content to the agent.

## 6. Safety

- `move_note`/`update_note` touch existing notes → **higher risk than append-only
  capture**. Each records `operations` with before/after hashes and an undo payload.
- **Conflict guard**: read returns a hash; update/move refuse if the on-disk hash no
  longer matches (someone edited it in Obsidian meanwhile) — never clobber.
- **Approval**: require explicit confirmation in Telegram for `move_note`/`update_note`
  (reserved from Phase 2). Auto-capture to Inbox stays approval-free.
- Sensitive notes: never return bodies to the agent; never index bodies.
- Path-safety: all operations stay inside the vault root; PARA targets are an allowlist.

## 7. Code

- Reuse dispatcher, capability registry, audit, `vault/writer.py`, `vault/sensitivity.py`.
- New: `vault/reader.py` (read + hash), `vault/search.py` (FTS index build/query),
  `vault/organize.py` (move + update with conflict guard + undo).
- New: `mcp_http_server.py` (FastMCP streamable_http) for the Mac-side remote Core,
  exposing the read/organize tools (and optionally capture if migrated).
- Enable `search_vault`, `move_note`, `update_note` capabilities; add `get_note`.
- Extend `undo_operation` to reverse moves/updates (restore prior path/content by hash).

## 8. Testing

All against a throwaway copy of the fixture vault (never the real vault):
search hits/ranking, get_note (incl sensitive refusal), move (Inbox → Projects,
path-safety, undo, conflict refusal), update (append, hash-guard, undo, conflict
refusal), index refresh, approval-required paths, disabled-by-default regression.

## 9. Deployment (Mac mini)

1. Install Tailscale (Mac mini + MacBook Air + iPhone); disable key expiry on Mac mini.
2. Put the repo on the Mac mini (it's already in `~/Projects/hermes-second-brain`),
   create a venv with `mcp`, set `VAULT_PATH=~/Documents/Second Brain`, build the FTS index.
3. Run the HTTP MCP Core as a launchd service bound to the tailnet, auto-start on boot.
4. `hermes mcp add second-brain-mac --url http://<tailnet>:8788/mcp` on the VPS; restart gateway.
5. Telegram dry run: search, move a note to a project, update a note, undo each.

## 10. Build Order

1. Tailscale foundation + Mac mini 24/7 verified (prereq).
2. `vault/reader.py` + `vault/search.py` (FTS) + tests.
3. `vault/organize.py` (move + update + undo, conflict-guarded) + tests.
4. Enable capabilities; dispatcher routing; extend undo.
5. `mcp_http_server.py` (FastMCP streamable_http) + local end-to-end test.
6. Deploy on Mac mini over Tailscale; register remote MCP with Hermes; dry run.
7. (Optional) migrate capture to Mac-side; retire/keep inbox courier.
8. Docs: API, ARCHITECTURE, DECISIONS, PHASE_LOG, PHASE_3_CHECKLIST, AI_HANDOFF.

## 11. Definition of Done

1. `search_vault`, `get_note`, `move_note`, `update_note` work from Telegram via the
   Mac-side Core over Tailscale.
2. Moves/updates are atomic, conflict-guarded, audited, undoable; approval enforced.
3. Sensitive notes never leak bodies to the agent or index.
4. Full test suite green; docs updated.

## 12. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Mac mini offline → organize unavailable | Capture still works via VPS inbox fallback; organize queues until Mac is up. |
| Edit conflict with Obsidian | Hash-guard: refuse to write if the note changed on disk. |
| Exposing the Core beyond the tailnet | Bind to tailnet IP only + bearer token + Tailscale ACLs. |
| Wikilink/backlink breakage on move | Phase 3 moves the file only; link-rewriting is a later enhancement. |
| Sensitive content reaching the agent | Index/return metadata only for sensitive notes. |

## 13. Inputs Needed from Andri (before building)

1. Confirm the Mac-side-over-Tailscale architecture (vs mirror) — recommended.
2. Capture: migrate to Mac-side now, or keep the VPS inbox courier as fallback first?
3. Approval policy for `move_note`/`update_note` (recommended: confirm in Telegram).
4. Search: FTS over the whole vault is fine? Any folders to exclude from indexing?
