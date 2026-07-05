"""Full-text search over the vault using the SQLite FTS5 `search_index` table.

Sensitive notes are indexed by metadata only (title, tags, path) — their body is
never indexed, so search can find them by name but never surfaces their content.
"""

from __future__ import annotations

from pathlib import Path
import re
import sqlite3

from second_brain.vault.reader import (
    frontmatter_value,
    is_sensitive,
    iter_markdown,
)

_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]+)")
_FM_TAGS_RE = re.compile(r"^tags:\s*\[([^\]]*)\]\s*$", re.MULTILINE)
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _strip_frontmatter(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :]).strip()
    return content.strip()


def _extract_tags(content: str) -> list[str]:
    tags: set[str] = set(_TAG_RE.findall(content))
    for match in _FM_TAGS_RE.findall(content):
        for tag in match.split(","):
            t = tag.strip().strip('"').strip("'")
            if t:
                tags.add(t)
    return sorted(tags)


def _match_expr(query: str) -> str:
    # Quote each term so arbitrary user text never breaks FTS5 syntax (AND search).
    terms = _WORD_RE.findall(query or "")
    return " ".join(f'"{t}"' for t in terms)


def rebuild_index(conn: sqlite3.Connection, vault_root: Path) -> int:
    root = Path(vault_root).expanduser().resolve()
    conn.execute("DELETE FROM search_index")
    count = 0
    for path in iter_markdown(root):
        rel = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = frontmatter_value(text, "title") or path.stem
        tags = " ".join(_extract_tags(text))
        body = "" if is_sensitive(text) else _strip_frontmatter(text)
        conn.execute(
            "INSERT INTO search_index (note_id, title, body, tags, path) "
            "VALUES (?, ?, ?, ?, ?)",
            (rel, title, body, tags, rel),
        )
        count += 1
    conn.commit()
    return count


def search(
    conn: sqlite3.Connection, query: str, *, limit: int = 10
) -> list[dict[str, str]]:
    expr = _match_expr(query)
    if not expr:
        return []
    rows = conn.execute(
        """
        SELECT path, title,
               snippet(search_index, 2, '[', ']', '…', 12) AS snip
        FROM search_index
        WHERE search_index MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (expr, limit),
    ).fetchall()
    return [
        {"path": row["path"], "title": row["title"], "snippet": row["snip"] or ""}
        for row in rows
    ]
