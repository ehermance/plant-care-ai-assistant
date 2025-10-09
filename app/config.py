"""
Centralized configuration for all environments.

Select a config by setting:
  APP_CONFIG=app.config.DevConfig      # local dev
  APP_CONFIG=app.config.ProdConfig     # production (default if unset)
  APP_CONFIG=app.config.TestConfig     # pytest

Notes:
- SECRET_KEY is read from FLASK_SECRET_KEY
- Rate limiting uses Flask-Limiter v3 keys (RATELIMIT_*).
"""

from __future__ import annotations
import os
from typing import List


def _list_from_env(name: str, default: str) -> List[str]:
    """
    Parse a semicolon-OR-comma-separated env var into a list of strings.
    Example:
      RATELIMIT_DEFAULT="60 per minute; 300 per hour"
    """
    raw = os.getenv(name, default)
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]

class BaseConfig:
    # Flask core
    ENV = "production"
    DEBUG = False
    TESTING = False

    # Matches your __init__.py (FLASK_SECRET_KEY)
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-not-secret")

    # JSON / template ergonomics
    JSONIFY_PRETTYPRINT_REGULAR = False
    JSON_SORT_KEYS = False
    TEMPLATES_AUTO_RELOAD = False

    # Optional UI flag used in __init__.py
    UI_DEBUG_LINKS = bool(os.getenv("UI_DEBUG_LINKS", ""))  # truthy string enables

    # Third-party API keys mirrored into app.config by your factory too
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # ---- Flask-Limiter v3 configuration ----
    # Enable/disable limiter globally
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "true").lower() != "false"

    # Storage backend (memory:// by default; use Redis for multi-instance)
    # Example: redis://:password@host:6379/0
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    # Default limits applied to all routes unless overridden by @limiter.limit()
    # Accepts semicolons or commas as separators.
    RATELIMIT_DEFAULT = _list_from_env(
        "RATELIMIT_DEFAULT",
        "60 per minute; 300 per hour"
    )

    # URL scheme hints (useful for url_for(..., _external=True) behind proxies)
    PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")

    # Static file caching (seconds); can increase in Prod via CDN anyway
    SEND_FILE_MAX_AGE_DEFAULT = int(os.getenv("SEND_FILE_MAX_AGE_DEFAULT", "3600"))

class ProdConfig(BaseConfig):
    """Production settings (selected by default if APP_CONFIG is unset)."""
    pass

class DevConfig(BaseConfig):
    """Developer-friendly settings."""
    ENV = "development"
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    # Disable aggressive static caching in dev
    SEND_FILE_MAX_AGE_DEFAULT = 0
    PREFERRED_URL_SCHEME = "http"

class TestConfig(BaseConfig):
    """CI/pytest settings."""
    TESTING = True
    DEBUG = True
    # Usually disable the limiter in tests to avoid flakiness
    RATELIMIT_ENABLED = False
    # Fast templates/static in tests
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0