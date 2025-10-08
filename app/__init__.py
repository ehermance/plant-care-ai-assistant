"""
Application factory and global configuration.

Creates the Flask app, applies security headers (CSP), configures rate limiting,
registers blueprints, and exposes UI flags used by templates. This file keeps
startup/config concerns together and avoids domain logic here.

Also provides a small set of compatibility exports so older tests that import
functions from the top-level `app` package (e.g., `app.ai_advice`) still work
after the project was modularized.
"""

from __future__ import annotations
import os
from flask import Flask, Response
from dotenv import load_dotenv  # <-- ensure .env is loaded for local dev
from .extensions import limiter
from .routes.api import api_bp
from .routes.web import web_bp


def create_app() -> Flask:
    # Load env vars from .env early so os.getenv() picks them up in dev.
    # In production, rely on real environment variables instead of .env.
    load_dotenv()

    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # Secret key (sessions/CSRF). In production, prefer an env var.
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-not-secret")

    # Surface API keys in app.config for /debug and services that read config.
    # (Reading from os.getenv at call time still works; this just mirrors them.)
    app.config.setdefault("OPENWEATHER_API_KEY", os.getenv("OPENWEATHER_API_KEY", ""))
    app.config.setdefault("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))

    # Optional UI flag: the template shows Health/Debug links if True or if ?debug=true.
    app.config.setdefault("UI_DEBUG_LINKS", False)

    # ---- Rate limiting (Flask-Limiter v3) ----
    # For production, use Redis/Memcached: e.g., app.config["RATELIMIT_STORAGE_URI"] = "redis://host:6379"
    app.config.setdefault("RATELIMIT_ENABLED", True)
    app.config.setdefault("RATELIMIT_STORAGE_URI", "memory://")
    # Default limits applied to all routes unless a route overrides with @limiter.limit(...)
    app.config.setdefault("RATELIMIT_DEFAULT", ["60 per minute", "300 per hour"])

    # Normalize RATELIMIT_DEFAULT in case it's a *stringified list* from env
    raw_limits = app.config.get("RATELIMIT_DEFAULT")
    if isinstance(raw_limits, str):
        # Accept "a; b" or "a, b" or even "['a', 'b']"
        cleaned = raw_limits.strip()
        if cleaned.startswith("[") and cleaned.endswith("]"):
            # strip brackets and quotes, then split by comma
            cleaned = cleaned[1:-1].replace("'", "").replace('"', "")
            parts = [p.strip() for p in cleaned.split(",") if p.strip()]
        else:
            # split by ; or ,
            parts = [p.strip() for p in cleaned.replace(";", ",").split(",") if p.strip()]
        app.config["RATELIMIT_DEFAULT"] = parts

    limiter.init_app(app)


    # ---- Content Security Policy ----
    csp = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )

    @app.after_request
    def apply_security_headers(resp: Response) -> Response:
        resp.headers["Content-Security-Policy"] = csp
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["X-XSS-Protection"] = "0"  # CSP supersedes legacy XSS filter
        return resp

    # Blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Add Jinja global for templates that need current date/time
    from datetime import datetime
    app.jinja_env.globals["now"] = lambda: datetime.now()

    return app


# -----------------------------------------------------------------------------
# Backward-compat exports for tests that import from the top-level `app` package
# -----------------------------------------------------------------------------
from .services.ai import ai_advice as ai_advice  # noqa: E402,F401
from .services.ai import _weather_tip as weather_adjustment_tip  # noqa: E402,F401
