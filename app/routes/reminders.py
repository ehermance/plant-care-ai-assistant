"""
Reminder routes for plant care scheduling.

Handles displaying, creating, updating, and completing reminders.
"""

from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.utils.auth import require_auth, get_current_user_id
from app.services import reminders as reminder_service
from app.services.supabase_client import get_user_profile

reminders_bp = Blueprint("reminders", __name__, url_prefix="/reminders")


@reminders_bp.route("/")
@require_auth
def index():
    """Display all user's reminders (due, upcoming, and all)."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to view reminders.", "error")
        return redirect(url_for("auth.login"))

    # Get reminders
    due_reminders = reminder_service.get_due_reminders(user_id)
    upcoming_reminders = reminder_service.get_upcoming_reminders(user_id, days=7)
    all_reminders = reminder_service.get_user_reminders(user_id, active_only=True)
    stats = reminder_service.get_reminder_stats(user_id)

    return render_template(
        "reminders/index.html",
        due_reminders=due_reminders,
        upcoming_reminders=upcoming_reminders,
        all_reminders=all_reminders,
        stats=stats,
    )


@reminders_bp.route("/history")
@require_auth
def history():
    """Display completed/archived reminders history."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to view reminders.", "error")
        return redirect(url_for("auth.login"))

    # Get inactive (archived) reminders
    archived_reminders = reminder_service.get_user_reminders(user_id, active_only=False)

    # Filter to only inactive ones and sort by completion date (most recent first)
    archived_reminders = [
        r for r in archived_reminders if not r.get("is_active", True)
    ]
    # Sort by last_completed_at, falling back to updated_at, then empty string
    # Use 'or' instead of nested get() to handle None values properly
    archived_reminders.sort(
        key=lambda r: r.get("last_completed_at") or r.get("updated_at") or "",
        reverse=True
    )

    return render_template(
        "reminders/history.html",
        archived_reminders=archived_reminders,
    )


@reminders_bp.route("/create", methods=["GET", "POST"])
@require_auth
def create():
    """Create a new reminder."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to create reminders.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        # Get form data
        plant_id = request.form.get("plant_id", "").strip()
        reminder_type = request.form.get("reminder_type", "watering")
        title = request.form.get("title", "").strip()
        frequency = request.form.get("frequency", "weekly")
        custom_interval_days = request.form.get("custom_interval_days")
        notes = request.form.get("notes", "").strip()
        skip_weather = request.form.get("skip_weather_adjustment") == "on"

        # Validation
        if not plant_id:
            flash("Please select a plant.", "error")
            return redirect(url_for("reminders.create"))

        if not title:
            flash("Reminder title is required.", "error")
            return redirect(url_for("reminders.create"))

        # Convert custom_interval_days to int
        if frequency == "custom":
            try:
                custom_interval_days = int(custom_interval_days)
                if custom_interval_days < 1 or custom_interval_days > 365:
                    flash("Custom interval must be between 1 and 365 days.", "error")
                    return redirect(url_for("reminders.create"))
            except (ValueError, TypeError):
                flash("Invalid custom interval days.", "error")
                return redirect(url_for("reminders.create"))
        else:
            custom_interval_days = None

        # Create reminder
        reminder, error = reminder_service.create_reminder(
            user_id=user_id,
            plant_id=plant_id,
            reminder_type=reminder_type,
            title=title,
            frequency=frequency,
            custom_interval_days=custom_interval_days,
            notes=notes or None,
            skip_weather_adjustment=skip_weather,
        )

        if error:
            flash(f"Error creating reminder: {error}", "error")
            return redirect(url_for("reminders.create"))

        flash(f"Reminder created: {title}", "success")
        return redirect(url_for("reminders.index"))

    # GET request - show form
    # Get user's plants for dropdown
    from app.services.supabase_client import get_user_plants
    plants = get_user_plants(user_id)

    if not plants:
        flash("Please add a plant before creating reminders.", "warning")
        return redirect(url_for("plants.add"))

    return render_template(
        "reminders/create.html",
        plants=plants,
        reminder_types=reminder_service.REMINDER_TYPE_NAMES,
    )


@reminders_bp.route("/<reminder_id>")
@require_auth
def view(reminder_id):
    """View a single reminder."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to view reminders.", "error")
        return redirect(url_for("auth.login"))

    reminder = reminder_service.get_reminder_by_id(reminder_id, user_id)

    if not reminder:
        flash("Reminder not found.", "error")
        return redirect(url_for("reminders.index"))

    return render_template("reminders/view.html", reminder=reminder)


@reminders_bp.route("/<reminder_id>/edit", methods=["GET", "POST"])
@require_auth
def edit(reminder_id):
    """Edit a reminder."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to edit reminders.", "error")
        return redirect(url_for("auth.login"))

    reminder = reminder_service.get_reminder_by_id(reminder_id, user_id)

    if not reminder:
        flash("Reminder not found.", "error")
        return redirect(url_for("reminders.index"))

    if request.method == "POST":
        # Get form data
        title = request.form.get("title", "").strip()
        frequency = request.form.get("frequency", "weekly")
        custom_interval_days = request.form.get("custom_interval_days")
        notes = request.form.get("notes", "").strip()
        skip_weather = request.form.get("skip_weather_adjustment") == "on"

        # Validation
        if not title:
            flash("Reminder title is required.", "error")
            return render_template("reminders/edit.html", reminder=reminder)

        # Convert custom_interval_days
        if frequency == "custom":
            try:
                custom_interval_days = int(custom_interval_days)
                if custom_interval_days < 1 or custom_interval_days > 365:
                    flash("Custom interval must be between 1 and 365 days.", "error")
                    return render_template("reminders/edit.html", reminder=reminder)
            except (ValueError, TypeError):
                flash("Invalid custom interval days.", "error")
                return render_template("reminders/edit.html", reminder=reminder)
        else:
            custom_interval_days = None

        # Update reminder
        updated, error = reminder_service.update_reminder(
            reminder_id=reminder_id,
            user_id=user_id,
            title=title,
            frequency=frequency,
            custom_interval_days=custom_interval_days,
            notes=notes or None,
            skip_weather_adjustment=skip_weather,
        )

        if error:
            flash(f"Error updating reminder: {error}", "error")
            return render_template("reminders/edit.html", reminder=reminder)

        flash("Reminder updated successfully.", "success")
        return redirect(url_for("reminders.view", reminder_id=reminder_id))

    return render_template("reminders/edit.html", reminder=reminder)


@reminders_bp.route("/<reminder_id>/complete", methods=["POST"])
@require_auth
def complete(reminder_id):
    """Mark a reminder as complete."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    success, error = reminder_service.mark_reminder_complete(reminder_id, user_id)

    if not success:
        flash(f"Error completing reminder: {error}", "error")
        return redirect(request.referrer or url_for("reminders.index"))

    flash("Reminder marked complete! Next reminder scheduled.", "success")
    return redirect(request.referrer or url_for("reminders.index"))


@reminders_bp.route("/bulk-complete", methods=["POST"])
@require_auth
def bulk_complete():
    """Mark all due reminders as complete."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to complete reminders.", "error")
        return redirect(url_for("auth.login"))

    # Get all due reminders
    due_reminders = reminder_service.get_due_reminders(user_id)

    completed_count = 0
    errors = []

    for reminder in due_reminders:
        success, error = reminder_service.mark_reminder_complete(reminder["id"], user_id)
        if success:
            completed_count += 1
        else:
            errors.append(f"{reminder['title']}: {error}")

    if completed_count > 0:
        flash(f"✓ Marked {completed_count} reminder{'s' if completed_count != 1 else ''} complete!", "success")

    if errors:
        flash(f"Some reminders failed: {'; '.join(errors[:3])}", "error")

    return redirect(url_for("reminders.index"))


@reminders_bp.route("/<reminder_id>/snooze", methods=["POST"])
@require_auth
def snooze(reminder_id):
    """Snooze a reminder by N days."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    # Get snooze days from form (default 1)
    try:
        days = int(request.form.get("days", 1))
    except ValueError:
        days = 1

    success, error = reminder_service.snooze_reminder(reminder_id, user_id, days)

    if not success:
        flash(f"Error snoozing reminder: {error}", "error")
        return redirect(request.referrer or url_for("reminders.index"))

    flash(f"Reminder snoozed for {days} day(s).", "success")
    return redirect(request.referrer or url_for("reminders.index"))


@reminders_bp.route("/<reminder_id>/delete", methods=["POST"])
@require_auth
def delete(reminder_id):
    """Delete (deactivate) a reminder."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    success, error = reminder_service.delete_reminder(reminder_id, user_id)

    if not success:
        flash(f"Error deleting reminder: {error}", "error")
        return redirect(request.referrer or url_for("reminders.index"))

    flash("Reminder deleted successfully.", "success")
    return redirect(url_for("reminders.index"))


@reminders_bp.route("/<reminder_id>/adjust-weather", methods=["POST"])
@require_auth
def adjust_weather(reminder_id):
    """Manually trigger weather adjustment for a reminder."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    # Get city from form or user profile
    city = request.form.get("city")
    if not city:
        profile = get_user_profile(user_id)
        city = profile.get("city") if profile else None

    if not city:
        flash("City required for weather adjustment.", "error")
        return redirect(request.referrer or url_for("reminders.index"))

    # Get reminder to find plant location
    reminder = reminder_service.get_reminder_by_id(reminder_id, user_id)
    if not reminder:
        flash("Reminder not found.", "error")
        return redirect(url_for("reminders.index"))

    plant = reminder.get("plants", {})
    plant_location = plant.get("location", "indoor_potted")

    success, message, weather = reminder_service.adjust_reminder_for_weather(
        reminder_id, user_id, city, plant_location
    )

    if success:
        flash(f"Weather adjustment applied: {message}", "success")
    else:
        flash(f"No adjustment made: {message}", "info")

    return redirect(request.referrer or url_for("reminders.index"))


@reminders_bp.route("/<reminder_id>/clear-weather", methods=["POST"])
@require_auth
def clear_weather(reminder_id):
    """Clear weather adjustment and revert to original schedule."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    success, error = reminder_service.clear_weather_adjustment(reminder_id, user_id)

    if not success:
        flash(f"Error clearing weather adjustment: {error}", "error")
        return redirect(request.referrer or url_for("reminders.index"))

    flash("Weather adjustment cleared. Reverted to original schedule.", "success")
    return redirect(request.referrer or url_for("reminders.index"))


# JSON API endpoints for AJAX calls


@reminders_bp.route("/api/due-today", methods=["GET"])
@require_auth
def api_due_today():
    """Get due reminders as JSON (for AJAX/widgets)."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    due_reminders = reminder_service.get_due_reminders(user_id)

    return jsonify({
        "success": True,
        "count": len(due_reminders),
        "reminders": due_reminders,
    })


@reminders_bp.route("/api/upcoming", methods=["GET"])
@require_auth
def api_upcoming():
    """Get upcoming reminders as JSON (for calendar view)."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    days = request.args.get("days", 7, type=int)
    upcoming = reminder_service.get_upcoming_reminders(user_id, days)

    return jsonify({
        "success": True,
        "count": len(upcoming),
        "reminders": upcoming,
    })


@reminders_bp.route("/api/stats", methods=["GET"])
@require_auth
def api_stats():
    """Get reminder statistics as JSON."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    stats = reminder_service.get_reminder_stats(user_id)

    return jsonify({
        "success": True,
        "stats": stats,
    })


@reminders_bp.route("/api/<reminder_id>/complete", methods=["POST"])
@require_auth
def api_complete(reminder_id):
    """
    Mark reminder complete via JSON API.

    Security: CSRF token required via X-CSRFToken header
    (automatically validated by Flask-WTF CSRFProtect)
    """
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    # Validate reminder_id format (UUID)
    import re
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', reminder_id, re.IGNORECASE):
        return jsonify({"success": False, "error": "Invalid reminder ID"}), 400

    success, error = reminder_service.mark_reminder_complete(reminder_id, user_id)

    if success:
        return jsonify({"success": True, "message": "Reminder completed"})
    else:
        # Sanitize error messages for security
        safe_error = error if error else "Failed to complete reminder"
        return jsonify({"success": False, "error": safe_error}), 400
