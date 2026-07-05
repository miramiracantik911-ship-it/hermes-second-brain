from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re


WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]+)")
FRONTMATTER_TAGS_RE = re.compile(r"^tags:\s*\[([^\]]*)\]\s*$", re.MULTILINE)
SENSITIVE_HINTS = {
    "password",
    "pass",
    "secret",
    "private",
    "seed",
    "recovery",
    "key",
    "token",
    "bank",
    "rekening",
}


@dataclass(frozen=True)
class VaultAudit:
    root: Path
    markdown_files: int
    attachments: int
    folders: list[str]
    tags: list[tuple[str, int]]
    wikilinks: list[tuple[str, int]]
    possible_sensitive_paths: list[str]
    para_like_folders: list[str]

    def to_markdown(self) -> str:
        def append_list(items: list[str]) -> None:
            if items:
                lines.extend(items)
            else:
                lines.append("- None")

        lines = [
            "# Vault Audit Report",
            "",
            f"Root: `{self.root}`",
            "",
            "## Summary",
            "",
            f"- Markdown files: {self.markdown_files}",
            f"- Attachments: {self.attachments}",
            f"- Folders: {len(self.folders)}",
            "",
            "## PARA-like Folders",
            "",
        ]
        append_list([f"- `{item}`" for item in self.para_like_folders])
        lines.extend(["", "## Top Tags", ""])
        append_list([f"- `#{tag}`: {count}" for tag, count in self.tags[:30]])
        lines.extend(["", "## Top Wikilinks", ""])
        append_list([f"- `[[{link}]]`: {count}" for link, count in self.wikilinks[:30]])
        lines.extend(["", "## Possible Sensitive Paths", ""])
        append_list([f"- `{path}`" for path in self.possible_sensitive_paths[:50]])
        lines.extend(
            [
                "",
                "## Notes",
                "",
                "- This audit is read-only.",
                "- Possible sensitive paths are detected from names and tags only.",
                "- No AI processing is required for this report.",
            ]
        )
        return "\n".join(lines) + "\n"


def audit_vault(root: str | Path, exclude_dirs: set[str] | None = None) -> VaultAudit:
    vault_root = Path(root).expanduser().resolve()
    exclude_dirs = exclude_dirs or set()
    folders: list[str] = []
    markdown_files = 0
    attachments = 0
    tag_counter: Counter[str] = Counter()
    wikilink_counter: Counter[str] = Counter()
    possible_sensitive: list[str] = []
    para_like: list[str] = []

    if not vault_root.exists() or not vault_root.is_dir():
        raise ValueError(f"Vault path must be an existing directory: {vault_root}")

    for path in sorted(vault_root.rglob("*")):
        rel = path.relative_to(vault_root)
        parts = set(rel.parts)
        if parts & exclude_dirs:
            continue

        rel_str = str(rel)
        lower = rel_str.lower()
        if path.is_dir():
            folders.append(rel_str)
            if rel.name in {"00 Inbox", "10 Projects", "20 Areas", "30 Resources", "40 Archives"}:
                para_like.append(rel_str)
            continue

        if any(hint in lower for hint in SENSITIVE_HINTS):
            possible_sensitive.append(rel_str)

        if path.suffix.lower() == ".md":
            markdown_files += 1
            text = path.read_text(encoding="utf-8", errors="ignore")
            tag_counter.update(TAG_RE.findall(text))
            for match in FRONTMATTER_TAGS_RE.findall(text):
                tag_counter.update(
                    tag.strip().strip('"').strip("'")
                    for tag in match.split(",")
                    if tag.strip()
                )
            wikilink_counter.update(match.strip() for match in WIKILINK_RE.findall(text))
        else:
            attachments += 1

    return VaultAudit(
        root=vault_root,
        markdown_files=markdown_files,
        attachments=attachments,
        folders=folders,
        tags=tag_counter.most_common(),
        wikilinks=wikilink_counter.most_common(),
        possible_sensitive_paths=possible_sensitive,
        para_like_folders=para_like,
    )


def write_audit_report(root: str | Path, output_path: str | Path) -> Path:
    audit = audit_vault(root)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(audit.to_markdown(), encoding="utf-8")
    return destination
