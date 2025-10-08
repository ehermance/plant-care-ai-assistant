"""
Weather lookups via OpenWeather.

Provides:
- get_weather_for_city(city_or_zip): current conditions for a city OR US ZIP.
- get_forecast_for_city(city_or_zip): aggregated 5-day forecast (daily highs/lows).

Adds friendly weather emojis for quick visual context (with screen-reader labels).
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
    """Retrieve OpenWeather API key safely (supports app or env context)."""
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key and has_app_context():
        key = current_app.config.get("OPENWEATHER_API_KEY")
    return key or None


# --------------------------
# Emoji helper
# --------------------------

def _emoji_for_conditions(desc: str | None) -> str:
    """Return a simple weather emoji for a given OpenWeather description."""
    if not desc:
        return "❓"
    d = desc.lower()
    if "thunder" in d:
        return "⛈️"
    if "rain" in d or "drizzle" in d:
        return "🌧️"
    if "snow" in d:
        return "❄️"
    if "mist" in d or "fog" in d or "haze" in d:
        return "🌫️"
    if "cloud" in d:
        return "☁️"
    if "clear" in d:
        return "☀️"
    if "wind" in d:
        return "💨"
    return "🌡️"


# --------------------------
# Current weather
# --------------------------

def get_weather_for_city(city: str | None) -> Optional[Dict]:
    """Fetch current weather; returns normalized dict with °C/°F and emoji."""
    if not city:
        return None

    key = _get_api_key()
    if not key:
        return None

    base_url = "https://api.openweathermap.org/data/2.5/weather"
    session = requests.Session()

    def _call_q(q: str):
        return session.get(base_url, params={"q": q, "appid": key, "units": "metric"}, timeout=6)

    def _call_zip(zip5: str):
        return session.get(base_url, params={"zip": f"{zip5},US", "appid": key, "units": "metric"}, timeout=6)

    try:
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
        desc = (data.get("weather") or [{}])[0].get("description", "")
        temp_c = data.get("main", {}).get("temp")
        wind_mps = data.get("wind", {}).get("speed")

        return {
            "city": data.get("name", city),
            "temp_c": temp_c,
            "temp_f": round((temp_c * 9 / 5) + 32, 1) if isinstance(temp_c, (int, float)) else None,
            "humidity": data.get("main", {}).get("humidity"),
            "conditions": desc,
            "emoji": _emoji_for_conditions(desc),
            "wind_mps": wind_mps,
            "wind_mph": round(wind_mps * 2.23694, 1) if isinstance(wind_mps, (int, float)) else None,
        }

    except Exception:
        return None


# --------------------------
# 5-day forecast (aggregate)
# --------------------------

def _weekday_name(dt_txt: str) -> str:
    try:
        dt = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%a")
    except Exception:
        return ""


def _date_key(dt_txt: str) -> str:
    return dt_txt.split(" ")[0] if " " in dt_txt else dt_txt


def _mode_text(texts: List[str]) -> str:
    counts = defaultdict(int)
    for t in texts:
        if t:
            counts[t] += 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: kv[1])[0]


def get_forecast_for_city(city: str | None) -> Optional[List[Dict]]:
    """
    Aggregate 5-day forecast into daily entries with emoji and highs/lows.
    """
    if not city:
        return None

    key = _get_api_key()
    if not key:
        return None

    base_url = "https://api.openweathermap.org/data/2.5/forecast"
    session = requests.Session()

    def _call_q(q: str):
        return session.get(base_url, params={"q": q, "appid": key, "units": "metric"}, timeout=7)

    def _call_zip(zip5: str):
        return session.get(base_url, params={"zip": f"{zip5},US", "appid": key, "units": "metric"}, timeout=7)

    try:
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

        groups: Dict[str, List[dict]] = defaultdict(list)
        for it in items:
            dt_txt = it.get("dt_txt")
            if not dt_txt:
                continue
            groups[_date_key(dt_txt)].append(it)

        daily = []
        for date_key, entries in sorted(groups.items()):
            highs_c, lows_c, hums, winds, descs = [], [], [], [], []
            for e in entries:
                main = e.get("main") or {}
                if isinstance(main.get("temp_max"), (int, float)): highs_c.append(main["temp_max"])
                if isinstance(main.get("temp_min"), (int, float)): lows_c.append(main["temp_min"])
                if isinstance(main.get("humidity"), (int, float)): hums.append(main["humidity"])
                w = (e.get("wind") or {}).get("speed")
                if isinstance(w, (int, float)): winds.append(w)
                wdesc = ((e.get("weather") or [{}])[0]).get("description")
                if wdesc: descs.append(wdesc)

            if not highs_c or not lows_c:
                continue

            max_c, min_c = max(highs_c), min(lows_c)
            avg_h = round(sum(hums) / len(hums)) if hums else None
            avg_w_mps = sum(winds) / len(winds) if winds else None
            rep_desc = _mode_text(descs)

            rep_dt_txt = entries[len(entries)//2].get("dt_txt") or entries[0].get("dt_txt", "")
            daily.append({
                "day": _weekday_name(rep_dt_txt),
                "date": date_key,
                "temp_max_c": round(max_c, 1),
                "temp_min_c": round(min_c, 1),
                "temp_max_f": round((max_c * 9/5) + 32),
                "temp_min_f": round((min_c * 9/5) + 32),
                "humidity": avg_h,
                "wind_mph": round(avg_w_mps * 2.23694, 1) if isinstance(avg_w_mps, (int, float)) else None,
                "conditions": rep_desc,
                "emoji": _emoji_for_conditions(rep_desc),
            })

        return daily[:5] if daily else None

    except Exception:
        return None
