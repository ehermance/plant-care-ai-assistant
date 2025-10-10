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

class BaseConfig:
    # Secrets & basics
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
    DEBUG = False
    TESTING = False

    # Feature flags
    UI_DEBUG_LINKS = os.getenv("UI_DEBUG_LINKS", "").strip().lower() in {"1", "true", "yes"}

    # Third-party keys
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Flask-Limiter v3
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "true").lower() == "true"
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "40 per minute; 2000 per day")
    RATELIMIT_ASK = os.getenv("RATELIMIT_ASK", "8 per minute; 1 per 2 seconds; 200 per day")

    # Misc
    PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")
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