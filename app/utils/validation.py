"""
Validates and sanitizes user inputs, provides a shallow sensitivity check,
and redacts simple PII before adding entries to the history.
"""

import re
import unicodedata

# Input length limits.
MAX_QUESTION_LEN = 1200
MAX_SHORT_FIELD_LEN = 80

# Common punctuation used in plant and city names.
ALLOWED_PUNCT = set(" -'(),./&×")

# PII patterns for redaction in saved history.
EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
PHONE_RE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")

# Simple trigger list for obviously sensitive/abusive requests.
SENSITIVE_TRIGGERS = (
    "api key", "password", "private key", "token ", "ssh ", "exploit", "ddos", "hack", "bypass"
)

def is_safe_short_field(text: str | None) -> bool:
    """Accept Unicode letters/digits/spaces and a limited punctuation set."""
    if not text:
        return True
    if len(text) > MAX_SHORT_FIELD_LEN:
        return False
    s = unicodedata.normalize("NFKC", text)
    for ch in s:
        if ch.isalpha() or ch.isdigit() or ch.isspace() or ch in ALLOWED_PUNCT:
            continue
        return False
    return True

def validate_inputs(plant: str | None, city: str | None, question: str) -> tuple[bool, str]:
    """Return (ok, message). Message is user-friendly when not ok."""
    if not question or len(question) > MAX_QUESTION_LEN:
        return False, "Question is required and must be under 1200 characters."
    if not is_safe_short_field(plant):
        return False, "Plant name is invalid or too long."
    if not is_safe_short_field(city):
        return False, "City name is invalid or too long."
    return True, ""

def looks_sensitive(question: str) -> bool:
    """Quick guard for obviously sensitive/abusive content."""
    q = (question or "").lower()
    return any(t in q for t in SENSITIVE_TRIGGERS)

def redact_pii(text: str) -> str:
    """Replace emails and phone numbers with placeholders."""
    text = EMAIL_RE.sub("[email]", text)
    text = PHONE_RE.sub("[phone]", text)
    return text

def display_sanitize_short(text: str | None) -> str | None:
    """Normalize and trim short values for consistent display."""
    if text is None:
        return None
    return unicodedata.normalize("NFKC", text).strip()
