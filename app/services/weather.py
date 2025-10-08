"""
Weather lookups via OpenWeather.

Provides:
- get_weather_for_city(city_or_zip): current conditions for a city OR US ZIP.
- get_forecast_for_city(city_or_zip): aggregated 5-day forecast (daily highs/lows).

Inputs:
- City forms like "Austin, TX", "Paris, FR", or just "Austin".
- US ZIP like "73301" or "73301-1234" (we use the first 5 digits).

Strategy:
- If looks like a US ZIP, query with zip= first (zip=73301,US) for accuracy.
- Otherwise, query with q=, preferring a lightly normalized form for US cities (e.g., "Austin, TX, US").
- On 404, gracefully fall back to a secondary query style.
- On any error, return None so UI remains responsive.

All network calls use short timeouts; errors never bubble to views.
"""

from __future__ import annotations
import os
from typing import Optional, Dict, List
import re
import requests
from flask import current_app, has_app_context
from collections import defaultdict
from datetime import datetime

# "City, ST" (two-letter region) → append ", US" to improve hit rate for ambiguous US names.
_US_STATE_LIKE = re.compile(r"^\s*([^,]+),\s*([A-Za-z]{2})\s*$")

# US ZIP: 12345 or 12345-6789 (we use only the first 5 for OpenWeather).
_US_ZIP = re.compile(r"^\s*(\d{5})(?:-\d{4})?\s*$")


def _normalize_city_query(city: str) -> str:
    """Normalize common US inputs for OpenWeather: 'Austin, TX' → 'Austin, TX, US'."""
    m = _US_STATE_LIKE.match(city)
    if m:
        city_part = m.group(1).strip()
        st_part = m.group(2).upper()
        return f"{city_part}, {st_part}, US"
    return city.strip()


def _get_api_key() -> str | None:
    """
    Read the OpenWeather API key from environment first; if an app context is active,
    also check current_app.config. Keeps tests/imports safe with no app ctx.
    """
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key and has_app_context():
        key = current_app.config.get("OPENWEATHER_API_KEY")
    return key or None


# --------------------------
# Current weather (metric)
# --------------------------

def get_weather_for_city(city: str | None) -> Optional[Dict]:
    """
    Current weather. Accepts city (e.g., "Austin, TX" or "Paris, FR") OR a US ZIP ("73301").
    Returns a dict with temps in °C/°F and wind in m/s & mph, or None on error.
    """
    if not city:
        return None

    key = _get_api_key()
    if not key:
        return None

    base_url = "https://api.openweathermap.org/data/2.5/weather"
    session = requests.Session()  # small reuse for the two attempts

    def _call_q(q: str) -> requests.Response:
        # Use metric here; we’ll compute °F for display.
        return session.get(base_url, params={"q": q, "appid": key, "units": "metric"}, timeout=6)

    def _call_zip(zip5: str) -> requests.Response:
        return session.get(base_url, params={"zip": f"{zip5},US", "appid": key, "units": "metric"}, timeout=6)

    try:
        # Branch 1: US ZIP detected → try zip= first, then fall back to q=
        mzip = _US_ZIP.match(city)
        if mzip:
            zip5 = mzip.group(1)
            r = _call_zip(zip5)
            if r.status_code == 404:
                r = _call_q(_normalize_city_query(city))
                if r.status_code == 404:
                    r = _call_q(city)
            r.raise_for_status()
        else:
            # Branch 2: Not a ZIP → try normalized q= first, then raw q=
            q1 = _normalize_city_query(city)
            r = _call_q(q1)
            if r.status_code == 404:
                r = _call_q(city)
            r.raise_for_status()

        data = r.json()
        temp_c = data.get("main", {}).get("temp")
        wind_mps = data.get("wind", {}).get("speed")

        return {
            "city": data.get("name", city),
            "temp_c": temp_c,  # kept for AI/weather tips and backend logic
            "temp_f": round((temp_c * 9 / 5) + 32, 1) if isinstance(temp_c, (int, float)) else None,
            "humidity": data.get("main", {}).get("humidity"),
            "conditions": (data.get("weather") or [{}])[0].get("description"),
            "wind_mps": wind_mps,
            "wind_mph": round(wind_mps * 2.23694, 1) if isinstance(wind_mps, (int, float)) else None,
        }

    except Exception:
        # Silently return None on any error; the UI should remain responsive.
        return None


# --------------------------
# 5-day forecast (aggregate)
# --------------------------

def _weekday_name(dt_txt: str) -> str:
    """Return short weekday name (e.g., 'Mon') from an API dt_txt string (UTC)."""
    try:
        dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%a")
    except Exception:
        return ""


def _date_key(dt_txt: str) -> str:
    """Extract YYYY-MM-DD from dt_txt."""
    try:
        return dt_txt.split(" ")[0]
    except Exception:
        return ""


def _mode_text(texts: List[str]) -> str:
    """Pick the most common non-empty text from a list; fallback to first non-empty."""
    counts = defaultdict(int)
    for t in texts:
        if t:
            counts[t] += 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: kv[1])[0]


def get_forecast_for_city(city: str | None) -> Optional[List[Dict]]:
    """
    5-day / 3-hour forecast aggregated into daily entries.

    Returns a list of up to 5 dicts like:
      {
        "day": "Thu",
        "date": "2025-09-26",
        "temp_max_f": 98,
        "temp_min_f": 76,
        "temp_max_c": 36.7,
        "temp_min_c": 24.4,
        "humidity": 52,              # average of the day
        "wind_mph": 8.1,             # average of the day
        "conditions": "few clouds"   # most common description
      }

    On any error (no key, bad response), returns None.
    """
    if not city:
        return None

    key = _get_api_key()
    if not key:
        return None

    base_url = "https://api.openweathermap.org/data/2.5/forecast"
    session = requests.Session()

    def _call_q(q: str) -> requests.Response:
        # Use metric to be consistent; we’ll compute °F after aggregation.
        return session.get(base_url, params={"q": q, "appid": key, "units": "metric"}, timeout=7)

    def _call_zip(zip5: str) -> requests.Response:
        return session.get(base_url, params={"zip": f"{zip5},US", "appid": key, "units": "metric"}, timeout=7)

    try:
        # ZIP-first if it looks like a US ZIP
        mzip = _US_ZIP.match(city)
        if mzip:
            zip5 = mzip.group(1)
            r = _call_zip(zip5)
            if r.status_code == 404:
                r = _call_q(_normalize_city_query(city))
                if r.status_code == 404:
                    r = _call_q(city)
            r.raise_for_status()
        else:
            q1 = _normalize_city_query(city)
            r = _call_q(q1)
            if r.status_code == 404:
                r = _call_q(city)
            r.raise_for_status()

        data = r.json()
        items = data.get("list") or []
        if not items:
            return None

        # Group 3-hour entries by date
        groups: Dict[str, List[dict]] = defaultdict(list)
        for it in items:
            dt_txt = it.get("dt_txt")
            if not dt_txt:
                continue
            groups[_date_key(dt_txt)].append(it)

        # Build daily aggregates
        daily = []
        for date_key, entries in sorted(groups.items()):
            highs_c, lows_c, hums, winds, descs = [], [], [], [], []
            for e in entries:
                main = e.get("main") or {}
                tmax_c = main.get("temp_max")
                tmin_c = main.get("temp_min")
                if isinstance(tmax_c, (int, float)): highs_c.append(tmax_c)
                if isinstance(tmin_c, (int, float)): lows_c.append(tmin_c)
                hum = main.get("humidity")
                if isinstance(hum, (int, float)): hums.append(hum)
                wind = (e.get("wind") or {}).get("speed")
                if isinstance(wind, (int, float)): winds.append(wind)
                wdesc = ((e.get("weather") or [{}])[0]).get("description")
                if wdesc: descs.append(wdesc)

            if not highs_c or not lows_c:
                continue

            max_c = max(highs_c)
            min_c = min(lows_c)
            avg_h = round(sum(hums)/len(hums)) if hums else None
            avg_w_mps = sum(winds)/len(winds) if winds else None

            # Find a representative entry's dt_txt (midday if possible)
            # Otherwise use the first entry for day name.
            rep_dt_txt = entries[len(entries)//2].get("dt_txt") or entries[0].get("dt_txt", "")
            daily.append({
                "day": _weekday_name(rep_dt_txt),
                "date": date_key,
                "temp_max_c": round(max_c, 1),
                "temp_min_c": round(min_c, 1),
                "temp_max_f": round((max_c * 9/5) + 32),
                "temp_min_f": round((min_c * 9/5) + 32),
                "humidity": avg_h,
                "wind_mph": round((avg_w_mps * 2.23694), 1) if isinstance(avg_w_mps, (int, float)) else None,
                "conditions": _mode_text(descs),
            })

        # Keep next 5 days (OpenWeather includes today/tomorrow depending on local time)
        # Sort is already chronological by date_key due to sorted(groups.items()).
        if not daily:
            return None
        return daily[:5]

    except Exception:
        return None
