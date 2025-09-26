"""
Weather lookups via OpenWeather.

Fetches current conditions for a city and returns a normalized dict:
{ city, temp_c, humidity, conditions, wind_mps } or None on failure.
"""

from __future__ import annotations
import os
from typing import Optional, Dict
import re
import requests
from flask import current_app, has_app_context

# Matches "City, ST" (two-letter region) and appends ", US" to improve hit rate.
_US_STATE_LIKE = re.compile(r"^\s*([^,]+),\s*([A-Za-z]{2})\s*$")


def _normalize_city_query(city: str) -> str:
    """
    Normalizes common inputs for OpenWeather:
    - "Austin, TX"  -> "Austin, TX, US"
    - Leaves other formats untouched (e.g., "Toronto, CA", "Paris, FR", "Austin,US")
    """
    m = _US_STATE_LIKE.match(city)
    if m:
        city_part = m.group(1).strip()
        st_part = m.group(2).upper()
        return f"{city_part}, {st_part}, US"
    return city.strip()


def _get_api_key() -> str | None:
    """
    Reads the OpenWeather API key from environment first; if an app context is
    active, also checks current_app.config. Keeps tests/imports safe with no ctx.
    """
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key and has_app_context():
        key = current_app.config.get("OPENWEATHER_API_KEY")
    return key or None


def get_weather_for_city(city: str | None) -> Optional[Dict]:
    """
    Small, defensive wrapper around OpenWeather's current weather endpoint.
    Reads API key at call time so tests/env changes are picked up immediately.

    Strategy:
      1) Try normalized query (e.g., "Austin, TX, US")
      2) If 404, try the raw input
      3) If still failing, return None
    """
    if not city:
        return None

    key = _get_api_key()
    if not key:
        return None

    base_url = "https://api.openweathermap.org/data/2.5/weather"
    session = requests.Session()  # small reuse for the two attempts

    def _call(q: str):
        params = {"q": q, "appid": key, "units": "metric"}
        r = session.get(base_url, params=params, timeout=6)
        return r

    try:
        # Attempt 1: normalized (handles "City, ST" for US inputs)
        q1 = _normalize_city_query(city)
        r = _call(q1)
        if r.status_code == 404:
            # Attempt 2: raw as typed
            r = _call(city)

        r.raise_for_status()
        data = r.json()
        return {
            "city": data.get("name", city),
            "temp_c": data.get("main", {}).get("temp"),
            "humidity": data.get("main", {}).get("humidity"),
            "conditions": (data.get("weather") or [{}])[0].get("description"),
            "wind_mps": data.get("wind", {}).get("speed"),
        }
    except Exception:
        # Silently return None on any error; the UI should remain responsive.
        return None
