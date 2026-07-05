"""Sensitivity detection for captured notes.

A note is treated as sensitive when the user marks it explicitly, when it carries
a private marker (e.g. ``#private``), or when it contains whole-word hints that
commonly indicate secrets. Sensitive notes are never semantically indexed, never
sent to AI processing, and their body is not echoed back to the user.
"""

from __future__ import annotations

import re

# Whole-word hints that suggest a note holds secrets. Kept conservative to avoid
# over-flagging; the user can always mark a note sensitive explicitly.
SENSITIVE_HINTS: frozenset[str] = frozenset(
    {
        "password",
        "passphrase",
        "secret",
        "seed phrase",
        "recovery phrase",
        "private key",
        "api key",
        "token",
        "pin",
        "cvv",
        "rekening",
        "kata sandi",
        "sandi",
    }
)

_PRIVATE_MARKER_RE = re.compile(r"(?<!\w)#private(?!\w)", re.IGNORECASE)
_WORD_BOUNDARY_TEMPLATE = r"(?<!\w){}(?!\w)"


def has_private_marker(text: str) -> bool:
    """True if the text contains an explicit ``#private`` tag."""
    return bool(_PRIVATE_MARKER_RE.search(text or ""))


def detect_sensitive(text: str, *, explicit: bool | None = None) -> bool:
    """Decide whether a note is sensitive.

    Args:
        text: The note body (and/or title) to scan.
        explicit: If the caller already knows (user said so), this wins.

    Returns:
        True if the note should be treated as sensitive.
    """
    if explicit is not None:
        return explicit

    haystack = (text or "").lower()
    if has_private_marker(haystack):
        return True
    for hint in SENSITIVE_HINTS:
        if re.search(_WORD_BOUNDARY_TEMPLATE.format(re.escape(hint)), haystack):
            return True
    return False
