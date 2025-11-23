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
from datetime import timedelta

class BaseConfig:
    # Secrets & basics
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
    DEBUG = False
    TESTING = False

    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)  # Sessions last 30 days
    SESSION_COOKIE_SECURE = True  # Only send cookies over HTTPS (overridden in dev)
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to cookies
    SESSION_COOKIE_SAMESITE = "Lax"  # CSRF protection (Lax allows normal links)

    # Feature flags
    UI_DEBUG_LINKS = os.getenv("UI_DEBUG_LINKS", "").strip().lower() in {"1", "true", "yes"}
    DEBUG_ENDPOINTS_ENABLED = os.getenv("DEBUG_ENDPOINTS_ENABLED", "false").lower() == "true"

    # Third-party keys
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Supabase (Database + Auth + Storage)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_REDIRECT_URL = os.getenv("SUPABASE_REDIRECT_URL", "http://localhost:5000/auth/callback")

    # Flask-Limiter v3
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "true").lower() == "true"
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "40 per minute; 2000 per day")
    RATELIMIT_ASK = os.getenv("RATELIMIT_ASK", "8 per minute; 1 per 2 seconds; 200 per day")

    # File uploads
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max upload size

    # Plant limits
    FREE_TIER_PLANT_LIMIT = 20  # Maximum plants for free tier users

    # Rate limiting
    UPLOAD_RATE_LIMIT = "20 per hour"  # Rate limit for plant/journal photo uploads
    SIGNUP_RATE_LIMIT = "5 per minute; 20 per hour"  # Rate limit for signup attempts

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
    DEBUG_ENDPOINTS_ENABLED = True  # Enable debug endpoint in development
    TEMPLATES_AUTO_RELOAD = True
    # Disable aggressive static caching in dev
    SEND_FILE_MAX_AGE_DEFAULT = 0
    PREFERRED_URL_SCHEME = "http"
    # Allow cookies over HTTP in dev
    SESSION_COOKIE_SECURE = False
    # Relaxed rate limits for development/testing
    SIGNUP_RATE_LIMIT = "100 per minute; 500 per hour"  # Much higher for dev testing

class TestConfig(BaseConfig):
    """CI/pytest settings."""
    TESTING = True
    DEBUG = True
    # Usually disable the limiter in tests to avoid flakiness
    RATELIMIT_ENABLED = False
    # Fast templates/static in tests
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0