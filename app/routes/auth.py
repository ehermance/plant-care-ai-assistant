"""
Authentication routes for signup, login, and logout.

Handles:
- Magic link signup/login (passwordless)
- Auth callback from Supabase
- Logout
- Current user info endpoint
"""

from __future__ import annotations
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from app.services import supabase_client
from app.utils.auth import set_session, clear_session, get_current_user, require_auth
from app.extensions import limiter


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("5 per minute; 20 per hour")  # Protect against bot signups
def signup():
    """
    Show signup form or send magic link.

    GET: Display email input form
    POST: Send magic link to email
    """
    if request.method == "GET":
        # Check if user already logged in
        if get_current_user():
            return redirect(url_for("dashboard.index"))

        # Get 'next' parameter to redirect after auth
        next_url = request.args.get("next", "")

        return render_template("auth/signup.html", next=next_url)

    # POST: Send magic link

    # Honeypot check (bot protection)
    honeypot = request.form.get("website", "")
    if honeypot:
        # Bot detected - filled the honeypot field
        current_app.logger.warning(f"Bot signup attempt blocked (honeypot filled)")
        # Pretend it worked to not reveal the honeypot
        from flask import session
        session["pending_email"] = "blocked@example.com"
        return redirect(url_for("auth.check_email"))

    email = request.form.get("email", "").strip().lower()

    if not email:
        flash("Please enter your email address.", "error")
        return redirect(url_for("auth.signup"))

    # Email validation
    # RFC 5322 simplified pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if len(email) > 320:  # RFC 5321 max email length
        flash("Email address is too long.", "error")
        return redirect(url_for("auth.signup"))

    if not re.match(email_pattern, email):
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("auth.signup"))

    # Send magic link via Supabase
    result = supabase_client.send_magic_link(email)

    if result["success"]:
        # Store email in session for display on check_email page
        from flask import session
        session["pending_email"] = email

        return redirect(url_for("auth.check_email"))
    else:
        # Use the user-friendly error message from supabase_client
        error_message = result.get("message", "Failed to send magic link. Please try again.")
        current_app.logger.error(f"Failed to send magic link: {result.get('error')} - {error_message}")
        flash(error_message, "error")
        return redirect(url_for("auth.signup"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Login page (same as signup for magic link auth).

    Redirects to signup since magic link works for both.
    """
    return signup()


@auth_bp.route("/check-email")
def check_email():
    """
    Show "check your email" page after magic link sent.
    """
    from flask import session
    email = session.get("pending_email", "your email")

    return render_template("auth/check_email.html", email=email)


@auth_bp.route("/callback")
def callback():
    """
    Handle magic link callback from Supabase.

    If no tokens in query params, serve the callback.html page which
    extracts tokens from URL hash and redirects back with tokens.

    If tokens present in query params (from callback.html redirect),
    verify and create session.
    """
    # Get tokens from query params (sent by JavaScript from hash)
    access_token = request.args.get("access_token")
    refresh_token = request.args.get("refresh_token")

    # If no tokens, serve the callback handler page
    if not access_token:
        return render_template("auth/callback.html")

    # Verify token and get user (pass both tokens to establish session)
    user = supabase_client.verify_session(access_token, refresh_token)

    if not user:
        flash("Authentication failed. Please try again.", "error")
        return redirect(url_for("auth.signup"))

    # Set session with both tokens
    set_session(user, access_token, refresh_token)

    # Get or create user profile
    user_id = user.get("id")
    email = user.get("email")

    profile = supabase_client.get_user_profile(user_id)

    if not profile:
        # Profile doesn't exist (trigger should have created it, but fallback)
        current_app.logger.warning(f"Profile not found for user {user_id}, creating...")
        supabase_client.create_user_profile(user_id, email)

    # Check if onboarding completed
    # TODO: Uncomment this when onboarding is implemented in Phase 3
    # if not supabase_client.is_onboarding_completed(user_id):
    #     flash(f"Welcome! Let's set up your first plant.", "success")
    #     return redirect(url_for("onboarding.step1"))

    # Redirect to dashboard or 'next' URL (with open redirect protection)
    next_url = request.args.get("next", "")
    if next_url:
        from urllib.parse import urlparse
        parsed = urlparse(next_url)
        # Only allow relative URLs with no scheme or netloc (prevents //evil.com)
        if parsed.scheme == '' and parsed.netloc == '' and next_url.startswith("/") and not next_url.startswith("//"):
            flash(f"Welcome back, {email}!", "success")
            return redirect(next_url)

    # Check if this is a new signup (profile just created)
    is_new_user = profile is None or not supabase_client.is_onboarding_completed(user_id)

    if is_new_user:
        flash(f"Welcome to PlantCareAI! Let's add your first plant 🌱", "success")
    else:
        flash(f"Welcome back!", "success")

    return redirect(url_for("dashboard.index"))


@auth_bp.route("/logout")
@require_auth
def logout():
    """
    Log out current user and clear session.
    """
    from flask import session
    access_token = session.get("access_token")

    if access_token:
        supabase_client.sign_out(access_token)

    clear_session()
    flash("You've been logged out successfully.", "info")

    return redirect(url_for("auth.signup"))


@auth_bp.route("/me")
@require_auth
def me():
    """
    Get current user info as JSON (for client-side use).

    Returns:
        JSON with user info, profile, trial status
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401

    user_id = user.get("id")
    profile = supabase_client.get_user_profile(user_id)

    return jsonify({
        "user": {
            "id": user.get("id"),
            "email": user.get("email"),
        },
        "profile": {
            "plan": profile.get("plan") if profile else "free",
            "is_premium": supabase_client.is_premium(user_id),
            "is_in_trial": supabase_client.is_in_trial(user_id),
            "trial_days_remaining": supabase_client.trial_days_remaining(user_id),
            "has_premium_access": supabase_client.has_premium_access(user_id),
            "onboarding_completed": supabase_client.is_onboarding_completed(user_id),
        }
    })
