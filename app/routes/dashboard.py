"""
Dashboard routes for authenticated users.

Shows:
- Plant collection
- Reminders due today
- Trial status
- Quick stats
"""

from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for
from app.utils.auth import require_auth, get_current_user_id
from app.services import supabase_client


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@require_auth
def index():
    """
    Main dashboard view.

    Shows:
    - Greeting
    - Trial status banner (if applicable)
    - Plant count
    - Reminders due today (placeholder for now)
    - Quick actions
    """
    user_id = get_current_user_id()

    # Get user profile and stats
    profile = supabase_client.get_user_profile(user_id)
    plant_count = supabase_client.get_plant_count(user_id)
    is_premium = supabase_client.is_premium(user_id)
    is_in_trial = supabase_client.is_in_trial(user_id)
    trial_days = supabase_client.trial_days_remaining(user_id)
    has_premium_access = supabase_client.has_premium_access(user_id)

    return render_template(
        "dashboard/index.html",
        profile=profile,
        plant_count=plant_count,
        is_premium=is_premium,
        is_in_trial=is_in_trial,
        trial_days=trial_days,
        has_premium_access=has_premium_access,
    )


@dashboard_bp.route("/account")
@require_auth
def account():
    """
    Account settings page.

    Shows:
    - Email
    - Plan type
    - Subscription management
    """
    user_id = get_current_user_id()
    profile = supabase_client.get_user_profile(user_id)

    return render_template(
        "dashboard/account.html",
        profile=profile,
    )
