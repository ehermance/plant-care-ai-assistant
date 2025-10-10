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
    # Load .env early (for local dev)
    load_dotenv()

    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # --- Load central config.py first ---
    # Allow APP_CONFIG to override (e.g., app.config.ProdConfig)
    cfg_path = os.getenv("APP_CONFIG", "app.config.ProdConfig")
    try:
        app.config.from_object(cfg_path)
    except (ImportError, AttributeError) as e:
        print(f"[WARN] Could not load config object {cfg_path}: {e}")

    limiter.init_app(app)

    if not app.config.get("RATELIMIT_ENABLED", True):
        limiter.enabled = False

    # Ensure SECRET_KEY is applied from config
    if not app.secret_key:
        app.secret_key = app.config.get("SECRET_KEY", "")

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