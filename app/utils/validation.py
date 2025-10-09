"""
Input validation and normalization.

Trims and bounds field lengths, filters suspicious characters while allowing
natural punctuation, normalizes select values, and builds a clean payload for
downstream processing.
"""

from __future__ import annotations
import html
import re
from typing import Any, Dict, Tuple

# Allowlist regex: we REMOVE anything NOT in this set.
# Includes letters/numbers/space and common lightweight punctuation used in names.
# This keeps plant/city fields readable while dropping odd control/symbol characters.

_SAFE_CHARS_PATTERN = re.compile(r"[^a-zA-Z0-9\s\-\.,'()/&]+")

MAX_PLANT_LEN = 80
MAX_CITY_LEN = 80
MAX_QUESTION_LEN = 1200

# Allowed values for the care-context select. Anything else is coerced to the default.
CARE_CONTEXT_CHOICES = {"indoor_potted", "outdoor_potted", "outdoor_bed"}


def _soft_sanitize(text: str, max_len: int) -> str:
    """
    Normalizes names/locations:
    - strip whitespace
    - bound length
    - remove disallowed characters via allowlist
    - collapse double spaces
    """
    t = (text or "").strip()
    if not t:
        return ""
    t = t[:max_len]
    t = _SAFE_CHARS_PATTERN.sub("", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t


def _soft_sanitize_question(text: str, max_len: int) -> str:
    """
    Question field is a bit more permissive:
    - strip & bound length
    - remove control chars only; keep reasonable punctuation
    - normalize repeated tabs/spaces
    """
    t = (text or "").strip()
    if not t:
        return ""
    t = t[:max_len]
    t = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t


def normalize_context(value: str | None) -> str:
    """Coerce unknown/missing values to the default option."""
    v = (value or "").strip().lower()
    return v if v in CARE_CONTEXT_CHOICES else "indoor_potted"


def display_sanitize_short(text: str) -> str:
    """
    Short UI messages are HTML-escaped and truncated to avoid layout breaks.
    Use this only for brief notices surfaced to the page.
    """
    if not text:
        return ""
    t = html.escape(text)
    return (t[:240] + "…") if len(t) > 240 else t


def validate_inputs(form: Dict[str, Any]) -> Tuple[Dict[str, Any], str | None]:
    """
    Validates incoming form data and returns (payload, error_message).
    On success, payload has:
      - plant (optional sanitized string)
      - city (optional sanitized string)
      - care_context (normalized select value)
      - question (required string within length limit)
    """
    raw_plant = form.get("plant", "")
    raw_city = form.get("city", "")
    raw_question = form.get("question", "")
    raw_context = form.get("care_context", "")

    plant = _soft_sanitize(raw_plant, MAX_PLANT_LEN)
    city = _soft_sanitize(raw_city, MAX_CITY_LEN)
    question = _soft_sanitize_question(raw_question, MAX_QUESTION_LEN)
    care_context = normalize_context(raw_context)

    if not question:
        return {}, "Question is required and must be under 1200 characters."

    return {
        "plant": plant,
        "city": city,
        "question": question,
        "care_context": care_context,
    }, None