"""
Application factory for the Plant Care AI Assistant.

Creates and configures the Flask app instance:
- Loads environment variables
- Sets secret key and config
- Initializes Flask-Limiter for rate limiting
- Registers UI/API blueprints
- Applies a strict Content Security Policy (CSP)
- Re-exports selected helpers for tests that import from `app`
"""

import os
from flask import Flask
from dotenv import load_dotenv

from .extensions import limiter
from .routes.web import web_bp
from .routes.api import api_bp


def create_app():
    """Create and configure the Flask application instance."""
    load_dotenv()
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # -------------------------------------------------------------------------
    # Core configuration
    # -------------------------------------------------------------------------
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-not-secret")

    # Human-friendly knobs for rate limits
    app.config.update(
        RATE_LIMIT_DEFAULT=os.getenv("RATE_LIMIT_DEFAULT", "60 per minute;300 per hour"),
        RATE_LIMIT_ASK=os.getenv("RATE_LIMIT_ASK", "20 per minute;200 per day"),
        RATE_LIMIT_STORAGE_URI=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
        RATE_LIMIT_ENABLED=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
    )

    # -------------------------------------------------------------------------
    # Flask-Limiter configuration (RATELIMIT_* keys it actually reads)
    # Normalize RATE_LIMIT_DEFAULT to a single semicolon-delimited string.
    # Examples accepted by limits:
    #   "60 per minute;300 per hour"  OR  "100/day"
    # This avoids the list/iterable confusion paths inside flask-limiter 3.x.
    raw_default = app.config["RATE_LIMIT_DEFAULT"]
    if isinstance(raw_default, str):
        # Collapse any accidental multi-semicolon spacing, trim ends
        default_str = ";".join(s.strip() for s in raw_default.split(";") if s.strip())
    elif isinstance(raw_default, (list, tuple)):
        default_str = ";".join(str(s).strip() for s in raw_default if str(s).strip())
    else:
        default_str = ""

    app.config["RATELIMIT_DEFAULT"] = default_str
    app.config["RATELIMIT_STORAGE_URI"] = app.config["RATE_LIMIT_STORAGE_URI"]
    app.config["RATELIMIT_ENABLED"] = app.config["RATE_LIMIT_ENABLED"]
    app.config["RATELIMIT_HEADERS_ENABLED"] = True  # expose limit headers

    # Initialize the limiter (no keyword args for v3.x)
    limiter.init_app(app)

    # -------------------------------------------------------------------------
    # Register blueprints (routes)
    # -------------------------------------------------------------------------
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/")

    # -------------------------------------------------------------------------
    # Content Security Policy (CSP)
    # -------------------------------------------------------------------------
    @app.after_request
    def set_csp(resp):
        """Apply a strict Content Security Policy to every response."""
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "upgrade-insecure-requests"
        )
        return resp

    return app


# -----------------------------------------------------------------------------
# Re-exports for backwards compatibility with tests and direct imports
# -----------------------------------------------------------------------------
from .services.weather import get_weather_for_city  # noqa: E402
from .services.ai import ai_advice, AI_LAST_ERROR  # noqa: E402
from .routes.web import weather_adjustment_tip, basic_plant_tip  # noqa: E402
