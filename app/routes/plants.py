"""
Plants management routes.

Handles:
- Plant listing (grid view)
- Adding new plants with photo upload
- Viewing/editing individual plants
- Plant deletion with photo cleanup
"""

from __future__ import annotations
from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app
from werkzeug.utils import secure_filename
from app.utils.auth import require_auth, get_current_user_id
from app.utils.file_upload import validate_upload_file
from app.services import supabase_client
from app.services import analytics
from app.extensions import limiter


plants_bp = Blueprint("plants", __name__, url_prefix="/plants")


@plants_bp.route("/")
@require_auth
def index():
    """Plant library - list all user's plants in grid view."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to view your plants.", "error")
        return redirect(url_for("auth.login"))

    plants = supabase_client.get_user_plants(user_id)
    plant_count = len(plants)

    return render_template(
        "plants/index.html",
        plants=plants,
        plant_count=plant_count
    )


@plants_bp.route("/add", methods=["GET", "POST"])
@require_auth
@limiter.limit(lambda: current_app.config['UPLOAD_RATE_LIMIT'])
def add():
    """Add a new plant to the user's collection."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to add plants.", "error")
        return redirect(url_for("auth.login"))

    # Check if user can add more plants
    can_add, message = supabase_client.can_add_plant(user_id)
    if not can_add:
        flash(message, "warning")
        return redirect(url_for("plants.index"))

    if request.method == "POST":
        # Get form data
        name = request.form.get("name", "").strip()
        species = request.form.get("species", "").strip()
        nickname = request.form.get("nickname", "").strip()
        location = request.form.get("location", "").strip()
        light = request.form.get("light", "").strip()
        notes = request.form.get("notes", "").strip()

        # Validation
        if not name:
            flash("Plant name is required.", "error")
            return render_template("plants/add.html")

        # Handle photo upload
        photo_url = None
        photo_url_original = None
        photo_url_thumb = None
        file = request.files.get("photo")
        is_valid, error, file_bytes = validate_upload_file(file)

        if error:  # Validation failed
            flash(error, "error")
            return render_template("plants/add.html")

        if is_valid and file_bytes:  # File provided and valid
            # Upload photo with optimized versions (original, display, thumbnail)
            photo_urls = supabase_client.upload_plant_photo_versions(
                file_bytes,
                user_id,
                secure_filename(file.filename)
            )

            if photo_urls:
                photo_url = photo_urls['display']
                photo_url_original = photo_urls['original']
                photo_url_thumb = photo_urls['thumbnail']
            else:
                flash("Failed to upload photo. Please try again.", "error")

        # Create plant
        plant_data = {
            "name": name,
            "species": species,
            "nickname": nickname,
            "location": location,
            "light": light,
            "notes": notes,
            "photo_url": photo_url,
            "photo_url_original": photo_url_original if photo_url else None,
            "photo_url_thumb": photo_url_thumb if photo_url else None
        }

        plant = supabase_client.create_plant(user_id, plant_data)
        if plant:
            # Track analytics event
            analytics.track_event(
                user_id,
                analytics.EVENT_PLANT_ADDED,
                {"plant_id": plant["id"], "plant_name": name}
            )
            flash(f"🌱 {name} added successfully!", "success")
            return redirect(url_for("plants.view", plant_id=plant["id"]))
        else:
            flash("Failed to add plant. Please try again.", "error")

    return render_template("plants/add.html")


@plants_bp.route("/<plant_id>")
@require_auth
def view(plant_id):
    """View a single plant's details with journal entries."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to view plants.", "error")
        return redirect(url_for("auth.login"))

    plant = supabase_client.get_plant_by_id(plant_id, user_id)
    if not plant:
        flash("Plant not found.", "error")
        return redirect(url_for("plants.index"))

    # Get journal data
    from app.services import journal as journal_service
    recent_actions = journal_service.get_plant_actions(plant_id, user_id, limit=5)
    stats = journal_service.get_action_stats(plant_id, user_id)

    return render_template(
        "plants/view.html",
        plant=plant,
        recent_actions=recent_actions,
        stats=stats,
        action_type_names=journal_service.ACTION_TYPE_NAMES,
        action_type_emojis=journal_service.ACTION_TYPE_EMOJIS,
    )


@plants_bp.route("/<plant_id>/edit", methods=["GET", "POST"])
@require_auth
@limiter.limit(lambda: current_app.config['UPLOAD_RATE_LIMIT'])
def edit(plant_id):
    """Edit plant information."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to edit plants.", "error")
        return redirect(url_for("auth.login"))

    plant = supabase_client.get_plant_by_id(plant_id, user_id)
    if not plant:
        flash("Plant not found.", "error")
        return redirect(url_for("plants.index"))

    if request.method == "POST":
        # Get form data
        name = request.form.get("name", "").strip()
        species = request.form.get("species", "").strip()
        nickname = request.form.get("nickname", "").strip()
        location = request.form.get("location", "").strip()
        light = request.form.get("light", "").strip()
        notes = request.form.get("notes", "").strip()

        # Validation
        if not name:
            flash("Plant name is required.", "error")
            return render_template("plants/edit.html", plant=plant)

        # Handle photo upload - keep existing photos by default
        photo_url = plant.get("photo_url")
        photo_url_original = plant.get("photo_url_original")
        photo_url_thumb = plant.get("photo_url_thumb")

        file = request.files.get("photo")
        is_valid, error, file_bytes = validate_upload_file(file)

        if error:  # Validation failed
            flash(error, "error")
            return render_template("plants/edit.html", plant=plant)

        if is_valid and file_bytes:  # New photo provided and valid
            # Upload new photo with optimized versions
            new_photo_urls = supabase_client.upload_plant_photo_versions(
                file_bytes,
                user_id,
                secure_filename(file.filename)
            )

            if new_photo_urls:
                # Delete old photos if they exist
                if photo_url:
                    supabase_client.delete_plant_photo(photo_url)
                if photo_url_original:
                    supabase_client.delete_plant_photo(photo_url_original)
                if photo_url_thumb:
                    supabase_client.delete_plant_photo(photo_url_thumb)

                # Set new photo URLs
                photo_url = new_photo_urls['display']
                photo_url_original = new_photo_urls['original']
                photo_url_thumb = new_photo_urls['thumbnail']
            else:
                flash("Failed to upload new photo.", "error")

        # Update plant
        plant_data = {
            "name": name,
            "species": species,
            "nickname": nickname,
            "location": location,
            "light": light,
            "notes": notes,
            "photo_url": photo_url,
            "photo_url_original": photo_url_original,
            "photo_url_thumb": photo_url_thumb
        }

        updated_plant = supabase_client.update_plant(plant_id, user_id, plant_data)
        if updated_plant:
            flash(f"✨ {name} updated successfully!", "success")
            return redirect(url_for("plants.view", plant_id=plant_id))
        else:
            flash("Failed to update plant. Please try again.", "error")

    return render_template("plants/edit.html", plant=plant)


@plants_bp.route("/<plant_id>/delete", methods=["POST"])
@require_auth
def delete(plant_id):
    """Delete a plant from the user's collection."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to delete plants.", "error")
        return redirect(url_for("auth.login"))

    plant = supabase_client.get_plant_by_id(plant_id, user_id)
    if not plant:
        flash("Plant not found.", "error")
        return redirect(url_for("plants.index"))

    plant_name = plant.get("name", "Plant")

    # Delete all photo versions if they exist
    if plant.get("photo_url"):
        supabase_client.delete_plant_photo(plant["photo_url"])
    if plant.get("photo_url_original"):
        supabase_client.delete_plant_photo(plant["photo_url_original"])
    if plant.get("photo_url_thumb"):
        supabase_client.delete_plant_photo(plant["photo_url_thumb"])

    # Delete plant
    if supabase_client.delete_plant(plant_id, user_id):
        flash(f"🗑️ {plant_name} removed from your collection.", "success")
    else:
        flash("Failed to delete plant. Please try again.", "error")

    return redirect(url_for("plants.index"))
