# Phase 2 Plan - First Write Capability (capture_note)

Status: planned — awaiting Andri's review and "start" command (do not begin coding yet)
Date: 2026-06-16
Repo: `/Users/andri/Projects/hermes-second-brain`
Live deployment: VPS `103.37.124.108` (Hermes + Second Brain MCP, Telegram, always-on)

Decisions locked for this plan:

- **Write path: Path 1** — the audited `capture_note` in Second Brain Core (NOT
  Hermes' built-in obsidian skill). Hermes' obsidian skill is reserved for
  lower-risk read/search in Phase 3 (the "Path 3 / hybrid" direction). See §3b.
- **Vault sync: git "inbox" courier** — VPS → private GitHub inbox repo → Mac mini
  ingest job → real vault → Obsidian Sync. See §3.
- **Auto-capture to `00 Inbox` without per-note approval is APPROVED** (append-only
  + undoable; approval reserved for `update_note`/`move_note` in Phase 3).

Still pending: Andri's review of this updated plan, then an explicit "start" command
before any coding begins.

## 1. Goal

Phase 1 gave Hermes a safe, read-only path into Second Brain Core (health/job/sync
status), live end-to-end from Telegram via MCP. Phase 2 turns Second Brain from
"observable" into "useful": the agent can **capture a note into the real Obsidian
vault** from Telegram, safely, idempotently, and reversibly.

By the end of Phase 2:

1. `capture_note` is implemented and enabled (currently registered-but-disabled).
2. A message to the Telegram bot can be saved as a Markdown note in the vault's
   `00 Inbox` with correct PARA/CODE frontmatter.
3. Every write is recorded as a `jobs` + `notes` + `operations` row, and is
   undoable via `undo_operation`.
4. Sensitive content is detected and never indexed, AI-processed, or echoed back.
5. The real vault on the VPS is synced to Andri's devices (decision in §3).
6. Tests cover capture, dedupe, sensitivity, path-safety, and undo — all against a
   throwaway copy of the fixture vault, never the real vault.

Out of scope for Phase 2 (later phases): `search_vault` (Phase 3), `update_note`/
`move_note` (Phase 3), semantic indexing/embeddings, attachments/media capture,
URL extraction. Phase 2 is text capture into Inbox only.

## 2. Safety Boundary

Phase 2 must:

- Write only inside the vault root, only under `00 Inbox/` (append-only create).
- Never overwrite an existing file (unique, timestamped filenames).
- Treat the write as atomic (temp file + rename) so a crash never leaves a
  half-written note.
- Record a reversible `operations` row (undo deletes the created file).
- Detect sensitive content and set `sensitive: true`, `ai_processing: disabled`,
  `semantic_index: disabled`, `telegram_preview: disabled`; do not echo the body
  back to Telegram for sensitive notes.
- Keep all other write tools (`update_note`, `move_note`) disabled.

Phase 2 must not:

- Modify or delete pre-existing notes.
- Send the vault or note contents to any external service.
- Store secrets in the repo or in git history of the vault.

## 3. The Key Decision - Bridging the VPS to an Obsidian Sync Vault

Andri's vault is synced across **Mac mini, MacBook Air, and iPhone via Obsidian
Sync** (paid, 1-year). Obsidian Sync officially requires the Obsidian app running;
there is no supported headless mode, so the **VPS cannot join Obsidian Sync
directly.** We keep Obsidian Sync as the device-sync layer and add a bridge from
the VPS to the real vault through a Mac.

Constraint: the **Mac mini is currently powered off at night** (a future 24/7
server is planned). The bridge must tolerate the Mac being offline.

| Bridge | How it works | Fits "Mac off at night"? | Recommended |
| --- | --- | --- | --- |
| **Git inbox courier** | VPS commits each note to a private "inbox" git repo (GitHub) and pushes. A small job on a Mac pulls the inbox and moves new notes into the vault's `00 Inbox`; Obsidian Sync propagates to all devices. | Yes — notes queue in GitHub and flush when a Mac wakes; nothing lost. | **Yes (Phase 2 now)** |
| Tailscale + Mac MCP | VPS Hermes calls a Second Brain writer on the Mac over a private tailnet; the Mac writes the vault directly. Real-time. | No — fails while the Mac is asleep. | Later (when the Mac is 24/7) |

**Recommendation: git inbox courier now.** A capture at 2am is stored in the GitHub
inbox immediately and lands in Obsidian the next time a Mac wakes and ingests —
nothing is lost. When the Mac mini becomes a 24/7 server, we can switch to the
Tailscale real-time bridge (or keep the courier; it works either way).

Components:

1. A **private "inbox" git repo** (separate from the Obsidian vault, which Sync
   owns), mirroring the `00 Inbox` folder. Deploy key on the VPS (write access).
2. `capture_note` on the VPS writes the note into a local checkout of the inbox
   repo and commits/pushes it.
3. An **ingest job on the Mac mini** (launchd periodic) that pulls the inbox, moves
   new `.md` files into the real vault's `00 Inbox`, and records what it ingested
   (so it never double-imports). Obsidian Sync then propagates to MacBook Air and
   iPhone. (Running the ingester on the MacBook Air too is a later enhancement that
   needs concurrency handling.)

In Phase 2 the "vault" that the writer (§4, §7) targets is the **inbox repo
checkout on the VPS**; the Mac-side courier is what lands notes in the real
Obsidian vault.

Decisions: **auto-capture to `00 Inbox` without per-note approval is APPROVED**
(append-only + undoable; approval reserved for `update_note`/`move_note` in
Phase 3).

Inputs still needed from Andri before building:

1. Which account/org hosts the **private inbox repo** (GitHub assumed).
2. Confirm the ingest job runs on the **Mac mini** for now.
3. Confirm PARA folder names (`00 Inbox`, `10 Projects`, `20 Areas`,
   `30 Resources`, `40 Archives`) and that capture targets `00 Inbox`.
4. Timezone/locale for metadata (assume `Asia/Jakarta` / WIB; Indonesian titles OK).

## 3b. Prior Art - Build vs Reuse

GitHub research (2026-06-16) on existing tools:

- **Hermes ships a bundled `obsidian` note-taking skill** (read, list, search,
  create, append, add wikilinks; vault via `OBSIDIAN_VAULT_PATH`). This is the most
  important finding: Hermes can already write notes. Two paths for Phase 2:
  - **Path 1 (our `capture_note`, recommended):** keep writes inside Second Brain
    Core so they go through the Capability Gateway, audit log, Inbox-only policy,
    and `undo_operation`. Preserves the project's safety architecture ("Hermes must
    not own direct vault writes").
  - **Path 2 (use Hermes' obsidian skill):** least code, but Hermes writes directly
    with no capability check / audit / undo and broader scope than Inbox-only.
  - **Hybrid:** our audited `capture_note` for writes now; consider enabling Hermes'
    obsidian skill for lower-risk read/search later (Phase 3).
- **Standalone Telegram→Obsidian bots** (`dimonier/tg2obsidian`, `fahadhasin/notes-bot`,
  `obsidian-ai-idea-capture-plugin`): good references for frontmatter, date-grouping,
  and future voice/OCR/URL capture, but they *duplicate* Hermes (each is its own bot),
  so they are reference-only, not drop-in.
- **Mac-side ingest:** the **Obsidian Git** and **GitHub Sync** community plugins are
  mature for the device-pull side; our inbox-repo → vault courier stays small/custom.

**DECIDED: Path 1** — build the audited `capture_note` (small, Inbox-only, undoable)
and borrow frontmatter/slug conventions from the references. Hermes' bundled obsidian
skill is NOT used for writes in Phase 2; it is reserved for lower-risk read/search in
Phase 3 (Path 3 / hybrid). The git-inbox courier (§3) is needed regardless.

## 4. capture_note Contract

Input (validated):

| Field | Type | Notes |
| --- | --- | --- |
| `text` | string (required) | The note body. |
| `title` | string (optional) | If absent, derive from first line / first N words. |
| `tags` | string[] (optional) | Added to frontmatter. |
| `source` | enum (optional) | `telegram` (default), `manual`. |
| `idempotency_key` | string (optional) | If absent, derived from a hash of text+minute to dedupe rapid retries. |

Behavior:

1. Validate input; reject empty text.
2. Compute `idempotency_key`; if a `jobs` row already has it, return the existing
   result (no duplicate file).
3. Run sensitivity detection (frontmatter `#private`, keyword hints from
   `vault_audit.SENSITIVE_HINTS`, or an explicit `sensitive` flag).
4. Build frontmatter: `title`, `created` (WIB date), `source_type`, `status:
   active`, `para: inbox`, `code_stage: capture`, `distillation_level: D1`,
   `tags`, `sensitive`, and (if sensitive) `ai_processing: disabled`,
   `semantic_index: disabled`, `telegram_preview: disabled`.
5. Choose a safe, unique path: `00 Inbox/<YYYY-MM-DD> <slug>.md`; if it exists,
   append a short suffix. Guard against path traversal and any path outside the
   vault root.
6. Atomic write (temp file in the same dir + `os.replace`).
7. Compute content hash; insert `jobs` (state `done`), `notes`, and `operations`
   rows (with `undo_payload` = the created path).
8. (Git vault) stage/commit/push.
9. Return `{ ok, note_path, operation_id, sensitive }`. For sensitive notes, the
   response omits the body and only confirms the path.

Result shape (Local Tool Result Shape, as JSON):

```json
{
  "tool": "capture_note",
  "ok": true,
  "result": { "note_path": "00 Inbox/2026-06-16 contoh.md", "sensitive": false },
  "error": null,
  "operation_id": "op_..."
}
```

## 5. undo_operation Contract (Phase 2 partner)

`undo_operation(operation_id)`:

1. Look up the `operations` row; verify it is an undoable capture and not already
   undone.
2. Delete the created file (only if its hash still matches — never delete a file
   the user has since edited).
3. (Git vault) commit the deletion.
4. Mark the operation undone; return status.

This makes capture safe to experiment with.

## 6. Capability + MCP Changes

- Registry: set `capture_note` and `undo_operation` to `enabled` (keep
  `approval_required: false` for inbox capture per §3.5). Add a migration or
  re-seed; document the change in `DECISIONS.md`.
- Dispatcher: implement `capture_note` and `undo_operation` execution paths,
  reusing capability checks + audit.
- MCP server (`mcp_server.py`): add `second_brain_capture_note` (annotations:
  `readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: true` via the
  idempotency key, `openWorldHint: false`) and `second_brain_undo_capture`
  (`destructiveHint: true`). Keep the three read-only tools as-is.

## 7. Code Layout

- `src/second_brain/vault/writer.py` (new): path safety, slug, atomic write,
  frontmatter rendering, hashing.
- `src/second_brain/vault/sensitivity.py` (new): sensitivity detection (reuse
  `SENSITIVE_HINTS`).
- `src/second_brain/vault/git_sync.py` (new, optional per §3): commit/push wrapper
  guarded by a config flag so non-git vaults still work.
- `src/second_brain/jobs/capture.py` (new): the capture job (validate → write →
  record rows → sync), and the undo path.
- Extend `tools/dispatcher.py` to route `capture_note` / `undo_operation`.
- Config additions: `VAULT_GIT_SYNC` (bool), `VAULT_GIT_REMOTE`/branch, timezone.

## 8. Testing

All tests copy `tests/fixtures/vault` into a temp dir (never touch the real vault):

- Capture creates a file in `00 Inbox` with valid frontmatter and the right
  `code_stage`/`para`.
- Title derivation from body when `title` omitted.
- Idempotency: same key → one file, second call returns existing result.
- Sensitivity: hinted content → `sensitive: true` + disabled index/AI/preview, and
  the result omits the body.
- Path safety: traversal attempts (`../`, absolute paths) are rejected; writes stay
  under the vault root.
- Atomicity: no temp files left behind on success.
- Undo: deletes the created file; refuses if the file was modified (hash mismatch);
  cannot double-undo.
- Disabled-by-default regression: with capability disabled, capture is rejected.
- Git sync path is unit-tested with a temp git repo when `VAULT_GIT_SYNC=true`.

Full suite must stay green (`python -m unittest discover -s tests`).

## 9. Deployment to VPS

1. Update the repo on the VPS (git pull once the repo is under version control, or
   rsync; exclude macOS `._*` sidecars — see the migrate.py dotfile guard).
2. Clone the private **inbox repo** on the VPS (e.g. `~/inbox`); point `VAULT_PATH`
   at that checkout and set the git-sync env vars. Set up the **Mac mini ingest
   job** (launchd) that pulls the inbox and moves notes into the real Obsidian vault.
3. Run migrations / re-seed capabilities.
4. `systemctl --user restart hermes-gateway`.
5. Telegram dry run: capture a test note → confirm it is committed/pushed to the
   inbox repo → confirm the Mac mini ingest lands it in the vault and Obsidian Sync
   propagates to MacBook Air + iPhone; then undo it.

## 10. Build Order (milestones)

1. Inbox repo created + Mac mini courier ready (§3) — **blocking, infra**.
2. `vault/writer.py` + `vault/sensitivity.py` + unit tests (local, fixture only).
3. `jobs/capture.py` + dispatcher routing + capability enable + tests.
4. `undo_operation` + tests.
5. MCP tools (`capture_note`, `undo_capture`) + local end-to-end test.
6. Optional `git_sync.py` behind a flag + tests.
7. Deploy to VPS, point at the inbox repo checkout, set up the Mac mini courier,
   Telegram dry run, undo.
8. Docs: update `API.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `PHASE_LOG.md`,
   `PHASE_2_CHECKLIST.md`, `AI_HANDOFF.md`.

## 11. Definition of Done

1. `capture_note` enabled; a Telegram message becomes an Inbox note with correct
   frontmatter.
2. Writes are atomic, path-safe, deduped, and recorded in `jobs`/`notes`/
   `operations`.
3. `undo_operation` removes a capture safely (hash-guarded, no double-undo).
4. Sensitive notes are detected, not indexed/echoed.
5. Real vault on the VPS syncs to Andri's devices.
6. Test suite green; docs updated.

## 12. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Writing outside the vault / path traversal | Resolve + assert path is under vault root; only `00 Inbox`. |
| Overwriting an existing note | Never overwrite; unique timestamped names; atomic rename. |
| Sensitive data leaking to AI/index/Telegram | Sensitivity flags disable index/AI/preview; body withheld in responses. |
| Sync conflicts across devices | Git transport with commit-per-capture; Inbox-only writes minimize conflicts. |
| Partial writes on crash | Temp file + `os.replace`. |
| Scope creep into Phase 3 | No update/move/search; Inbox capture only. |
| Credit exhaustion suspends the VPS | Monitor IDCloudHost credit; top up before depletion. |
