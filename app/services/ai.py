"""
Advice engine (AI-first with safe fallback).

Attempts to get guidance from OpenAI when available; otherwise falls back
to a compact rule set. Adds a short weather hint if current temperature is known.
OpenAI usage is isolated and failures never break the request flow.
"""

from __future__ import annotations
import os
from typing import Tuple, Optional

from flask import current_app, has_app_context
from .weather import get_weather_for_city

# Most recent AI error (shown in UI/Debug to help diagnose model/key issues)

AI_LAST_ERROR: Optional[str] = None


def _openai_client():
    """
    Returns an OpenAI client or (None, error).

    Reads OPENAI_API_KEY from the environment first; if a Flask app context is
    active, also checks current_app.config. This avoids touching current_app
    during unit tests that import this module without an application context.
    """
    key = os.getenv("OPENAI_API_KEY")
    if not key and has_app_context():
        key = current_app.config.get("OPENAI_API_KEY")

    if not key:
        return None, "OPENAI_API_KEY not configured"

    # Prefer modern SDK first; fall back to legacy if present.
    try:
        from openai import OpenAI
        return OpenAI(api_key=key), None
    except Exception as e:
        try:
            import openai as legacy  # type: ignore
            legacy.api_key = key
            return legacy, None
        except Exception as e2:
            return None, f"OpenAI import error: {e or e2}"

def _fmt_temp(weather: Optional[dict]) -> str:
    """Return a compact temperature string using both units when available."""
    if not weather:
        return "n/a"
    t_c = weather.get("temp_c")
    t_f = weather.get("temp_f")
    try:
        if isinstance(t_c, (int, float)) and isinstance(t_f, (int, float)):
            return f"~{t_c:.0f}°C / {t_f:.0f}°F"
        if isinstance(t_c, (int, float)):
            return f"~{t_c:.0f}°C"
        if isinstance(t_f, (int, float)):
            return f"~{t_f:.0f}°F"
    except Exception:
        pass
    return "n/a"

def _weather_tip(weather: Optional[dict], plant: Optional[str]) -> Optional[str]:
    """
    Tiny, safe hint based on temperature (thresholds in °C), but display both °C/°F when possible.
    """
    if not weather or weather.get("temp_c") is None:
        return None

    t_c = weather["temp_c"]
    temp_str = _fmt_temp(weather)
    name = plant or "the plant"
    try:
        if t_c >= 32:
            return f"It’s hot ({temp_str}). Check {name} more often; water may evaporate quickly."
        if t_c <= 5:
            return f"It’s cold ({temp_str}). Keep {name} away from drafts and reduce watering."
        return f"Current temp {temp_str}. Maintain your usual schedule; verify soil moisture first."
    except Exception:
        return None


def _basic_plant_tip(question: str, plant: Optional[str], care_context: str) -> str:
    """
    Minimal rules for a predictable fallback response. Slight phrasing changes
    make answers feel relevant without needing a large ruleset.
    """
    q = (question or "").lower()
    p = (plant or "").strip() or "the plant"

    loc = {
        "indoor_potted": f"{p} indoors",
        "outdoor_potted": f"{p} outdoors in a pot",
        "outdoor_bed": f"{p} in a garden bed",
    }.get(care_context, p)

    if "water" in q:
        return f"For {loc}, water when the top 2–3 cm of soil is dry. Soak thoroughly and ensure drainage."
    if "light" in q or "sun" in q:
        return f"{loc.capitalize()} generally prefers bright, indirect light unless it’s sun-tolerant."
    if "fertil" in q or "feed" in q:
        return f"Feed {loc} at 1/4–1/2 strength every 4–6 weeks during active growth; reduce in winter."
    if "repot" in q or "pot" in q:
        return f"Repot {loc} only when root-bound; choose a pot 2–5 cm wider with a free-draining mix."
    return f"For {loc}, aim for bright-indirect light, water when the top inch is dry, and ensure good drainage."


def _ai_advice(question: str, plant: Optional[str], weather: Optional[dict], care_context: str) -> Optional[str]:
    """
    Calls OpenAI via the modern SDK if available; falls back to the Responses API;
    if both fail, returns None (the caller will use rule-based output).
    """
    global AI_LAST_ERROR
    AI_LAST_ERROR = None

    client, err = _openai_client()
    if not client:
        AI_LAST_ERROR = err or "Unknown OpenAI client error"
        return None

    # Compact weather summary included in the prompt when available.
    w_summary = None
    if weather:
        parts = []
        city = weather.get("city")
        if city:
            parts.append(f"city: {city}")

        temp_c = weather.get("temp_c")
        if temp_c is not None:
            parts.append(f"temp_c: {temp_c}")

        temp_f = weather.get("temp_f")
        if temp_f is not None:
            parts.append(f"temp_f: {temp_f}")

        hum = weather.get("humidity")
        if hum is not None:
            parts.append(f"humidity: {hum}%")

        cond = weather.get("conditions")
        if cond:
            parts.append(f"conditions: {cond}")

        wind_mps = weather.get("wind_mps")
        if wind_mps is not None:
            parts.append(f"wind_mps: {wind_mps}")

        wind_mph = weather.get("wind_mph")
        if wind_mph is not None:
            parts.append(f"wind_mph: {wind_mph}")

        w_summary = ", ".join(parts) if parts else None

    context_map = {
        "indoor_potted": "potted house plant (indoors)",
        "outdoor_potted": "potted plant kept outdoors",
        "outdoor_bed": "plant grown in an outdoor garden bed",
    }
    context_str = context_map.get(care_context, "potted house plant (indoors)")

    sys_msg = (
        "You are a plant-care expert. Provide safe, concise, practical steps. "
        "If uncertain, say so."
    )
    user_msg = (
        f"Plant: {(plant or '').strip() or 'unspecified'}\n"
        f"Care context: {context_str}\n"
        f"Question: {question.strip()}\n"
        f"Weather: {w_summary or 'n/a'}\n\n"
        "Respond with 3–6 short bullet points."
    )

    try:
        # Modern Chat Completions
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=350,
                messages=[{"role": "system", "content": sys_msg},
                          {"role": "user", "content": user_msg}],
            )
            txt = (resp.choices[0].message.content or "").strip()
            if txt:
                return txt

        # Responses API (SDK-dependent)
        if hasattr(client, "responses") and hasattr(client.responses, "create"):
            resp2 = client.responses.create(
                model="gpt-4o-mini",
                input=[{"role": "system", "content": sys_msg},
                       {"role": "user", "content": user_msg}],
                temperature=0.3,
                max_output_tokens=350,
            )
            txt = getattr(resp2, "output_text", None)
            if not txt:
                content = getattr(resp2, "content", None)
                if isinstance(content, list) and content and hasattr(content[0], "text"):
                    txt = getattr(content[0].text, "value", "").strip()
                elif isinstance(content, str):
                    txt = content.strip()
            if txt:
                return txt

        AI_LAST_ERROR = "No usable OpenAI response (model/path mismatch)"
        return None
    except Exception as e:
        # Never raise; capture a short reason for /debug and the template.
        AI_LAST_ERROR = str(e)[:300]
        return None


def ai_advice(
    question: str,
    plant: str | None,
    weather: dict | None,
    care_context: str | None = "indoor_potted",
) -> str | None:
    """
    Back-compat shim for any code/tests that import ai_advice directly.
    """
    return _ai_advice(question, plant, weather, care_context or "indoor_potted")


def generate_advice(
    question: str,
    plant: Optional[str],
    city: Optional[str],
    care_context: str,
) -> Tuple[str, Optional[dict], str]:
    """
    Orchestrates advice generation:
      1) Best-effort weather fetch (does not block if it fails)
      2) Try OpenAI; on failure, fall back to rules
      3) Append a short weather hint when available
    Returns (answer, weather, source: "ai"|"rule")
    """
    weather = get_weather_for_city(city) if city else None

    ai_text = _ai_advice(question, plant, weather, care_context)
    if ai_text:
        answer = ai_text
        source = "ai"
    else:
        answer = _basic_plant_tip(question, plant, care_context)
        source = "rule"

    hint = _weather_tip(weather, plant)
    if hint:
        city_name = weather.get("city") if weather else (city or "")
        suffix = f"\n\nWeather tip{(' for ' + city_name) if city_name else ''}: {hint}"
        answer = f"{answer}{suffix}"

    return answer, weather, source