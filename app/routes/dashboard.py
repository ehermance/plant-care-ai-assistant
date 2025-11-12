"""
Dashboard routes for authenticated users.

Shows:
- Plant collection
- Reminders due today
- Trial status
- Quick stats
"""

from __future__ import annotations
from flask import Blueprint, render_template, redirect, url_for, request, flash
from app.utils.auth import require_auth, get_current_user_id
from app.services import supabase_client
from app.services import reminders as reminder_service


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

    # Get user plants
    plants = supabase_client.get_user_plants(user_id, 4, 0)

    # Get reminder stats and due reminders
    reminder_stats = reminder_service.get_reminder_stats(user_id)
    due_reminders = reminder_service.get_due_reminders(user_id)

    return render_template(
        "dashboard/index.html",
        profile=profile,
        plant_count=plant_count,
        is_premium=is_premium,
        is_in_trial=is_in_trial,
        trial_days=trial_days,
        has_premium_access=has_premium_access,
        plants=plants,
        reminder_stats=reminder_stats,
        due_reminders=due_reminders,
    )


@dashboard_bp.route("/account", methods=["GET", "POST"])
@require_auth
def account():
    """
    Account settings page.

    GET: Shows account settings form
    POST: Updates user preferences (city)

    Shows:
    - Email
    - Plan type
    - Subscription management
    - Location preferences
    """
    user_id = get_current_user_id()
    profile = supabase_client.get_user_profile(user_id)

    if request.method == "POST":
        # Track if any updates were made
        updates_made = []

        # Handle city update
        city = request.form.get("city", "").strip()
        if "city" in request.form:  # Only update if field is present
            success, error = supabase_client.update_user_city(user_id, city)
            if success:
                if city:
                    updates_made.append("location")
                else:
                    updates_made.append("location (cleared)")
            else:
                flash(f"Failed to update location: {error}", "error")

        # Handle theme update
        theme = request.form.get("theme", "").strip().lower()
        if theme and theme in ["light", "dark", "auto"]:
            success, error = supabase_client.update_user_theme(user_id, theme)
            if success:
                updates_made.append("theme")
            else:
                flash(f"Failed to update theme: {error}", "error")

        # Show success message if any updates were made
        if updates_made:
            flash(f"Preferences updated: {', '.join(updates_made)}", "success")
            # Refresh profile to show updated data
            profile = supabase_client.get_user_profile(user_id)

    return render_template(
        "dashboard/account.html",
        profile=profile,
    )
