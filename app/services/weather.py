"""
Weather service helpers (OpenWeather).

Functions:
- get_weather_for_city(city): current weather for city OR US ZIP.
- get_forecast_for_city(city): 5–6 day daily forecast from the 3-hourly API.
- get_hourly_for_city(city): hourly chips for the rest of today; if none remain,
  return the first few hours of tomorrow (so the UI never feels empty).
- get_weather_alerts_for_city(current, forecast): simple derived alerts for heat/cold/wind.

Notes:
- Uses metric units from the API and converts to °F on the server. The UI toggles
  presentation only; no API re-requests needed.
- All functions are best-effort and return None/[] on failure to keep the UI responsive.
- Small emoji mapper improves glanceability while remaining neutral and accessible.
"""

from __future__ import annotations
import os
from typing import Optional, Dict, List
import re
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from flask import current_app, has_app_context

_US_STATE_LIKE = re.compile(r"^\s*([^,]+),\s*([A-Za-z]{2})\s*$")
_US_ZIP = re.compile(r"^\s*(\d{5})(?:-\d{4})?\s*$")

def _normalize_city_query(city: str) -> str:
    m = _US_STATE_LIKE.match(city)
    if m:
        return f"{m.group(1).strip()}, {m.group(2).upper()}, US"
    return city.strip()

def _get_api_key() -> str | None:
    key = os.getenv("OPENWEATHER_API_KEY")
    if not key and has_app_context():
        key = current_app.config.get("OPENWEATHER_API_KEY")
    return key or None

def _emoji_for(weather_id: int, main: str, descr: str) -> str:
    if 200 <= weather_id < 300: return "⛈️"
    if 300 <= weather_id < 400: return "🌦️"
    if 500 <= weather_id < 600: return "🌧️"
    if 600 <= weather_id < 700: return "❄️"
    if 700 <= weather_id < 800: return "🌫️"
    if weather_id == 800: return "☀️"
    if 801 <= weather_id <= 804: return "⛅" if weather_id in (801, 802) else "☁️"
    d = (descr or "").lower()
    if "rain" in d: return "🌧️"
    if "snow" in d: return "❄️"
    if "cloud" in d: return "☁️"
    if "clear" in d: return "☀️"
    return "🌤️"

def get_weather_for_city(city: str | None) -> Optional[Dict]:
    if not city:
        return None
    key = _get_api_key()
    if not key:
        return None

    base_url = "https://api.openweathermap.org/data/2.5/weather"
    session = requests.Session()

    def _call_q(q: str) -> requests.Response:
        return session.get(base_url, params={"q": q, "appid": key, "units": "metric"}, timeout=6)
    def _call_zip(zip5: str) -> requests.Response:
        return session.get(base_url, params={"zip": f"{zip5},US", "appid": key, "units": "metric"}, timeout=6)

    try:
        mzip = _US_ZIP.match(city)
        if mzip:
            r = _call_zip(mzip.group(1))
            if r.status_code == 404:
                r = _call_q(_normalize_city_query(city))
                if r.status_code == 404:
                    r = _call_q(city)
            r.raise_for_status()
        else:
            r = _call_q(_normalize_city_query(city))
            if r.status_code == 404:
                r = _call_q(city)
            r.raise_for_status()

        data = r.json()
        temp_c = data.get("main", {}).get("temp")
        wind_mps = data.get("wind", {}).get("speed")
        wid = (data.get("weather") or [{}])[0].get("id", 800)
        wmain = (data.get("weather") or [{}])[0].get("main", "")
        wdesc = (data.get("weather") or [{}])[0].get("description", "")

        return {
            "city": data.get("name", city),
            "temp_c": temp_c,
            "temp_f": round((temp_c * 9 / 5) + 32, 1) if isinstance(temp_c, (int, float)) else None,
            "humidity": data.get("main", {}).get("humidity"),
            "conditions": wdesc,
            "wind_mps": wind_mps,
            "wind_mph": round(wind_mps * 2.23694, 1) if isinstance(wind_mps, (int, float)) else None,
            "emoji": _emoji_for(wid, wmain, wdesc),
        }
    except Exception:
        return None

def _coords_for(city: str, key: str):
    base = "https://api.openweathermap.org/data/2.5/weather"
    session = requests.Session()
    params = {"appid": key, "units": "metric"}
    mzip = _US_ZIP.match(city)
    if mzip:
        params["zip"] = f"{mzip.group(1)},US"
    else:
        params["q"] = _normalize_city_query(city)
    try:
        r = session.get(base, params=params, timeout=6)
        if r.status_code == 404 and not mzip:
            r = session.get(base, params={"q": city, "appid": key, "units": "metric"}, timeout=6)
        r.raise_for_status()
        data = r.json()
        coord = data.get("coord") or {}
        tz = data.get("timezone", 0)
        name = data.get("name", city)
        return coord.get("lat"), coord.get("lon"), tz, name
    except Exception:
        return None

def get_forecast_for_city(city: str | None) -> Optional[List[Dict]]:
    if not city:
        return None
    key = _get_api_key()
    if not key:
        return None

    coords = _coords_for(city, key)
    if not coords:
        return None
    lat, lon, tz_offset, _ = coords

    url = "https://api.openweathermap.org/data/2.5/forecast"
    try:
        r = requests.get(url, params={"lat": lat, "lon": lon, "appid": key, "units": "metric"}, timeout=8)
        r.raise_for_status()
        data = r.json()
        items = data.get("list") or []
        by_date: dict[str, list[dict]] = defaultdict(list)
        for it in items:
            dt_utc = datetime.fromtimestamp(it["dt"], tz=timezone.utc)
            local_dt = dt_utc + timedelta(seconds=tz_offset)
            local_date = local_dt.strftime("%Y-%m-%d")
            by_date[local_date].append(it)

        daily = []
        for date_str, bucket in sorted(by_date.items()):
            temps = [x.get("main", {}).get("temp") for x in bucket if isinstance(x.get("main", {}).get("temp"), (int,float))]
            hums = [x.get("main", {}).get("humidity") for x in bucket if isinstance(x.get("main", {}).get("humidity"), (int,float))]
            winds = [x.get("wind", {}).get("speed") for x in bucket if isinstance(x.get("wind", {}).get("speed"), (int,float))]
            conds = [((x.get("weather") or [{}])[0].get("id", 800),
                      (x.get("weather") or [{}])[0].get("main", ""),
                      (x.get("weather") or [{}])[0].get("description","")) for x in bucket]
            if not temps:
                continue
            tmin_c = min(temps)
            tmax_c = max(temps)
            desc_counts = Counter([c[2] for c in conds if c[2]])
            top_desc = (desc_counts.most_common(1)[0][0]) if desc_counts else "clear sky"
            wid, wmain, wdesc = conds[0] if conds else (800, "Clear", top_desc)
            emoji = _emoji_for(wid, wmain, top_desc)

            dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
            day = dt_obj.strftime("%a")

            daily.append({
                "date": date_str,
                "day": day,
                "temp_min_c": round(tmin_c, 1),
                "temp_max_c": round(tmax_c, 1),
                "temp_min_f": round((tmin_c * 9/5) + 32, 1),
                "temp_max_f": round((tmax_c * 9/5) + 32, 1),
                "humidity": round(sum(hums)/len(hums)) if hums else None,
                "wind_mps": round(sum(winds)/len(winds), 1) if winds else None,
                "wind_mph": round((sum(winds)/len(winds)) * 2.23694, 1) if winds else None,
                "conditions": top_desc,
                "emoji": emoji,
            })

        return daily[:6]
    except Exception:
        return None

def _fmt_hour_label(dt_local: datetime) -> str:
    # Cross-platform 12h format without leading zero
    label = dt_local.strftime("%I%p")  # e.g., "01PM"
    return label.lstrip("0") if label[0] == "0" else label

def get_hourly_for_city(city: str | None) -> Optional[List[Dict]]:
    """
    Return hourly entries:
      - Remaining hours for today (3-hour steps)
      - If none remain (end of day), return the first few hours of tomorrow.
    """
    if not city:
        return None
    key = _get_api_key()
    if not key:
        return None

    coords = _coords_for(city, key)
    if not coords:
        return None
    lat, lon, tz_offset, _ = coords

    url = "https://api.openweathermap.org/data/2.5/forecast"
    try:
        r = requests.get(url, params={"lat": lat, "lon": lon, "appid": key, "units": "metric"}, timeout=8)
        r.raise_for_status()
        data = r.json()
        items = data.get("list") or []

        now_local = datetime.now(timezone.utc) + timedelta(seconds=tz_offset)
        today_str = now_local.strftime("%Y-%m-%d")

        today_future = []
        tomorrow = []

        for it in items:
            dt_local = datetime.fromtimestamp(it["dt"], tz=timezone.utc) + timedelta(seconds=tz_offset)
            date_str = dt_local.strftime("%Y-%m-%d")

            temp_c = it.get("main", {}).get("temp")
            if not isinstance(temp_c, (int, float)):
                continue

            wid = (it.get("weather") or [{}])[0].get("id", 800)
            wmain = (it.get("weather") or [{}])[0].get("main", "")
            wdesc = (it.get("weather") or [{}])[0].get("description", "")

            entry = {
                "time": _fmt_hour_label(dt_local),
                "temp_c": temp_c,
                "temp_f": round((temp_c * 9/5) + 32, 1),
                "emoji": _emoji_for(wid, wmain, wdesc),
            }

            if date_str == today_str and dt_local > now_local:
                today_future.append(entry)
            elif len(tomorrow) < 8 and date_str != today_str:
                # collect next day early hours (cap to keep UI tight)
                tomorrow.append(entry)

        if today_future:
            return today_future[:8]
        if tomorrow:
            return tomorrow[:8]

        return []
    except Exception:
        return None

def get_weather_alerts_for_city(current: Optional[Dict], forecast: Optional[List[Dict]]) -> List[Dict]:
    alerts: List[Dict] = []
    try:
        if current and isinstance(current.get("temp_f"), (int, float)):
            if current["temp_f"] >= 95:
                alerts.append({"title": "Heat Advisory", "desc": "High temperatures. Water may evaporate quickly."})
            if current["temp_f"] <= 35:
                alerts.append({"title": "Freeze Risk", "desc": "Protect sensitive plants from cold exposure."})
        if current and isinstance(current.get("wind_mph"), (int, float)) and current["wind_mph"] >= 20:
            alerts.append({"title": "Windy Conditions", "desc": "Strong winds can increase transpiration and stress."})

        if forecast:
            for d in forecast[:2]:
                if isinstance(d.get("temp_max_f"), (int,float)) and d["temp_max_f"] >= 95:
                    alerts.append({"title": "Upcoming Heat", "desc": f"Highs near {round(d['temp_max_f'])}°F expected."})
                if isinstance(d.get("temp_min_f"), (int,float)) and d["temp_min_f"] <= 35:
                    alerts.append({"title": "Cold Overnight", "desc": f"Lows near {round(d['temp_min_f'])}°F expected."})
                if isinstance(d.get("wind_mph"), (int,float)) and d["wind_mph"] >= 20:
                    alerts.append({"title": "Windy Forecast", "desc": "Elevated winds expected. Consider wind protection."})
    except Exception:
        return []

    seen = set()
    unique = []
    for a in alerts:
        key = (a["title"], a["desc"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(a)
    return unique
