"""Read-side vault helpers for Phase 3 (search/get/organize).

Path-safe reads that stay inside the vault root, plus lightweight frontmatter
inspection so callers can honor the `sensitive` flag without parsing full YAML.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from second_brain.vault.writer import content_hash

EXCLUDE_DIRS = {".git", ".obsidian", ".trash", "node_modules"}


class VaultReadError(ValueError):
    """Raised when a requested path is unsafe or not a readable note."""


def resolve_in_vault(vault_root: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` under the vault root, rejecting traversal/escapes."""
    root = Path(vault_root).expanduser().resolve()
    candidate = (root / rel_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise VaultReadError(f"Path escapes the vault root: {rel_path}")
    return candidate


def read_note(vault_root: Path, rel_path: str) -> tuple[str, str]:
    """Return (content, content_hash) for a note. Path-safe, .md only."""
    path = resolve_in_vault(vault_root, rel_path)
    if path.suffix.lower() != ".md":
        raise VaultReadError(f"Not a Markdown note: {rel_path}")
    if not path.is_file():
        raise VaultReadError(f"Note not found: {rel_path}")
    text = path.read_text(encoding="utf-8")
    return text, content_hash(text)


def frontmatter_value(content: str, key: str) -> str | None:
    """Return the raw value of a top-level frontmatter key, or None.

    Only inspects the leading ``---`` block; no full YAML parsing.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, _, v = line.partition(":")
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return None


def is_sensitive(content: str) -> bool:
    return (frontmatter_value(content, "sensitive") or "").lower() == "true"


@dataclass(frozen=True)
class NoteRef:
    rel_path: str
    title: str
    sensitive: bool


def iter_markdown(vault_root: Path) -> Iterator[Path]:
    root = Path(vault_root).expanduser().resolve()
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if set(rel.parts) & EXCLUDE_DIRS:
            continue
        if path.name.startswith("."):
            continue
        yield path


def list_notes(vault_root: Path) -> list[NoteRef]:
    """List notes with title + sensitivity (cheap frontmatter read)."""
    root = Path(vault_root).expanduser().resolve()
    notes: list[NoteRef] = []
    for path in iter_markdown(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = frontmatter_value(text, "title") or path.stem
        notes.append(
            NoteRef(
                rel_path=str(path.relative_to(root)),
                title=title,
                sensitive=is_sensitive(text),
            )
        )
    return notes
