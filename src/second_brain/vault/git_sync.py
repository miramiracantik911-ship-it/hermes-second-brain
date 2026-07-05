"""Git transport for the vault "inbox" repo.

When ``VAULT_GIT_SYNC`` is enabled, the vault root on the VPS is a checkout of a
private "inbox" git repo. After a capture (or undo) the change is committed and
pushed so a Mac-side ingest job can pull it into the real Obsidian vault.

Design choices for resilience:
- Commit is local and fast; we only commit when there is something staged.
- Push is best-effort: a network failure does NOT fail the capture. The note is
  safe in the local checkout and will be carried by the next successful push.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


class GitSyncError(RuntimeError):
    """Raised when a required local git operation fails (e.g. not a repo)."""


@dataclass(frozen=True)
class SyncResult:
    committed: bool
    pushed: bool
    message: str


def _run(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and proc.returncode != 0:
        raise GitSyncError(
            f"git {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()}"
        )
    return proc


def is_git_repo(repo_root: Path) -> bool:
    proc = _run(["rev-parse", "--is-inside-work-tree"], repo_root, check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def sync(repo_root: Path, message: str, *, push: bool = True) -> SyncResult:
    """Stage all changes, commit if anything changed, and best-effort push.

    Raises GitSyncError only for local failures (not a git repo, commit failure).
    A push failure is swallowed and reported via ``SyncResult.pushed = False``.
    """
    repo_root = Path(repo_root)
    if not is_git_repo(repo_root):
        raise GitSyncError(f"VAULT_GIT_SYNC is on but {repo_root} is not a git repo.")

    _run(["add", "-A"], repo_root)
    status = _run(["status", "--porcelain"], repo_root).stdout
    if not status.strip():
        return SyncResult(committed=False, pushed=False, message="nothing to commit")

    _run(["commit", "-m", message], repo_root)

    if not push:
        return SyncResult(committed=True, pushed=False, message="committed (push off)")

    push_proc = _run(["push"], repo_root, check=False)
    if push_proc.returncode == 0:
        return SyncResult(committed=True, pushed=True, message="committed and pushed")
    return SyncResult(
        committed=True,
        pushed=False,
        message=f"committed; push deferred: {(push_proc.stderr or '').strip()[:200]}",
    )
