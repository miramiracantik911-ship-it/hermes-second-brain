"""Safe, atomic Markdown note writing for the vault.

Phase 2 only creates notes under the Inbox folder. The writer guarantees:
- writes stay inside the vault root (no path traversal),
- existing files are never overwritten (unique, timestamped names),
- writes are atomic (temp file + os.replace),
- sensitive notes get a non-revealing filename and disabled index/AI/preview flags.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence
import hashlib
import os
import re
import tempfile

INBOX_DIR = "00 Inbox"
MAX_SLUG_LEN = 60
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
_PLAIN_SCALAR_RE = re.compile(r"^[A-Za-z0-9_./\-]+$")
_YAML_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "none", "~"}


@dataclass(frozen=True)
class WriteResult:
    relative_path: str
    absolute_path: Path
    content_hash: str
    title: str


def slugify(text: str) -> str:
    """Lowercase, hyphenated, filesystem-safe slug. Never empty."""
    slug = _SLUG_STRIP_RE.sub("-", (text or "").lower()).strip("-")
    slug = slug[:MAX_SLUG_LEN].strip("-")
    return slug or "catatan"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return content_hash(path.read_text(encoding="utf-8"))


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    # Render simple identifier-like values unquoted (e.g. `code_stage: capture`),
    # matching the vault's frontmatter style; quote anything else (e.g. titles).
    if text and _PLAIN_SCALAR_RE.match(text) and text.lower() not in _YAML_RESERVED:
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_frontmatter(fields: Sequence[tuple[str, object]]) -> str:
    lines = ["---"]
    for key, value in fields:
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(_yaml_scalar(item) for item in value)
            lines.append(f"{key}: [{rendered}]")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def build_note(
    *,
    title: str,
    body: str,
    tags: Sequence[str],
    created_date: date,
    sensitive: bool,
    source: str,
) -> str:
    """Render the full Markdown note (frontmatter + body)."""
    fields: list[tuple[str, object]] = [
        ("title", title),
        ("created", created_date),
        ("source_type", source),
        ("status", "private" if sensitive else "active"),
        ("para", "inbox"),
        ("code_stage", "capture"),
        ("distillation_level", "D1"),
        ("tags", list(tags)),
        ("sensitive", sensitive),
    ]
    if sensitive:
        fields += [
            ("ai_processing", "disabled"),
            ("semantic_index", "disabled"),
            ("telegram_preview", "disabled"),
        ]
    else:
        fields.append(("semantic_index", "enabled"))

    frontmatter = render_frontmatter(fields)
    body_text = (body or "").strip()
    return f"{frontmatter}\n\n# {title}\n\n{body_text}\n"


def _resolve_inbox(vault_root: Path) -> Path:
    root = vault_root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Vault root is not a directory: {root}")
    inbox = (root / INBOX_DIR).resolve()
    # Path-safety: the inbox must live directly under the vault root.
    if root not in inbox.parents and inbox != root:
        raise ValueError("Resolved inbox escapes the vault root.")
    inbox.mkdir(parents=True, exist_ok=True)
    return inbox


def _unique_path(inbox: Path, base_name: str) -> Path:
    candidate = inbox / f"{base_name}.md"
    counter = 2
    while candidate.exists():
        candidate = inbox / f"{base_name}-{counter}.md"
        counter += 1
    # Final guard: the chosen file is inside the inbox.
    resolved = candidate.resolve()
    if inbox not in resolved.parents:
        raise ValueError("Resolved note path escapes the inbox.")
    return candidate


def atomic_write(path: Path, content: str) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def write_capture(
    vault_root: Path,
    *,
    title: str,
    body: str,
    tags: Sequence[str],
    created_date: date,
    sensitive: bool,
    source: str,
) -> WriteResult:
    """Create a capture note under ``00 Inbox`` and return its location + hash.

    For sensitive notes the filename is intentionally non-revealing.
    """
    inbox = _resolve_inbox(vault_root)
    content = build_note(
        title=title,
        body=body,
        tags=tags,
        created_date=created_date,
        sensitive=sensitive,
        source=source,
    )
    digest = content_hash(content)

    if sensitive:
        slug = f"private-{digest[:8]}"
    else:
        slug = slugify(title)
    base_name = f"{created_date.isoformat()} {slug}"

    target = _unique_path(inbox, base_name)
    atomic_write(target, content)

    vault_root_resolved = vault_root.expanduser().resolve()
    relative = target.resolve().relative_to(vault_root_resolved)
    return WriteResult(
        relative_path=str(relative),
        absolute_path=target.resolve(),
        content_hash=digest,
        title=title,
    )
