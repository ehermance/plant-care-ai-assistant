"""
Defines JSON endpoints used by the front end. Currently exposes /presets,
which returns regional plant presets using geolocation or city as hints.
Also exposes /user/theme for updating user theme preferences.
"""

from flask import Blueprint, request, jsonify
from ..utils.presets import infer_region_from_latlon, infer_region_from_city, region_presets
from ..utils.auth import require_auth, get_current_user_id
from ..services import supabase_client


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
            return jsonify({"success": False, "error": error}), 500

    except Exception as e:
        # Log error but don't expose internal details
        return jsonify({
            "success": False,
            "error": "An error occurred while updating theme preference"
        }), 500