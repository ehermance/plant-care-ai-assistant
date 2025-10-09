"""
Defines JSON endpoints used by the front end. Currently exposes /presets,
which returns regional plant presets using geolocation or city as hints.
"""

from flask import Blueprint, request, jsonify
from ..utils.presets import infer_region_from_latlon, infer_region_from_city, region_presets


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