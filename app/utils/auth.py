"""
Authentication utilities and decorators for route protection.

Provides:
- @require_auth: Decorator to require authenticated user
- @require_premium: Decorator to require premium plan
- Session management helpers
"""

from __future__ import annotations
from functools import wraps
from typing import Optional, Dict, Any
from flask import session, redirect, url_for, request, flash, g
from app.services import supabase_client


# ============================================================================
# Session Management
# ============================================================================

SESSION_USER_KEY = "user"
SESSION_ACCESS_TOKEN_KEY = "access_token"
SESSION_REFRESH_TOKEN_KEY = "refresh_token"


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get currently logged-in user from session.

    Returns:
        User dict with id, email, etc. or None if not logged in
    """
    # Check if user already loaded in request context
    if hasattr(g, 'user'):
        return g.user

    # Try to get from session
    access_token = session.get(SESSION_ACCESS_TOKEN_KEY)
    refresh_token = session.get(SESSION_REFRESH_TOKEN_KEY)

    if not access_token:
        g.user = None
        return None

    # Verify token with Supabase (pass both tokens)
    user = supabase_client.verify_session(access_token, refresh_token)
    if not user:
        # Token invalid/expired, clear session
        clear_session()
        g.user = None
        return None

    # Store in request context for this request
    g.user = user
    return user


def get_current_user_id() -> Optional[str]:
    """
    Get current user's ID.

    Returns:
        User UUID or None if not logged in
    """
    user = get_current_user()
    return user.get("id") if user else None


def set_session(user: Dict[str, Any], access_token: str, refresh_token: Optional[str] = None) -> None:
    """
    Store user session data.

    Security: Regenerates session ID to prevent session fixation attacks.

    Args:
        user: User dict from Supabase Auth
        access_token: JWT access token
        refresh_token: Optional refresh token for session renewal
    """
    # Regenerate session ID to prevent session fixation
    session.clear()
    session.modified = True

    session[SESSION_USER_KEY] = {
        "id": user.get("id"),
        "email": user.get("email"),
    }
    session[SESSION_ACCESS_TOKEN_KEY] = access_token
    if refresh_token:
        session[SESSION_REFRESH_TOKEN_KEY] = refresh_token
    session.permanent = True  # Use permanent session (configurable lifetime)


def clear_session() -> None:
    """Clear user session data."""
    session.pop(SESSION_USER_KEY, None)
    session.pop(SESSION_ACCESS_TOKEN_KEY, None)
    session.pop(SESSION_REFRESH_TOKEN_KEY, None)


def is_authenticated() -> bool:
    """Check if user is currently authenticated."""
    return get_current_user() is not None


# ============================================================================
# Decorators
# ============================================================================

def require_auth(f):
    """
    Decorator to require authentication for a route.

    If user not logged in, redirects to signup page with 'next' parameter.

    Usage:
        @app.route('/dashboard')
        @require_auth
        def dashboard():
            user = get_current_user()
            return render_template('dashboard.html', user=user)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            # Store the intended destination
            next_url = request.url
            flash("Please sign in to access this page.", "info")
            return redirect(url_for("auth.signup", next=next_url))

        return f(*args, **kwargs)

    return decorated_function


def require_premium(f):
    """
    Decorator to require premium plan for a route.

    Checks if user is authenticated AND has premium access (paid or trial).
    If not premium, redirects to pricing page.

    Usage:
        @app.route('/export')
        @require_premium
        def export_plants():
            # Only premium users can access this
            return generate_pdf()
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check authentication
        if not is_authenticated():
            flash("Please sign in to access this page.", "info")
            return redirect(url_for("auth.signup", next=request.url))

        # Check premium access
        user_id = get_current_user_id()
        if not supabase_client.has_premium_access(user_id):
            flash("This feature requires a Premium plan. Upgrade to get unlimited access!", "warning")
            return redirect(url_for("pricing.index"))

        return f(*args, **kwargs)

    return decorated_function


def require_admin(f):
    """
    Decorator to require admin privileges for a route.

    Checks if user is authenticated AND has admin role.
    If not authenticated, redirects to signup page.
    If not admin, redirects to dashboard with access denied message.

    Usage:
        @app.route('/admin/metrics')
        @require_admin
        def admin_metrics():
            # Only admin users can access this
            return render_template('admin/metrics.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First check authentication
        if not is_authenticated():
            flash("Please sign in to access this page.", "info")
            return redirect(url_for("auth.signup", next=request.url))

        # Check admin privileges
        user_id = get_current_user_id()
        profile = supabase_client.get_user_profile(user_id)

        if not profile or not profile.get("is_admin", False):
            flash("Access denied. Admin privileges required.", "error")
            return redirect(url_for("dashboard.index"))

        return f(*args, **kwargs)

    return decorated_function


def optional_auth(f):
    """
    Decorator to mark a route as optionally authenticated.

    This doesn't enforce auth, but loads user if available.
    Useful for routes that work for both guests and logged-in users.

    Usage:
        @app.route('/')
        @optional_auth
        def index():
            user = get_current_user()  # May be None
            if user:
                # Show personalized content
            else:
                # Show guest content
            return render_template('index.html', user=user)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Just trigger user loading (doesn't enforce)
        get_current_user()
        return f(*args, **kwargs)

    return decorated_function


# ============================================================================
# Helper Functions for Templates
# ============================================================================

def inject_auth_context():
    """
    Context processor to inject auth data into all templates.

    Call this from the Flask app factory:
        app.context_processor(inject_auth_context)

    Makes these available in all templates:
        - current_user: User dict or None
        - is_authenticated: Boolean
        - is_premium: Boolean
        - is_in_trial: Boolean
        - trial_days_remaining: Integer
        - profile: User profile dict or None (includes theme_preference)
    """
    user = get_current_user()
    user_id = user.get("id") if user else None

    return {
        "current_user": user,
        "is_authenticated": user is not None,
        "is_premium": supabase_client.is_premium(user_id) if user_id else False,
        "is_in_trial": supabase_client.is_in_trial(user_id) if user_id else False,
        "trial_days_remaining": supabase_client.trial_days_remaining(user_id) if user_id else 0,
        "has_premium_access": supabase_client.has_premium_access(user_id) if user_id else False,
        "profile": supabase_client.get_user_profile(user_id) if user_id else None,
    }
