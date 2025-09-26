"""
Provides a wrapper for OpenAI moderation. The function returns a simple
(allowed: bool, reason: str|None) tuple and is safe to call without a Flask
application context. When no API key is configured, moderation is skipped.
"""

import os

try:
    from flask import current_app
except Exception:  # pragma: no cover
    current_app = None  # type: ignore

def _cfg(name: str, default=None):
    """Safely read Flask config if available, else return default."""
    try:
        if current_app:
            return current_app.config.get(name, default)
    except Exception:
        pass
    return default

def run_moderation(text: str):
    """
    Perform an input/output moderation check.
    - If no API key is present, returns (True, None) to avoid blocking dev/tests.
    - If the API call fails, returns (False, "…") to fail closed.
    """
    key = os.getenv("OPENAI_API_KEY") or _cfg("OPENAI_API_KEY")
    if not key:
        return True, None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        resp = client.moderations.create(model="omni-moderation-latest", input=text)
        flagged = resp.results[0].flagged if resp.results else False
        return (not flagged), ("Content flagged by moderation" if flagged else None)
    except Exception as e:
        return False, f"Moderation service unavailable: {str(e)[:160]}"
