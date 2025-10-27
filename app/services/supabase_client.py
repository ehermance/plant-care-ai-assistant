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
from flask import current_app
from supabase import create_client, Client


# Global client instances (initialized once per app)
_supabase_client: Optional[Client] = None  # User client (anon key)
_supabase_admin: Optional[Client] = None   # Admin client (service role key)


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
        current_app.logger.error(f"Error sending magic link: {e}")
        return {"success": False, "error": str(e)}


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
        current_app.logger.error(f"Error verifying session: {e}")
        return None


def sign_out(access_token: str) -> bool:
    """
    Sign out a user session.

    Args:
        access_token: JWT access token

    Returns:
        True if successful, False otherwise
    """
    if not _supabase_client:
        return False

    try:
        _supabase_client.auth.sign_out(access_token)
        return True
    except Exception as e:
        current_app.logger.error(f"Error signing out: {e}")
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
        current_app.logger.error(f"Error fetching user profile: {e}")
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
            current_app.logger.info(f"Profile already exists for user {user_id}, fetching existing profile")
            return get_user_profile(user_id)

        current_app.logger.error(f"Error creating user profile: {e}")
        return None


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
        current_app.logger.error(f"Error parsing trial date: {e}")
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
        current_app.logger.error(f"Error calculating trial days: {e}")
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
        current_app.logger.error(f"Error getting plant count: {e}")
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

    # Starter users limited to 10 plants
    current_count = get_plant_count(user_id)
    if current_count >= 10:
        return False, f"You've reached your 10-plant limit. Upgrade to Premium for unlimited plants."

    return True, f"You can add {10 - current_count} more plants"


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
        current_app.logger.error(f"Error marking onboarding complete: {e}")
        return False
