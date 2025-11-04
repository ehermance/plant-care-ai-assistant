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

# Track which AI provider was actually used for the last successful response
AI_LAST_PROVIDER: Optional[str] = None

# Cache for LiteLLM Router to avoid recreating on every request
_ROUTER_CACHE: Optional[object] = None


def _clear_router_cache():
    """Clear the router cache. Used for testing and when API keys change."""
    global _ROUTER_CACHE
    _ROUTER_CACHE = None


def _get_litellm_router():
    """
    Returns a LiteLLM Router configured with OpenAI (primary) and Gemini (fallback),
    or (None, error) if neither API key is available.

    Reads API keys from environment first; if a Flask app context is active,
    also checks current_app.config.

    PERFORMANCE: Router is cached to avoid recreation on every request.
    """
    global _ROUTER_CACHE

    # Return cached router if available
    if _ROUTER_CACHE is not None:
        return _ROUTER_CACHE, None

    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not openai_key and has_app_context():
        openai_key = current_app.config.get("OPENAI_API_KEY")
    if not gemini_key and has_app_context():
        gemini_key = current_app.config.get("GEMINI_API_KEY")

    if not openai_key and not gemini_key:
        return None, "Neither OPENAI_API_KEY nor GEMINI_API_KEY configured"

    try:
        from litellm import Router

        model_list = []
        fallbacks = {}

        # Add OpenAI as primary if key exists
        if openai_key:
            model_list.append({
                "model_name": "primary-gpt",
                "litellm_params": {
                    "model": "gpt-4o-mini",
                    "api_key": openai_key,
                    "temperature": 0.3,
                    "max_tokens": 1500,  # Increased from 350 to match Gemini
                }
            })

        # Add Gemini as fallback if key exists
        if gemini_key:
            model_list.append({
                "model_name": "fallback-gemini",
                "litellm_params": {
                    "model": "gemini/gemini-flash-latest",
                    "api_key": gemini_key,
                    "temperature": 0.3,
                    "max_tokens": 1500,  # Increased from 350 to avoid truncation
                }
            })

        # Configure fallback chain: OpenAI -> Gemini
        if openai_key and gemini_key:
            fallbacks = [{"primary-gpt": ["fallback-gemini"]}]

        router = Router(
            model_list=model_list,
            fallbacks=fallbacks if fallbacks else None,
            num_retries=2,
            timeout=30,
        )

        # Cache the router for future requests
        _ROUTER_CACHE = router
        return router, None
    except Exception as e:
        return None, f"LiteLLM Router initialization error: {e}"

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

def _weather_tip(weather: Optional[dict], plant: Optional[str], care_context: Optional[str] = None) -> Optional[str]:
    """
    Tiny, safe hint based on temperature (thresholds in °C), but display both °C/°F when possible.
    Only shows tips for outdoor plants (outdoor_potted, outdoor_bed).

    Args:
        weather: Weather dict with temp_c and optional care_context
        plant: Plant name for personalization
        care_context: Location context (outdoor_potted, outdoor_bed, indoor_potted, etc.)
                     Can also be passed in weather dict as weather["care_context"]
    """
    if not weather or weather.get("temp_c") is None:
        return None

    # Get care_context from parameter or weather dict, default to outdoor_potted for backward compatibility
    context = care_context or weather.get("care_context", "outdoor_potted")

    # Only show weather tips for outdoor plants (not indoor)
    if "indoor" in context.lower():
        return None

    t_c = weather["temp_c"]
    temp_str = _fmt_temp(weather)
    name = plant or "the plant"
    try:
        if t_c >= 32:
            return f"It's hot ({temp_str}). Check {name} more often; water may evaporate quickly."
        if t_c <= 5:
            return f"It's cold ({temp_str}). Keep {name} away from drafts and reduce watering."
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


def _ai_advice(question: str, plant: Optional[str], weather: Optional[dict], care_context: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Calls AI providers using LiteLLM Router (OpenAI primary, Gemini fallback).
    Returns (response_text, provider_name) or (None, None) if all providers fail.
    The caller will use rule-based output if this returns (None, None).
    """
    global AI_LAST_ERROR, AI_LAST_PROVIDER
    AI_LAST_ERROR = None
    AI_LAST_PROVIDER = None

    router, err = _get_litellm_router()
    if not router:
        AI_LAST_ERROR = err or "AI Router initialization failed"
        return None, None

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
        "You are a helpful plant-care expert with calm persona. Provide safe, concise, accurate, and practical steps. "
        "If uncertain, say so."
    )
    user_msg = (
        f"Plant: {(plant or '').strip() or 'unspecified'}\n"
        f"Care context: {context_str}\n"
        f"Question: {question.strip()}\n"
        f"Weather: {w_summary or 'n/a'}\n\n"
        "Respond with one short, introductory sentence, 3–6 short bullet points, and a final encouraging sentence."
    )

    try:
        # Use LiteLLM Router with automatic fallback
        # Start with primary model (OpenAI if configured)
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key and has_app_context():
            openai_key = current_app.config.get("OPENAI_API_KEY")

        model_to_use = "primary-gpt" if openai_key else "fallback-gemini"

        resp = router.completion(
            model=model_to_use,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg}
            ],
        )

        txt = (resp.choices[0].message.content or "").strip()

        if txt:
            # Determine which provider was actually used
            model_used = getattr(resp, "model", None) or model_to_use
            if "gemini" in model_used.lower():
                AI_LAST_PROVIDER = "gemini"
                return txt, "gemini"
            else:
                AI_LAST_PROVIDER = "openai"
                return txt, "openai"

        AI_LAST_ERROR = "Empty response from AI providers"
        return None, None
    except Exception as e:
        # Never raise; capture a short reason for /debug and the template.
        AI_LAST_ERROR = str(e)[:300]
        return None, None


def ai_advice(
    question: str,
    plant: str | None,
    weather: dict | None,
    care_context: str | None = "indoor_potted",
) -> str | None:
    """
    Back-compat shim for any code/tests that import ai_advice directly.
    Returns just the text response, discarding the provider information.
    """
    text, _provider = _ai_advice(question, plant, weather, care_context or "indoor_potted")
    return text


def generate_advice(
    question: str,
    plant: Optional[str],
    city: Optional[str],
    care_context: str,
) -> Tuple[str, Optional[dict], str]:
    """
    Orchestrates advice generation:
      1) Best-effort weather fetch (does not block if it fails)
      2) Try AI providers (OpenAI primary, Gemini fallback); on failure, fall back to rules
      3) Append a short weather hint when available
    Returns (answer, weather, source: "openai"|"gemini"|"rule")
    """
    weather = get_weather_for_city(city) if city else None

    ai_text, provider = _ai_advice(question, plant, weather, care_context)
    if ai_text and provider:
        answer = ai_text
        source = provider  # "openai" or "gemini"
    else:
        answer = _basic_plant_tip(question, plant, care_context)
        source = "rule"

    hint = _weather_tip(weather, plant, care_context)
    if hint:
        city_name = weather.get("city") if weather else (city or "")
        suffix = f"\n\nWeather tip{(' for ' + city_name) if city_name else ''}: {hint}"
        answer = f"{answer}{suffix}"

    return answer, weather, source