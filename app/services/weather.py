"""
Encapsulates calls to OpenWeather for current conditions. Accepts flexible
inputs like “Austin, TX”, normalizes them for OpenWeather, and falls back
to the geocoding API when a name lookup fails. Returns a uniform dict or None.
"""

import os
import requests
from flask import current_app as app

def normalize_city_for_openweather(raw: str) -> str:
    """
    Accepts 'City', 'City, ST', 'City, ST, CC', 'City, CC' and returns a format
    OpenWeather understands. If a state is given with no country, assume US.
    """
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        city, second = parts[0], parts[1]
        if len(second) == 2 and second.isalpha():
            return f"{city},{second.upper()},US"
        return f"{city},{second.upper()}"
    city, state, country = parts[0], parts[1], parts[2]
    return f"{city},{state.upper()},{country.upper()}"

def _ok(resp) -> bool:
    """Return True if HTTP status is OK without raising."""
    try:
        resp.raise_for_status()
        return True
    except Exception:
        return False

def _normalize_weather(data: dict, fallback_city: str):
    """Shape OpenWeather payload into a compact dict for the UI."""
    return {
        "city": data.get("name", fallback_city),
        "temp_c": data.get("main", {}).get("temp"),
        "humidity": data.get("main", {}).get("humidity"),
        "conditions": (data.get("weather") or [{}])[0].get("description"),
        "wind_mps": data.get("wind", {}).get("speed"),
    }

def get_weather_for_city(city: str):
    """
    Resolve weather for a user-entered location:
      1) Normalize and query by name.
      2) If that fails, geocode to lat/lon and query by coordinates.
    Returns a dict or None on failure.
    """
    key = os.getenv("OPENWEATHER_API_KEY") or app.config.get("OPENWEATHER_API_KEY")
    if not city or not key:
        return None

    try:
        q = normalize_city_for_openweather(city)
        weather_url = "https://api.openweathermap.org/data/2.5/weather"

        # Try by name
        r = requests.get(weather_url, params={"q": q, "appid": key, "units": "metric"}, timeout=6)
        if _ok(r):
            return _normalize_weather(r.json(), fallback_city=city)

        # Fallback: geocode then query by coordinates
        geo_url = "https://api.openweathermap.org/geo/1.0/direct"
        gr = requests.get(geo_url, params={"q": q, "limit": 1, "appid": key}, timeout=6)
        if _ok(gr):
            arr = gr.json() or []
            if arr:
                lat = arr[0].get("lat")
                lon = arr[0].get("lon")
                name = arr[0].get("name") or city
                if lat is not None and lon is not None:
                    wr = requests.get(weather_url, params={"lat": lat, "lon": lon, "appid": key, "units": "metric"}, timeout=6)
                    if _ok(wr):
                        return _normalize_weather(wr.json(), fallback_city=name)
        return None
    except Exception:
        return None
