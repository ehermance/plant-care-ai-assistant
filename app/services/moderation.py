"""
Lightweight text moderation.

Checks user input and returns (allowed, reason). If blocked, 'reason' is a
short message suitable for UI display. Replace with a stronger policy or a
vendor API if you need more coverage.
"""

from __future__ import annotations
from typing import Tuple

# Very light heuristic example; extend as needed.

_BLOCKLIST = {
    "hate", "suicide", "bomb", "kill", "murder", "shoot", "terror", "nsfw",
}


def run_moderation(text: str) -> Tuple[bool, str | None]:
    """
    Returns (allowed, reason). Lowercase match against a tiny blocklist.
    This is intentionally minimal to avoid false positives.
    """
    t = (text or "").lower()
    for term in _BLOCKLIST:
        if term in t:
            return False, f"contains disallowed content: “{term}”"
    return True, None