"""
Defines JSON endpoints used by the front end.

Endpoints:
- /presets: Regional plant presets using geolocation or city
- /user/theme: Update user theme preferences
- /user/context: Get user context for AI (plants, reminders, activities)
- /user/plant/<id>/context: Get detailed context for specific plant
"""

from flask import Blueprint, request, jsonify
from ..utils.presets import infer_region_from_latlon, infer_region_from_city, region_presets
from ..utils.auth import require_auth, get_current_user_id
from ..utils.errors import sanitize_error, GENERIC_MESSAGES
from ..services import supabase_client, user_context
from ..extensions import limiter


api_bp = Blueprint("api", __name__)

@api_bp.route("/presets")
def presets_api():
    """
    Decide region via:
      - ?lat=..&lon=.. (preferred)
      - else ?city=..
      - else default 'temperate'
    Returns a stable JSON payload for the client UI.
    """
    try:
        lat = request.args.get("lat", type=float)
        lon = request.args.get("lon", type=float)
        city = request.args.get("city", type=str)

        if lat is not None and lon is not None:
            region = infer_region_from_latlon(lat, lon)
        elif city:
            region = infer_region_from_city(city)
        else:
            region = "temperate"

        return jsonify({"region": region, "items": region_presets(region)})
    except Exception:
        # Never surface internal errors; return a safe fallback.
        return jsonify({"region": "temperate", "items": region_presets("temperate")})


@api_bp.route("/user/theme", methods=["POST"])
@require_auth
def update_theme():
    """
    Updates user's theme preference (light, dark, or auto).

    Security:
    - Requires authentication
    - Input validation (only allows 'light', 'dark', 'auto')
    - User can only update their own preference

    Request body (JSON):
        {
            "theme": "light" | "dark" | "auto"
        }

    Returns:
        {
            "success": true/false,
            "error": "error message" (if applicable)
        }
    """
    try:
        # Get user ID from session
        user_id = get_current_user_id()

        # Parse JSON body
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid request body"}), 400

        theme = data.get("theme", "").strip().lower()

        # Validate theme value
        if theme not in ["light", "dark", "auto"]:
            return jsonify({
                "success": False,
                "error": "Invalid theme. Must be 'light', 'dark', or 'auto'"
            }), 400

        # Update theme in database
        success, error = supabase_client.update_user_theme(user_id, theme)

        if success:
            return jsonify({"success": True}), 200
        else:
            # Sanitize service layer error
            sanitized_msg = GENERIC_MESSAGES["database"]
            return jsonify({"success": False, "error": sanitized_msg}), 500

    except Exception as e:
        # Log the actual error for debugging, return sanitized message
        sanitized_msg = sanitize_error(e, "database", "Theme update failed")
        return jsonify({"success": False, "error": sanitized_msg}), 500


@api_bp.route("/user/context", methods=["GET"])
@require_auth
@limiter.limit("10 per minute")
def get_user_context():
    """
    Get consolidated user context for AI.

    Returns comprehensive context including:
    - User's plants (name, location, light)
    - Reminders (overdue, due today, upcoming week)
    - Recent care activities (last 7 days)
    - Summary statistics

    **Authentication required**

    Rate limit: 10 requests per minute

    Returns:
        200: JSON with user context
        401: Not authenticated
        429: Rate limit exceeded

    Example response:
        {
            "success": true,
            "context": {
                "plants": [...],
                "reminders": {...},
                "recent_activities": [...],
                "stats": {...}
            }
        }
    """
    user_id = get_current_user_id()

    try:
        context = user_context.get_user_context(user_id)
        return jsonify({
            "success": True,
            "context": context
        }), 200
    except Exception as e:
        sanitized_msg = sanitize_error(e, "database", "Failed to get user context")
        return jsonify({
            "success": False,
            "error": sanitized_msg
        }), 500


@api_bp.route("/user/plant/<plant_id>/context", methods=["GET"])
@require_auth
@limiter.limit("10 per minute")
def get_plant_context(plant_id: str):
    """
    Get detailed context for specific plant.

    Returns plant-specific context including:
    - Full plant details
    - Last 14 days of care activities
    - All active reminders for this plant
    - Plant-specific statistics

    **Authentication required**

    Rate limit: 10 requests per minute

    Args:
        plant_id: UUID of the plant

    Returns:
        200: JSON with plant context
        401: Not authenticated
        403: Access denied (not user's plant)
        404: Plant not found
        429: Rate limit exceeded

    Example response:
        {
            "success": true,
            "context": {
                "plant": {...},
                "activities": [...],
                "reminders": [...],
                "stats": {...}
            }
        }
    """
    user_id = get_current_user_id()

    try:
        context = user_context.get_plant_context(user_id, plant_id)

        # Check if plant was found
        if context.get("error"):
            return jsonify({
                "success": False,
                "error": context["error"]
            }), 404 if "not found" in context["error"].lower() else 403

        return jsonify({
            "success": True,
            "context": context
        }), 200
    except Exception as e:
        sanitized_msg = sanitize_error(e, "database", "Failed to get plant context")
        return jsonify({
            "success": False,
            "error": sanitized_msg
        }), 500