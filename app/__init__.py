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
from flask import Flask, Response, request, redirect
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv  # <-- ensure .env is loaded for local dev
from .extensions import limiter
from .routes.api import api_bp
from .routes.web import web_bp
from .routes.auth import auth_bp
from .routes.dashboard import dashboard_bp
from .routes.pricing import pricing_bp
from .routes.legal import legal_bp
from .routes.plants import plants_bp
from .services import supabase_client
from .utils import auth


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

    # Initialize CSRF Protection
    csrf = CSRFProtect(app)

    # Initialize Supabase client
    supabase_client.init_supabase(app)

    # Register auth context processor (makes current_user, is_authenticated, etc. available in templates)
    app.context_processor(auth.inject_auth_context)

    # ---- Content Security Policy ----
    # Allow Supabase domains for auth, API calls, and storage
    supabase_domain = app.config.get("SUPABASE_URL", "").replace("https://", "").replace("http://", "")

    csp = (
        "default-src 'self'; "
        "script-src 'self' https://static.cloudflareinsights.com; "
        "style-src 'self'; "
        f"img-src 'self' data: https://{supabase_domain}; "  # Allow Supabase Storage images
        "font-src 'self'; "
        f"connect-src 'self' https://cloudflareinsights.com https://static.cloudflareinsights.com https://{supabase_domain}; "  # Allow Supabase API calls
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "upgrade-insecure-requests"
    )

    @app.after_request
    def apply_security_headers(resp: Response) -> Response:
        resp.headers["Content-Security-Policy"] = csp
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["X-XSS-Protection"] = "0"  # CSP supersedes legacy XSS filter
        return resp

    # ---- Domain Redirects ----
    # Handle www subdomain and legacy domain redirects
    @app.before_request
    def handle_domain_redirects():
        """
        Redirect www subdomain to apex domain and legacy domain to new domain.
        - www.plantcareai.app/* → plantcareai.app/*
        - plants.ehermance.com/* → plantcareai.app/ask
        """
        host = request.host.lower()

        # Redirect www subdomain to apex domain (301 permanent)
        if host.startswith("www."):
            new_url = request.url.replace(f"://{host}", f"://{host[4:]}", 1)
            return redirect(new_url, code=301)

        # Redirect legacy domain to new domain's /ask page (301 permanent)
        if host == "plants.ehermance.com" or host.startswith("plants.ehermance.com:"):
            new_url = request.url.replace(
                f"://{host}",
                "://plantcareai.app",
                1
            )
            # Force path to /ask for legacy domain
            return redirect("https://plantcareai.app/ask", code=301)

    # Blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pricing_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(plants_bp)

    # Add Jinja global for templates that need current date/time
    from datetime import datetime
    app.jinja_env.globals["now"] = lambda: datetime.now()

    # Add Jinja global for Cloudflare Web Analytics
    app.jinja_env.globals["CF_BEACON_TOKEN"] = os.getenv("CF_BEACON_TOKEN", "")

    return app


# -----------------------------------------------------------------------------
# Backward-compat exports for tests that import from the top-level `app` package
# -----------------------------------------------------------------------------
from .services.ai import ai_advice as ai_advice  # noqa: E402,F401
from .services.ai import _weather_tip as weather_adjustment_tip  # noqa: E402,F401