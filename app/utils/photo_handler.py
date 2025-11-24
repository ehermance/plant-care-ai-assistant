"""
Photo handling utilities for plant and journal photo uploads.

Consolidated photo upload logic to eliminate duplication across routes.
Handles photo upload, validation, version creation, and deletion.
"""

from __future__ import annotations
from typing import Tuple, Optional, Dict, Any, Callable
from werkzeug.utils import secure_filename
from flask import flash
from .file_upload import validate_upload_file
from app.services import supabase_client


def handle_photo_upload(file, user_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Handle photo upload with validation and version creation.

    Consolidates the common photo upload pattern used across plants and journal routes:
    1. Initialize URL variables
    2. Validate uploaded file
    3. Upload to Supabase with version creation (original, display, thumbnail)
    4. Extract and return URLs

    Args:
        file: FileStorage object from Flask request.files
        user_id: User's UUID for upload authorization

    Returns:
        Tuple of (photo_url, photo_url_original, photo_url_thumb)
        All values are None if no file provided or upload failed

    Example:
        >>> file = request.files.get("photo")
        >>> photo_url, photo_url_original, photo_url_thumb = handle_photo_upload(file, user_id)
        >>> if photo_url:
        ...     # Use the URLs to save to database
    """
    # Initialize URL variables
    photo_url = None
    photo_url_original = None
    photo_url_thumb = None

    # Validate file
    is_valid, error, file_bytes = validate_upload_file(file)

    if error:  # Validation failed
        flash(error, "error")
        return None, None, None

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

    return photo_url, photo_url_original, photo_url_thumb


def delete_all_photo_versions(
    obj: Dict[str, Any],
    delete_func: Optional[Callable[[str], Any]] = None
) -> None:
    """
    Delete all photo versions for an object (plant or journal entry).

    Consolidates the common photo deletion pattern:
    - Checks for existence of 3 photo URL types
    - Deletes each existing photo version

    Args:
        obj: Dictionary containing photo URLs (photo_url, photo_url_original, photo_url_thumb)
        delete_func: Optional custom delete function. Defaults to supabase_client.delete_plant_photo

    Example:
        >>> plant = get_plant_by_id(plant_id, user_id)
        >>> delete_all_photo_versions(plant)
        >>> # All 3 photo versions deleted from storage
    """
    if delete_func is None:
        delete_func = supabase_client.delete_plant_photo

    # Delete all photo versions if they exist
    if obj.get("photo_url"):
        delete_func(obj["photo_url"])
    if obj.get("photo_url_original"):
        delete_func(obj["photo_url_original"])
    if obj.get("photo_url_thumb"):
        delete_func(obj["photo_url_thumb"])


def extract_photo_urls(photo_urls_dict: Optional[Dict[str, str]]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract photo URLs from upload result dictionary.

    Helper to safely extract the 3 URL types from the upload result.

    Args:
        photo_urls_dict: Dictionary with keys 'display', 'original', 'thumbnail'

    Returns:
        Tuple of (photo_url, photo_url_original, photo_url_thumb)

    Example:
        >>> upload_result = upload_plant_photo_versions(...)
        >>> display, original, thumb = extract_photo_urls(upload_result)
    """
    if not photo_urls_dict:
        return None, None, None

    return (
        photo_urls_dict.get('display'),
        photo_urls_dict.get('original'),
        photo_urls_dict.get('thumbnail')
    )
