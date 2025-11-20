"""
Supabase client initialization and helper functions.

Provides centralized access to Supabase for:
- Authentication (Magic Link)
- Database queries (plants, reminders, profiles)
- Storage (photo uploads)
"""

from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from flask import current_app, has_app_context
from supabase import create_client, Client


def _safe_log_error(message: str) -> None:
    """
    Log error message only if Flask app context is available.

    This allows functions to be called from tests without app context.
    In production, errors are logged to current_app.logger.
    In tests without app context, errors are silently ignored.
    """
    try:
        if has_app_context():
            current_app.logger.error(message)
    except (ImportError, RuntimeError):
        pass  # Ignore if no app context available (e.g., in tests)


def _safe_log_info(message: str) -> None:
    """Log info message only if Flask app context is available."""
    try:
        if has_app_context():
            current_app.logger.info(message)
    except (ImportError, RuntimeError):
        pass


# Global client instances (initialized once per app)
_supabase_client: Optional[Client] = None  # User client (anon key)
_supabase_admin: Optional[Client] = None   # Admin client (service role key)

# In-memory cache for plant queries (simple dict-based cache)
# Format: {cache_key: (data, timestamp)}
_PLANT_CACHE: Dict[str, tuple[list[dict], datetime]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def init_supabase(app) -> None:
    """
    Initialize Supabase clients with app config.
    Creates two clients:
    - Regular client with anon key (for user operations)
    - Admin client with service role key (for admin operations like creating profiles)

    Call this from the Flask app factory.
    """
    global _supabase_client, _supabase_admin

    url = app.config.get("SUPABASE_URL", "")
    anon_key = app.config.get("SUPABASE_ANON_KEY", "")
    service_key = app.config.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not anon_key:
        app.logger.warning("Supabase URL or ANON_KEY not configured. Supabase features will be disabled.")
        _supabase_client = None
        _supabase_admin = None
        return

    try:
        # Regular client for user operations
        _supabase_client = create_client(url, anon_key)
        app.logger.info("Supabase client initialized successfully")

        # Admin client for admin operations (if service key available)
        if service_key:
            _supabase_admin = create_client(url, service_key)
            app.logger.info("Supabase admin client initialized successfully")
        else:
            app.logger.warning("SUPABASE_SERVICE_ROLE_KEY not configured. Admin operations will be limited.")

    except Exception as e:
        app.logger.error(f"Failed to initialize Supabase client: {e}")
        _supabase_client = None
        _supabase_admin = None


def get_client() -> Optional[Client]:
    """Get the global Supabase client instance (user client with anon key)."""
    return _supabase_client


def get_admin_client() -> Optional[Client]:
    """Get the admin Supabase client instance (admin client with service role key)."""
    return _supabase_admin


def is_configured() -> bool:
    """Check if Supabase is properly configured."""
    return _supabase_client is not None


# ============================================================================
# Authentication Helpers
# ============================================================================

def send_magic_link(email: str) -> Dict[str, Any]:
    """
    Send a magic link to the user's email for passwordless login.

    Args:
        email: User's email address

    Returns:
        Dict with 'success' bool and 'message' or 'error'
    """
    if not _supabase_client:
        return {"success": False, "error": "Supabase not configured"}

    try:
        # Supabase Auth will automatically send magic link email
        response = _supabase_client.auth.sign_in_with_otp({
            "email": email,
            "options": {
                "email_redirect_to": current_app.config.get("SUPABASE_REDIRECT_URL", "http://localhost:5000/auth/callback")
            }
        })

        return {
            "success": True,
            "message": f"Magic link sent to {email}. Please check your inbox."
        }
    except Exception as e:
        error_msg = str(e).lower()
        _safe_log_error(f"Error sending magic link: {e}")

        # Detect rate limiting errors
        if "rate limit" in error_msg or "too many requests" in error_msg:
            return {
                "success": False,
                "error": "rate_limit",
                "message": "You've requested too many magic links. Please wait a few minutes and try again."
            }
        # Detect invalid email errors
        elif "invalid" in error_msg and "email" in error_msg:
            return {
                "success": False,
                "error": "invalid_email",
                "message": "The email address is invalid. Please check and try again."
            }
        # Generic error
        else:
            return {
                "success": False,
                "error": "unknown",
                "message": "Unable to send magic link. Please try again later."
            }


def verify_session(access_token: str, refresh_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Verify a user session token and return user data.

    This establishes the session in Supabase using the provided tokens,
    then retrieves the authenticated user's data.

    Args:
        access_token: JWT access token from Supabase Auth
        refresh_token: Optional refresh token (recommended for magic links)

    Returns:
        User dict with id, email, etc. or None if invalid
    """
    if not _supabase_client:
        return None

    try:
        # Set the session with the provided tokens
        # This is required before getting the user
        session_response = _supabase_client.auth.set_session(
            access_token=access_token,
            refresh_token=refresh_token or ""
        )

        # Now get the authenticated user
        if session_response and session_response.user:
            return session_response.user.model_dump()
        return None

    except Exception as e:
        _safe_log_error(f"Error verifying session: {e}")
        return None


def sign_out(access_token: str) -> bool:
    """
    Sign out a user session.

    Args:
        access_token: JWT access token (used to set session before signing out)

    Returns:
        True if successful, False otherwise
    """
    if not _supabase_client:
        return False

    try:
        # Set the session first if we have an access token
        if access_token:
            _supabase_client.auth.set_session(access_token, "")

        # Sign out (no parameters needed - signs out current session)
        _supabase_client.auth.sign_out()
        return True
    except Exception as e:
        _safe_log_error(f"Error signing out: {e}")
        return False


# ============================================================================
# Profile Helpers
# ============================================================================

def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user profile by user ID.

    Args:
        user_id: Supabase user UUID

    Returns:
        Profile dict with plan, trial_ends_at, etc. or None if not found
    """
    if not _supabase_client:
        return None

    try:
        # Use maybeSingle() instead of single() to handle 0 rows gracefully
        response = _supabase_client.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
        return response.data  # Returns None if no rows found
    except Exception as e:
        _safe_log_error(f"Error fetching user profile: {e}")
        return None


def create_user_profile(user_id: str, email: str) -> Optional[Dict[str, Any]]:
    """
    Create a new user profile with 14-day trial.
    Note: This should be handled by the database trigger, but included as fallback.

    Uses admin client to bypass RLS (Row-Level Security) policies.

    Args:
        user_id: Supabase user UUID
        email: User's email address

    Returns:
        Created profile dict or None
    """
    # Use admin client to bypass RLS when creating profiles
    admin_client = get_admin_client()

    if not admin_client:
        current_app.logger.error("Admin client not available. Cannot create profile.")
        return None

    try:
        trial_ends_at = (datetime.utcnow() + timedelta(days=14)).isoformat()

        response = admin_client.table("profiles").insert({
            "id": user_id,
            "email": email,
            "plan": "free",
            "trial_ends_at": trial_ends_at,
            "onboarding_completed": False
        }).execute()

        return response.data[0] if response.data else None
    except Exception as e:
        error_msg = str(e)

        # If profile already exists (duplicate key), fetch and return it instead
        if "duplicate key" in error_msg or "23505" in error_msg:
            _safe_log_info(f"Profile already exists for user {user_id}, fetching existing profile")
            return get_user_profile(user_id)

        _safe_log_error(f"Error creating user profile: {e}")
        return None


def update_user_city(user_id: str, city: str) -> tuple[bool, Optional[str]]:
    """
    Update user's city/location in their profile.

    Security:
    - Input sanitization (XSS prevention)
    - Length validation (max 200 characters)
    - Authorization check (user can only update own profile)

    Args:
        user_id: User's UUID
        city: City name or ZIP code (e.g., "Austin, TX" or "78701")

    Returns:
        tuple[bool, Optional[str]]: (success, error_message)
    """
    if not _supabase_client:
        return False, "Database not configured"

    try:
        # Input validation and sanitization
        if city:
            # Strip whitespace
            city = city.strip()

            # Max length check (prevent abuse)
            if len(city) > 200:
                return False, "City name too long (max 200 characters)"

            # Basic sanitization: remove dangerous characters
            # Allow letters, numbers, spaces, commas, hyphens, periods
            import re
            if not re.match(r'^[a-zA-Z0-9\s,.\-]+$', city):
                return False, "Invalid characters in city name"
        else:
            city = None  # Allow clearing the city

        # Update profile (RLS ensures user can only update their own)
        response = _supabase_client.table("profiles").update({
            "city": city
        }).eq("id", user_id).execute()

        if response.data:
            return True, None
        return False, "Failed to update city"

    except Exception as e:
        _safe_log_error(f"Error updating user city: {e}")
        return False, f"Error updating city: {str(e)}"


def update_user_theme(user_id: str, theme: str) -> tuple[bool, Optional[str]]:
    """
    Update user's theme preference (light, dark, or auto).

    Security:
    - Input validation (only allows 'light', 'dark', 'auto')
    - Authorization check (user can only update own preference)

    Args:
        user_id: User's UUID
        theme: Theme preference ('light', 'dark', or 'auto')

    Returns:
        (success, error_message)
    """
    if not _supabase_client:
        return False, "Database not configured"

    try:
        # Validate theme value
        theme = theme.strip().lower() if theme else 'auto'

        if theme not in ['light', 'dark', 'auto']:
            return False, "Invalid theme option. Must be 'light', 'dark', or 'auto'"

        # Update user's theme preference
        response = _supabase_client.table("profiles").update({
            "theme_preference": theme
        }).eq("id", user_id).execute()

        if response.data:
            return True, None
        return False, "Failed to update theme preference"

    except Exception as e:
        _safe_log_error(f"Error updating user theme: {e}")
        return False, f"Error updating theme: {str(e)}"


def is_premium(user_id: str) -> bool:
    """
    Check if user has premium plan.

    Args:
        user_id: Supabase user UUID

    Returns:
        True if premium, False otherwise
    """
    profile = get_user_profile(user_id)
    if not profile:
        return False

    return profile.get("plan") == "premium"


def is_in_trial(user_id: str) -> bool:
    """
    Check if user is currently in premium trial period.

    Args:
        user_id: Supabase user UUID

    Returns:
        True if in trial, False otherwise
    """
    profile = get_user_profile(user_id)
    if not profile:
        return False

    trial_ends_at = profile.get("trial_ends_at")
    if not trial_ends_at:
        return False

    try:
        trial_end = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
        return datetime.utcnow() < trial_end.replace(tzinfo=None)
    except Exception as e:
        _safe_log_error(f"Error parsing trial date: {e}")
        return False


def trial_days_remaining(user_id: str) -> int:
    """
    Get number of days remaining in trial.

    Args:
        user_id: Supabase user UUID

    Returns:
        Days remaining (0 if trial expired or not in trial)
    """
    profile = get_user_profile(user_id)
    if not profile:
        return 0

    trial_ends_at = profile.get("trial_ends_at")
    if not trial_ends_at:
        return 0

    try:
        trial_end = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
        delta = trial_end.replace(tzinfo=None) - datetime.utcnow()
        return max(0, delta.days)
    except Exception as e:
        _safe_log_error(f"Error calculating trial days: {e}")
        return 0


def has_premium_access(user_id: str) -> bool:
    """
    Check if user has premium access (either paid premium or in trial).

    Args:
        user_id: Supabase user UUID

    Returns:
        True if has premium access, False otherwise
    """
    return is_premium(user_id) or is_in_trial(user_id)


# ============================================================================
# Plant Helpers
# ============================================================================

def get_plant_count(user_id: str) -> int:
    """
    Get number of plants user has.

    Args:
        user_id: Supabase user UUID

    Returns:
        Plant count (0 if error)
    """
    if not _supabase_client:
        return 0

    try:
        response = _supabase_client.table("plants").select("id", count="exact").eq("user_id", user_id).execute()
        return response.count or 0
    except Exception as e:
        _safe_log_error(f"Error getting plant count: {e}")
        return 0


def can_add_plant(user_id: str) -> tuple[bool, str]:
    """
    Check if user can add another plant (respects 10-plant limit for Starter).

    Args:
        user_id: Supabase user UUID

    Returns:
        Tuple of (can_add: bool, message: str)
    """
    # Premium users (paid or trial) can add unlimited plants
    if has_premium_access(user_id):
        return True, "Premium access - unlimited plants"

    # Starter users limited to configured plant limit
    plant_limit = current_app.config['FREE_TIER_PLANT_LIMIT']
    current_count = get_plant_count(user_id)
    if current_count >= plant_limit:
        return False, f"You've reached your {plant_limit}-plant limit. Upgrade to Premium for unlimited plants."

    if current_count == plant_limit - 1:
        return True, f"You can add 1 more plant"

    return True, f"You can add {plant_limit - current_count} more plants"


def _get_cache_key(user_id: str, limit: int, offset: int, fields: str) -> str:
    """Generate cache key for plant query."""
    return f"plants:{user_id}:{limit}:{offset}:{fields}"


def _get_cached_plants(cache_key: str) -> list[dict] | None:
    """
    Get plants from cache if valid.

    Returns:
        Cached plant list if valid, None if cache miss or expired
    """
    if cache_key not in _PLANT_CACHE:
        return None

    cached_data, cached_at = _PLANT_CACHE[cache_key]
    age_seconds = (datetime.now() - cached_at).total_seconds()

    if age_seconds > _CACHE_TTL_SECONDS:
        # Cache expired, remove it
        del _PLANT_CACHE[cache_key]
        return None

    return cached_data


def _cache_plants(cache_key: str, plants: list[dict]) -> None:
    """Store plants in cache with current timestamp."""
    _PLANT_CACHE[cache_key] = (plants, datetime.now())


def invalidate_plant_cache(user_id: str) -> None:
    """
    Invalidate all cached plant queries for a user.

    Call this when plants are added, updated, or deleted.
    """
    # Remove all cache entries for this user
    keys_to_remove = [key for key in _PLANT_CACHE.keys() if key.startswith(f"plants:{user_id}:")]
    for key in keys_to_remove:
        del _PLANT_CACHE[key]


def get_user_plants(user_id: str, limit: int = 100, offset: int = 0, fields: str = "*", use_cache: bool = True) -> list[dict]:
    """
    Get all plants for a user with pagination.

    Args:
        user_id: Supabase user UUID
        limit: Maximum number of plants to return
        offset: Number of plants to skip (for pagination)
        fields: Comma-separated list of fields to select (default: "*" for all)
                For optimal performance, specify only needed fields.
                Example: "id,name,nickname,photo_url_thumb"
        use_cache: Whether to use in-memory cache (default: True)
                   Set to False when you need fresh data immediately after updates

    Returns:
        List of plant dictionaries, empty list if error
    """
    if not _supabase_client:
        return []

    # Check cache first (if enabled)
    if use_cache:
        cache_key = _get_cache_key(user_id, limit, offset, fields)
        cached_plants = _get_cached_plants(cache_key)
        if cached_plants is not None:
            return cached_plants

    try:
        response = (_supabase_client
                   .table("plants")
                   .select(fields)
                   .eq("user_id", user_id)
                   .order("created_at", desc=True)
                   .limit(limit)
                   .offset(offset)
                   .execute())
        plants = response.data or []

        # Cache the results (if caching enabled)
        if use_cache:
            cache_key = _get_cache_key(user_id, limit, offset, fields)
            _cache_plants(cache_key, plants)

        return plants
    except Exception as e:
        _safe_log_error(f"Error getting user plants: {e}")
        return []


def get_plant_by_id(plant_id: str, user_id: str) -> dict | None:
    """
    Get a single plant by ID, verifying ownership.

    Args:
        plant_id: Plant UUID
        user_id: User UUID (for ownership verification)

    Returns:
        Plant dictionary if found and owned by user, None otherwise
    """
    if not _supabase_client:
        return None

    try:
        response = (_supabase_client
                   .table("plants")
                   .select("*")
                   .eq("id", plant_id)
                   .eq("user_id", user_id)
                   .single()
                   .execute())
        return response.data
    except Exception as e:
        _safe_log_error(f"Error getting plant {plant_id}: {e}")
        return None


def create_plant(user_id: str, plant_data: dict) -> dict | None:
    """
    Create a new plant for the user.

    Args:
        user_id: User UUID
        plant_data: Dictionary with plant fields (name, species, nickname, location, light, notes, photo_url)

    Returns:
        Created plant dictionary, or None if error
    """
    if not _supabase_client:
        return None

    try:
        # Prepare plant data with user_id
        data = {
            "user_id": user_id,
            "name": plant_data.get("name", "").strip(),
            "species": plant_data.get("species", "").strip() or None,
            "nickname": plant_data.get("nickname", "").strip() or None,
            "location": plant_data.get("location", "").strip() or None,
            "light": plant_data.get("light", "").strip() or None,
            "notes": plant_data.get("notes", "").strip() or None,
            "photo_url": plant_data.get("photo_url") or None,
        }

        response = _supabase_client.table("plants").insert(data).execute()

        if response.data and len(response.data) > 0:
            # Invalidate cache so fresh data is fetched
            invalidate_plant_cache(user_id)
            return response.data[0]
        return None
    except Exception as e:
        _safe_log_error(f"Error creating plant: {e}")
        return None


def update_plant(plant_id: str, user_id: str, plant_data: dict) -> dict | None:
    """
    Update an existing plant (with ownership verification).

    Args:
        plant_id: Plant UUID
        user_id: User UUID (for ownership verification)
        plant_data: Dictionary with fields to update

    Returns:
        Updated plant dictionary, or None if error
    """
    if not _supabase_client:
        return None

    try:
        # Prepare update data (only include provided fields)
        data = {}
        if "name" in plant_data:
            data["name"] = plant_data["name"].strip()
        if "species" in plant_data:
            data["species"] = plant_data["species"].strip() or None
        if "nickname" in plant_data:
            data["nickname"] = plant_data["nickname"].strip() or None
        if "location" in plant_data:
            data["location"] = plant_data["location"].strip() or None
        if "light" in plant_data:
            data["light"] = plant_data["light"].strip() or None
        if "notes" in plant_data:
            data["notes"] = plant_data["notes"].strip() or None
        if "photo_url" in plant_data:
            data["photo_url"] = plant_data["photo_url"] or None

        response = (_supabase_client
                   .table("plants")
                   .update(data)
                   .eq("id", plant_id)
                   .eq("user_id", user_id)  # Ownership check
                   .execute())

        if response.data and len(response.data) > 0:
            # Invalidate cache so fresh data is fetched
            invalidate_plant_cache(user_id)
            return response.data[0]
        return None
    except Exception as e:
        _safe_log_error(f"Error updating plant {plant_id}: {e}")
        return None


def delete_plant(plant_id: str, user_id: str) -> bool:
    """
    Delete a plant (with ownership verification).

    Args:
        plant_id: Plant UUID
        user_id: User UUID (for ownership verification)

    Returns:
        True if deleted successfully, False otherwise
    """
    if not _supabase_client:
        return False

    try:
        response = (_supabase_client
                   .table("plants")
                   .delete()
                   .eq("id", plant_id)
                   .eq("user_id", user_id)  # Ownership check
                   .execute())
        # Invalidate cache so fresh data is fetched
        invalidate_plant_cache(user_id)
        return True
    except Exception as e:
        _safe_log_error(f"Error deleting plant {plant_id}: {e}")
        return False


def create_image_versions(file_bytes: bytes) -> dict[str, bytes] | None:
    """
    Create multiple versions of an image for different display contexts.

    Args:
        file_bytes: Original image file bytes

    Returns:
        Dictionary with 3 versions:
        - 'original': Full resolution (preserved as-is)
        - 'display': Optimized for grid/detail views (max 900px width, 80% quality)
        - 'thumbnail': Small version for buttons (128x128, 85% quality)
        Returns None if image processing fails
    """
    try:
        from PIL import Image
        from io import BytesIO

        # Open original image
        img = Image.open(BytesIO(file_bytes))

        # Convert RGBA/LA/P to RGB (JPEG doesn't support transparency)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            # Paste image with alpha channel as mask if RGBA
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background

        versions = {}

        # Original - keep as-is for archival
        versions['original'] = file_bytes

        # Display version - optimize for web (max 900px width)
        display_img = img.copy()
        if display_img.width > 900 or display_img.height > 900:
            display_img.thumbnail((900, 900), Image.Resampling.LANCZOS)

        display_output = BytesIO()
        display_img.save(display_output, format='JPEG', quality=80, optimize=True)
        versions['display'] = display_output.getvalue()

        # Thumbnail - 128x128 for retina displays (shown at 64x64)
        thumb_img = img.copy()
        thumb_img.thumbnail((128, 128), Image.Resampling.LANCZOS)

        thumb_output = BytesIO()
        thumb_img.save(thumb_output, format='JPEG', quality=85, optimize=True)
        versions['thumbnail'] = thumb_output.getvalue()

        return versions

    except Exception as e:
        _safe_log_error(f"Error creating image versions: {e}")
        return None


def upload_plant_photo_versions(file_bytes: bytes, user_id: str, filename: str) -> dict[str, str] | None:
    """
    Upload plant photo with multiple optimized versions (original, display, thumbnail).

    Args:
        file_bytes: Original image file bytes
        user_id: User UUID (for organizing files)
        filename: Original filename (used for extension detection)

    Returns:
        Dictionary with public URLs for each version:
        - 'original': Full resolution URL
        - 'display': Optimized version URL (max 900px)
        - 'thumbnail': Small thumbnail URL (128x128)
        Returns None if upload fails
    """
    if not _supabase_client:
        return None

    try:
        import uuid
        from pathlib import Path

        # Generate unique base filename (without extension)
        base_uuid = str(uuid.uuid4())

        # Create optimized versions
        versions = create_image_versions(file_bytes)
        if not versions:
            _safe_log_error("Failed to create image versions")
            return None

        # Upload all versions in parallel for 3× faster uploads
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def upload_single_version(version_name: str, version_bytes: bytes) -> tuple[str, str]:
            """Upload a single version and return (version_name, public_url)."""
            version_filename = f"{user_id}/{base_uuid}-{version_name}.jpg"

            # Upload to plant-photos bucket
            _supabase_client.storage.from_("plant-photos").upload(
                version_filename,
                version_bytes,
                file_options={"content-type": "image/jpeg"}
            )

            # Get public URL
            public_url = _supabase_client.storage.from_("plant-photos").get_public_url(version_filename)
            return (version_name, public_url)

        # Upload all 3 versions concurrently
        urls = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all upload tasks
            future_to_version = {
                executor.submit(upload_single_version, version_name, version_bytes): version_name
                for version_name, version_bytes in versions.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_version):
                version_name, public_url = future.result()
                urls[version_name] = public_url

        return urls

    except Exception as e:
        _safe_log_error(f"Error uploading plant photo versions: {e}")
        return None


def delete_plant_photo(photo_url: str) -> bool:
    """
    Delete a plant photo from Supabase Storage.

    Args:
        photo_url: Full public URL of the photo

    Returns:
        True if deleted successfully, False otherwise
    """
    if not _supabase_client or not photo_url:
        return False

    try:
        # Extract file path from URL
        # URL format: https://{project}.supabase.co/storage/v1/object/public/plant-photos/{path}
        if "/plant-photos/" in photo_url:
            file_path = photo_url.split("/plant-photos/")[1]
            _supabase_client.storage.from_("plant-photos").remove([file_path])
            return True
        return False
    except Exception as e:
        _safe_log_error(f"Error deleting plant photo: {e}")
        return False


# ============================================================================
# Onboarding Helpers
# ============================================================================

def is_onboarding_completed(user_id: str) -> bool:
    """
    Check if user has completed onboarding wizard.

    Args:
        user_id: Supabase user UUID

    Returns:
        True if completed, False otherwise
    """
    profile = get_user_profile(user_id)
    if not profile:
        return False

    return profile.get("onboarding_completed", False)


def mark_onboarding_complete(user_id: str) -> bool:
    """
    Mark user's onboarding as completed.

    Args:
        user_id: Supabase user UUID

    Returns:
        True if successful, False otherwise
    """
    if not _supabase_client:
        return False

    try:
        _supabase_client.table("profiles").update({
            "onboarding_completed": True
        }).eq("id", user_id).execute()

        return True
    except Exception as e:
        _safe_log_error(f"Error marking onboarding complete: {e}")
        return False
