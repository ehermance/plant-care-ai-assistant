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
from flask import Flask, Response, g, request
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
from .routes.reminders import reminders_bp
from .routes.journal import journal_bp
from .routes.admin import admin_bp
from .routes.marketing import marketing_bp
from .routes.guides import guides_bp
from .services import supabase_client
from .utils import auth


def _validate_production_security(app: Flask, cfg_path: str) -> None:
    """
    Validate critical security settings in production environments.

    Raises RuntimeError if production security requirements are not met.
    This prevents the app from starting with insecure configurations.

    Checks:
    - SESSION_COOKIE_SECURE must be True (cookies only over HTTPS)
    - SECRET_KEY must be set and strong (>= 32 characters)
    - DEBUG must be False (no debug mode in production)
    - PREFERRED_URL_SCHEME should be "https"

    Args:
        app: Flask application instance
        cfg_path: Config path being used (e.g., "app.config.ProdConfig")
    """
    # Only validate if running production config
    is_production = "ProdConfig" in cfg_path
    is_test = app.config.get("TESTING", False)

    # Skip validation in test/dev environments
    if not is_production or is_test:
        return

    errors = []

    # Check SESSION_COOKIE_SECURE
    if not app.config.get("SESSION_COOKIE_SECURE", False):
        errors.append(
            "SESSION_COOKIE_SECURE must be True in production. "
            "Cookies must only be sent over HTTPS to prevent session hijacking."
        )

    # Check SECRET_KEY strength
    secret_key = app.config.get("SECRET_KEY", "")
    if not secret_key:
        errors.append(
            "SECRET_KEY is not set. Set FLASK_SECRET_KEY environment variable. "
            "Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
        )
    elif len(secret_key) < 32:
        errors.append(
            f"SECRET_KEY is too weak ({len(secret_key)} chars). "
            "Must be at least 32 characters for production security."
        )

    # Check DEBUG mode
    if app.config.get("DEBUG", False):
        errors.append(
            "DEBUG must be False in production. Debug mode exposes sensitive information "
            "and should never be enabled in production environments."
        )

    # Check HTTPS enforcement
    if app.config.get("PREFERRED_URL_SCHEME", "http") != "https":
        errors.append(
            "PREFERRED_URL_SCHEME should be 'https' in production. "
            "Set PREFERRED_URL_SCHEME=https environment variable."
        )

    # If any errors, raise exception to prevent app startup
    if errors:
        error_msg = "\n\n[ERROR] PRODUCTION SECURITY VALIDATION FAILED:\n\n" + "\n\n".join(f"  * {err}" for err in errors)
        error_msg += "\n\n[WARNING] The application will not start until these security issues are resolved.\n"
        raise RuntimeError(error_msg)

    # Log success
    app.logger.info("[OK] Production security validation passed")


def create_app() -> Flask:
    # Load .env early (for local dev)
    # Use override=True to ensure .env values take precedence over system environment
    load_dotenv(override=True)

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
        app.logger.warning(f"Could not load config object {cfg_path}: {e}")

    # --- Production Security Validation ---
    # Validate critical security settings in production to prevent misconfigurations
    _validate_production_security(app, cfg_path)

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

    # Set user timezone in request context (for client-side timestamp conversion)
    @app.before_request
    def load_user_timezone():
        """Load user's timezone preference into request context."""
        g.user_timezone = None

        # Skip for static files and certain paths to avoid unnecessary API calls
        if request.path.startswith('/static/') or request.path.endswith('.ico'):
            return

        try:
            user_id = auth.get_current_user_id()
            if user_id:
                profile = supabase_client.get_user_profile(user_id)
                if profile:
                    g.user_timezone = profile.get("timezone")
        except Exception:
            pass  # Don't fail request on timezone lookup errors

    # ---- Content Security Policy ----
    # Allow Supabase domains for auth, API calls, and storage
    supabase_domain = app.config.get("SUPABASE_URL", "").replace("https://", "").replace("http://", "")

    # Content Security Policy
    # Note: 'unsafe-inline' is needed for JSON-LD structured data (SEO)
    # This is safe as JSON-LD scripts are type="application/ld+json" (data, not executable)
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline'; "  # Allow inline styles (modernization CSS)
        f"img-src 'self' data: https://{supabase_domain}; "
        "font-src 'self'; "
        f"connect-src 'self' https://cloudflareinsights.com https://static.cloudflareinsights.com https://{supabase_domain}; "
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

        # HSTS: Force HTTPS for 1 year, include subdomains, allow preload list
        # Only apply in production (when SESSION_COOKIE_SECURE is True)
        if app.config.get("SESSION_COOKIE_SECURE", False):
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Permissions-Policy: Disable sensitive browser features not needed by the app
        resp.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        return resp

    # Blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pricing_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(plants_bp)
    app.register_blueprint(reminders_bp)
    app.register_blueprint(journal_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(marketing_bp)
    app.register_blueprint(guides_bp)

    # Add Jinja global for templates that need current date/time
    from datetime import datetime, date
    app.jinja_env.globals["now"] = lambda: datetime.now()

    # Add Jinja filter for relative dates ("today", "yesterday", "3 days ago")
    def relative_date(value):
        """Convert a date/datetime to relative format like 'today', 'yesterday', '3 days ago'."""
        if not value:
            return "Unknown"

        # Parse string to date if needed
        if isinstance(value, str):
            try:
                # Handle ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
                value = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except (ValueError, AttributeError):
                return value[:10] if len(value) >= 10 else value
        elif isinstance(value, datetime):
            value = value.date()

        today = date.today()
        delta = (today - value).days

        if delta == 0:
            return "Today"
        elif delta == 1:
            return "Yesterday"
        elif delta < 7:
            return f"{delta} days ago"
        elif delta < 14:
            return "1 week ago"
        elif delta < 30:
            weeks = delta // 7
            return f"{weeks} weeks ago"
        elif delta < 60:
            return "1 month ago"
        else:
            # Fall back to formatted date for older entries
            return value.strftime("%b %d, %Y")

    app.jinja_env.filters["relative_date"] = relative_date

    # Add Jinja global for Cloudflare Web Analytics
    app.jinja_env.globals["CF_BEACON_TOKEN"] = os.getenv("CF_BEACON_TOKEN", "")

    # --- Background Scheduler for Weather Adjustments (Phase 2C) ---
    # Initialize APScheduler for daily weather adjustment job
    # Runs at 6:00 AM daily to adjust reminders based on weather forecasts
    if not app.config.get("TESTING", False):  # Skip scheduler in test mode
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from app.services.reminder_adjustments import batch_adjust_all_users_reminders
            from app.services.marketing_emails import process_welcome_email_queue

            scheduler = BackgroundScheduler()

            # Wrapper functions to ensure Flask app context is available
            # APScheduler runs jobs in background threads without app context
            def run_weather_adjustments():
                with app.app_context():
                    batch_adjust_all_users_reminders()

            def run_welcome_email_job():
                with app.app_context():
                    process_welcome_email_queue()

            # Schedule daily weather adjustments at 6:00 AM (UTC)
            scheduler.add_job(
                func=run_weather_adjustments,
                trigger="cron",
                hour=6,
                minute=0,
                id="daily_weather_adjustments",
                name="Daily Weather Reminder Adjustments",
                replace_existing=True
            )

            # Schedule welcome email processing every hour
            scheduler.add_job(
                func=run_welcome_email_job,
                trigger="interval",
                hours=1,
                id="welcome_email_job",
                name="Process Welcome Email Queue",
                replace_existing=True
            )

            scheduler.start()
            app.logger.info("[Scheduler] Daily weather adjustment job scheduled for 6:00 AM UTC")
            app.logger.info("[Scheduler] Welcome email job scheduled to run hourly")

            # Shutdown scheduler gracefully on app exit
            import atexit
            atexit.register(lambda: scheduler.shutdown())

        except Exception as e:
            app.logger.warning(f"[Scheduler] Failed to initialize weather adjustment scheduler: {e}")

    return app


# -----------------------------------------------------------------------------
# Backward-compat exports for tests that import from the top-level `app` package
# -----------------------------------------------------------------------------
from .services.ai import ai_advice as ai_advice  # noqa: E402,F401
from .services.ai import _weather_tip as weather_adjustment_tip  # noqa: E402,F401