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
from app.services import supabase_client
from PIL import Image
from io import BytesIO
import os


plants_bp = Blueprint("plants", __name__, url_prefix="/plants")

# Allowed image file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def allowed_file(filename: str) -> bool:
    """Check if filename has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_image_content(file_bytes: bytes) -> bool:
    """
    Validate that file content is actually a valid image.

    This prevents malicious files with spoofed extensions by checking
    the actual file content (magic numbers/file signature).

    Args:
        file_bytes: The file content as bytes

    Returns:
        True if valid image, False otherwise
    """
    try:
        img = Image.open(BytesIO(file_bytes))
        img.verify()  # Verify it's a valid image
        return True
    except Exception:
        return False


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
        if "photo" in request.files:
            file = request.files["photo"]
            if file and file.filename and allowed_file(file.filename):
                # Check file size
                file.seek(0, os.SEEK_END)
                file_length = file.tell()
                if file_length > MAX_FILE_SIZE:
                    flash("Photo must be less than 5MB.", "error")
                    return render_template("plants/add.html")

                file.seek(0)  # Reset file pointer
                file_bytes = file.read()

                # Validate actual file content (prevents malicious files with spoofed extensions)
                if not validate_image_content(file_bytes):
                    flash("Invalid image file. Please upload a valid image.", "error")
                    return render_template("plants/add.html")

                photo_url = supabase_client.upload_plant_photo(
                    file_bytes,
                    user_id,
                    secure_filename(file.filename)
                )

                if not photo_url:
                    flash("Failed to upload photo. Please try again.", "error")

        # Create plant
        plant_data = {
            "name": name,
            "species": species,
            "nickname": nickname,
            "location": location,
            "light": light,
            "notes": notes,
            "photo_url": photo_url
        }

        plant = supabase_client.create_plant(user_id, plant_data)
        if plant:
            flash(f"🌱 {name} added successfully!", "success")
            return redirect(url_for("plants.view", plant_id=plant["id"]))
        else:
            flash("Failed to add plant. Please try again.", "error")

    return render_template("plants/add.html")


@plants_bp.route("/<plant_id>")
@require_auth
def view(plant_id):
    """View a single plant's details."""
    user_id = get_current_user_id()
    if not user_id:
        flash("Please log in to view plants.", "error")
        return redirect(url_for("auth.login"))

    plant = supabase_client.get_plant_by_id(plant_id, user_id)
    if not plant:
        flash("Plant not found.", "error")
        return redirect(url_for("plants.index"))

    return render_template("plants/view.html", plant=plant)


@plants_bp.route("/<plant_id>/edit", methods=["GET", "POST"])
@require_auth
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

        # Handle photo upload
        photo_url = plant.get("photo_url")  # Keep existing photo by default
        if "photo" in request.files:
            file = request.files["photo"]
            if file and file.filename and allowed_file(file.filename):
                # Check file size
                file.seek(0, os.SEEK_END)
                file_length = file.tell()
                if file_length > MAX_FILE_SIZE:
                    flash("Photo must be less than 5MB.", "error")
                    return render_template("plants/edit.html", plant=plant)

                file.seek(0)
                file_bytes = file.read()

                # Validate actual file content (prevents malicious files with spoofed extensions)
                if not validate_image_content(file_bytes):
                    flash("Invalid image file. Please upload a valid image.", "error")
                    return render_template("plants/edit.html", plant=plant)

                new_photo_url = supabase_client.upload_plant_photo(
                    file_bytes,
                    user_id,
                    secure_filename(file.filename)
                )

                if new_photo_url:
                    # Delete old photo if it exists
                    if photo_url:
                        supabase_client.delete_plant_photo(photo_url)
                    photo_url = new_photo_url
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
            "photo_url": photo_url
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

    # Delete photo if it exists
    if plant.get("photo_url"):
        supabase_client.delete_plant_photo(plant["photo_url"])

    # Delete plant
    if supabase_client.delete_plant(plant_id, user_id):
        flash(f"🗑️ {plant_name} removed from your collection.", "success")
    else:
        flash("Failed to delete plant. Please try again.", "error")

    return redirect(url_for("plants.index"))
