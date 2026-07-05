#!/usr/bin/env bash
#
# Mac-side ingest for the Hermes Second Brain "inbox" courier.
#
# Pulls the private inbox git repo (which the VPS pushes captures to) and copies
# any new notes into the real Obsidian vault's "00 Inbox". Obsidian Sync then
# propagates them to all devices. Append-only: existing files are never
# overwritten, so a note you have edited in Obsidian is safe.
#
# Edit the two paths below (or pass them as env vars), then run on a schedule
# via launchd (see scripts/com.hermes.inbox-ingest.plist).

set -euo pipefail

# --- Edit these two paths ---------------------------------------------------
INBOX_REPO="${INBOX_REPO:-$HOME/hermes-inbox}"
VAULT_INBOX="${VAULT_INBOX:-$HOME/Documents/Second Brain/00 Inbox}"
# ---------------------------------------------------------------------------

if [ ! -d "$INBOX_REPO/.git" ]; then
  echo "Inbox repo not found at: $INBOX_REPO" >&2
  exit 1
fi
[ -d "$VAULT_INBOX" ] || mkdir -p "$VAULT_INBOX"

# Pull latest captures from the VPS.
git -C "$INBOX_REPO" pull --rebase --autostash --quiet \
  || git -C "$INBOX_REPO" pull --quiet

# Copy new notes into the vault. We use bash's own redirection (not rsync/cp) so
# the process that opens the TCC-protected vault folder is bash itself — which has
# Full Disk Access — rather than a child binary that would be denied.
# `[ ! -e ]` means we never overwrite a note you have edited in Obsidian.
if [ -d "$INBOX_REPO/00 Inbox" ]; then
  shopt -s nullglob
  for src in "$INBOX_REPO/00 Inbox/"*.md; do
    [ -f "$src" ] || continue
    dst="$VAULT_INBOX/$(basename "$src")"
    [ -e "$dst" ] || cat "$src" > "$dst"
  done
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') ingest ok"
