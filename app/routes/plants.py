"""
Plants management routes.

Handles:
- Plant listing
- Adding new plants
- Viewing/editing individual plants
- Plant care tracking

TODO: Implement full plant management functionality in Phase 4
"""

from __future__ import annotations
from flask import Blueprint, render_template, flash, redirect, url_for
from app.utils.auth import require_auth


plants_bp = Blueprint("plants", __name__, url_prefix="/plants")


@plants_bp.route("/")
@require_auth
def index():
    """
    Plant library - list all user's plants.

    TODO: Phase 4 - Implement full plant listing with:
    - Grid/list view of plants with photos
    - Sorting/filtering options
    - Quick care status indicators
    """
    flash("Plant library coming soon! We're working hard to bring you this feature.", "info")
    return redirect(url_for("dashboard.index"))


@plants_bp.route("/add", methods=["GET", "POST"])
@require_auth
def add():
    """
    Add a new plant to the user's collection.

    TODO: Phase 4 - Implement plant creation form with:
    - Plant name, species, variety
    - Location (indoor/outdoor)
    - Photo upload
    - Initial care schedule setup
    """
    flash("Adding plants is coming soon! We're building this feature now.", "info")
    return redirect(url_for("dashboard.index"))


@plants_bp.route("/<plant_id>")
@require_auth
def view(plant_id):
    """
    View a single plant's details and care history.

    TODO: Phase 4 - Implement plant detail page with:
    - Plant info and photo gallery
    - Care timeline (watering, fertilizing, etc.)
    - Health notes and observations
    - Care schedule management
    """
    flash("Plant details page coming soon!", "info")
    return redirect(url_for("dashboard.index"))


@plants_bp.route("/<plant_id>/edit", methods=["GET", "POST"])
@require_auth
def edit(plant_id):
    """
    Edit plant information.

    TODO: Phase 4 - Implement plant editing form
    """
    flash("Plant editing coming soon!", "info")
    return redirect(url_for("dashboard.index"))


@plants_bp.route("/<plant_id>/delete", methods=["POST"])
@require_auth
def delete(plant_id):
    """
    Delete a plant from the user's collection.

    TODO: Phase 4 - Implement plant deletion with confirmation
    """
    flash("Plant management features coming soon!", "info")
    return redirect(url_for("dashboard.index"))
