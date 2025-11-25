"""
Advice engine (AI-first with safe fallback).

Attempts to get guidance from OpenAI when available; otherwise falls back
to a compact rule set. Adds a short weather hint if current temperature is known.
OpenAI usage is isolated and failures never break the request flow.
"""

from __future__ import annotations
import os
from typing import Tuple, Optional, Dict, Any

from flask import current_app, has_app_context
from .weather import get_weather_for_city
from . import user_context

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


def detect_question_type(question: str, selected_plant_id: Optional[str]) -> str:
    """
    Detect question type to determine appropriate context level.

    Returns "plant" (Tier 2) or "diagnosis" (Tier 3 premium) based on question content.
    All questions default to rich plant-aware context (Tier 2).
    Diagnosis questions with health concerns trigger premium diagnostic features (Tier 3).

    Args:
        question: User's question text
        selected_plant_id: Whether user selected a specific plant

    Returns:
        "plant" - Plant-specific rich context (Tier 2 default)
        "diagnosis" - Full diagnostic context with health trends (Tier 3 premium)

    Examples:
        >>> detect_question_type("Why are my leaves yellow?", "plant-123")
        'diagnosis'
        >>> detect_question_type("How often should I water?", "plant-123")
        'plant'
    """
    q_lower = question.lower()

    # Diagnosis indicators (trigger premium Tier 3 features)
    diagnosis_keywords = [
        "yellow", "brown", "droopy", "drooping", "wilting", "wilt",
        "dying", "dead", "sick", "unhealthy", "problem", "wrong",
        "help", "issue", "concern", "worry", "pest", "bug", "disease",
        "spots", "curling", "crispy", "mushy", "rot"
    ]

    if any(kw in q_lower for kw in diagnosis_keywords):
        return "diagnosis"

    # All other questions use rich plant-aware context (Tier 2)
    return "plant"


def is_watering_question(question: str) -> bool:
    """
    Detect if question is asking about watering recommendations.

    Args:
        question: User's question text

    Returns:
        True if question is about watering

    Examples:
        >>> is_watering_question("Should I water my plant today?")
        True
        >>> is_watering_question("What type of soil should I use?")
        False
    """
    q_lower = question.lower()

    # Watering question patterns
    watering_keywords = [
        "should i water", "do i need to water", "time to water",
        "water today", "water my", "watering", "need water",
        "how much water", "when to water", "water schedule",
        "water now", "ready for water", "thirsty",
        "needs water", "need watering"
    ]

    return any(keyword in q_lower for keyword in watering_keywords)


def build_system_prompt(
    user_context_data: Optional[Dict[str, Any]] = None,
    context_level: str = "plant"
) -> str:
    """
    Build AI system prompt with enhanced context and weather awareness.

    Args:
        user_context_data: Enhanced context from get_enhanced_user_context() or
                          get_enhanced_plant_context()
        context_level: "plant" (Tier 2 default) or "diagnosis" (Tier 3 premium)

    Returns:
        System prompt string with rich context and weather insights
    """
    base = (
        "You are a helpful plant-care expert with calm persona. "
        "Provide safe, concise, accurate, and practical steps. "
        "Reference the user's specific observations and care history when relevant. "
        "If uncertain, say so."
    )

    if not user_context_data:
        return base

    # Build enhanced context summary for prompt
    context_lines = []

    # WEATHER CONTEXT (Phase 2 - Weather-aware AI)
    weather_context = user_context_data.get("weather_context")
    if weather_context:
        context_lines.append(f"Current weather: {weather_context}")

    # WATERING RECOMMENDATION (intelligent stress-based analysis)
    watering_rec = user_context_data.get("watering_recommendation")
    if watering_rec:
        rec_text = watering_rec.get("recommendation", "")
        reason = watering_rec.get("reason", "")
        if rec_text:
            context_lines.append(f"Watering analysis: {rec_text}")
            if reason:
                context_lines.append(f"  Reason: {reason}")

    # USER'S PLANTS with notes and patterns
    plants = user_context_data.get("plants", [])
    if plants:
        for p in plants[:5]:  # Limit to 5 plants
            plant_info = p.get("name", "Unknown")
            if p.get("species"):
                plant_info += f" ({p['species']})"

            # Add notes summary if available
            if p.get("notes_summary"):
                plant_info += f" - {p['notes_summary']}"

            # Add watering pattern if available
            if p.get("watering_pattern"):
                plant_info += f" [watered {p['watering_pattern']}]"

            context_lines.append(f"Plant: {plant_info}")

    # SPECIFIC PLANT CONTEXT (from get_enhanced_plant_context)
    plant_details = user_context_data.get("plant")
    if plant_details:
        plant_name = plant_details.get("name", "Plant")
        context_lines.append(f"Selected plant: {plant_name}")

        # Add full plant notes
        if plant_details.get("notes_full"):
            notes = plant_details["notes_full"]
            context_lines.append(f"Plant notes: {notes}")

        # Add care history summary
        care_history = plant_details.get("care_history_summary", {})
        if care_history.get("avg_watering_interval_days"):
            interval = care_history["avg_watering_interval_days"]
            consistency = care_history.get("watering_consistency", "")
            context_lines.append(f"Watering pattern: every ~{interval} days ({consistency})")

        if care_history.get("care_level"):
            care_level = care_history["care_level"]
            context_lines.append(f"Care level: {care_level}")

    # RECENT OBSERVATIONS with health keywords
    recent_obs = user_context_data.get("recent_observations", [])
    if recent_obs:
        context_lines.append("Recent observations:")
        for obs in recent_obs[:3]:  # Max 3
            days_ago = obs.get("days_ago", 0)
            note = obs.get("note_preview", "")
            if obs.get("has_concern"):
                context_lines.append(f"  ⚠ {days_ago}d ago: {note}")
            else:
                context_lines.append(f"  • {days_ago}d ago: {note}")

    # HEALTH PATTERNS (for diagnosis context level)
    if context_level == "diagnosis":
        health_trends = user_context_data.get("health_trends")
        if health_trends:
            concerns = health_trends.get("recent_concerns", [])
            if concerns:
                context_lines.append(f"Health concerns: {', '.join(concerns)}")

            if health_trends.get("improving"):
                context_lines.append("Trend: Improving (fewer issues recently)")
            elif health_trends.get("deteriorating"):
                context_lines.append("Trend: Deteriorating (more issues recently)")

        # Comparative insights (premium)
        comparative = user_context_data.get("comparative_insights")
        if comparative:
            vs_avg = comparative.get("watering_vs_user_avg")
            if vs_avg == "more_frequent_than_others":
                context_lines.append("This plant is watered more frequently than user's other plants")
            elif vs_avg == "less_frequent_than_others":
                context_lines.append("This plant is watered less frequently than user's other plants")

    # REMINDERS
    reminders = user_context_data.get("reminders", {})
    if reminders:
        due_today = reminders.get("due_today", [])
        if due_today:
            tasks = [r["title"] for r in due_today[:3]]
            context_lines.append(f"Care due today: {', '.join(tasks)}")

        overdue = reminders.get("overdue", [])
        if overdue:
            context_lines.append(f"Overdue tasks: {len(overdue)}")

    # Build final context section
    if context_lines:
        context_section = "\n\nUser Context:\n" + "\n".join(f"- {line}" for line in context_lines)
        return base + context_section

    return base


def _ai_advice(
    question: str,
    plant: Optional[str],
    weather: Optional[dict],
    care_context: str,
    user_context_data: Optional[Dict[str, Any]] = None,
    context_level: str = "plant"
) -> Tuple[Optional[str], Optional[str]]:
    """
    Calls AI providers using LiteLLM Router (OpenAI primary, Gemini fallback).
    Returns (response_text, provider_name) or (None, None) if all providers fail.
    The caller will use rule-based output if this returns (None, None).

    Args:
        question: User's question
        plant: Plant name/species
        weather: Weather dict
        care_context: Location context
        user_context_data: Enhanced context data
        context_level: "plant" (Tier 2) or "diagnosis" (Tier 3)

    Returns:
        Tuple of (response_text, provider_name) or (None, None)
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

    # Build system message with enhanced user context and context level
    sys_msg = build_system_prompt(user_context_data, context_level=context_level)

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
    text, _provider = _ai_advice(question, plant, weather, care_context or "indoor_potted", None)
    return text


def generate_advice(
    question: str,
    plant: Optional[str],
    city: Optional[str],
    care_context: str,
    user_id: Optional[str] = None,
    selected_plant_id: Optional[str] = None,
) -> Tuple[str, Optional[dict], str]:
    """
    Orchestrates advice generation with enhanced context and weather awareness.

    Enhanced with:
      - Rich plant-aware context (Tier 2 default for all users)
      - Premium diagnostic features (Tier 3 for premium users)
      - Weather-aware insights integrated into context
      - Pattern recognition from care history
      - Health trend analysis

    Steps:
      1) Fetch weather data (best-effort)
      2) Detect question type (plant vs diagnosis)
      3) Fetch enhanced user context with weather awareness
      4) Try AI providers (OpenAI primary, Gemini fallback) with rich context
      5) Fallback to rules if AI unavailable

    Args:
        question: User's plant care question
        plant: Plant name or species
        city: City for weather data
        care_context: indoor_potted, outdoor_potted, or outdoor_bed
        user_id: Optional user ID for context fetching
        selected_plant_id: Optional specific plant ID for detailed context

    Returns:
        Tuple of (answer, weather, source: "openai"|"gemini"|"rule")
    """
    # Fetch weather first (needed for weather-aware context)
    weather = get_weather_for_city(city) if city else None

    # Detect question type to determine context level
    context_level = detect_question_type(question, selected_plant_id)

    # Determine if user has premium tier (TODO: integrate with subscription system)
    # For now, diagnosis questions trigger premium features for all users
    is_premium = (context_level == "diagnosis")

    # Fetch enhanced user context if authenticated
    user_context_data = None
    if user_id:
        try:
            if selected_plant_id:
                # Get enhanced plant-specific context with weather
                user_context_data = user_context.get_enhanced_plant_context(
                    user_id,
                    selected_plant_id,
                    weather=weather,
                    is_premium=is_premium
                )
            else:
                # Get enhanced general user context with weather
                user_context_data = user_context.get_enhanced_user_context(
                    user_id,
                    weather=weather
                )
        except Exception as e:
            # If context fetch fails, continue without it (graceful degradation)
            # Log error for debugging
            from app.utils.errors import log_info
            log_info(f"Context fetch failed: {str(e)}")
            user_context_data = None

    # Detect watering questions and generate intelligent recommendations
    if is_watering_question(question) and selected_plant_id and weather:
        try:
            from . import watering_intelligence
            from .journal import get_last_watered_date

            # Get last watered date for stress calculation
            last_watered = get_last_watered_date(selected_plant_id, user_id) if user_id else None

            # Calculate hours since watered
            hours_since_watered = None
            if last_watered:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                if last_watered.tzinfo is None:
                    # Make timezone-aware if naive
                    from datetime import timezone
                    last_watered = last_watered.replace(tzinfo=timezone.utc)
                hours_since_watered = (now - last_watered).total_seconds() / 3600

            # Determine plant type from care_context
            plant_type = "houseplant"
            if care_context == "outdoor_bed":
                # Could be shrubs or wildflowers - default to shrub
                plant_type = "outdoor_shrub"
            elif care_context == "outdoor_potted":
                plant_type = "outdoor_shrub"

            # Generate watering recommendation
            watering_rec = watering_intelligence.generate_watering_recommendation(
                plant_name=plant or "Your plant",
                hours_since_watered=hours_since_watered,
                weather=weather,
                plant_type=plant_type,
                plant_age_weeks=None,  # TODO: Track plant age for wildflowers
                hours_since_rain=None,  # TODO: Track rain data
                recent_rain=False,  # TODO: Integrate rain tracking
                rain_expected=False  # TODO: Check forecast for rain
            )

            # Add watering recommendation to context
            if user_context_data is None:
                user_context_data = {}
            user_context_data["watering_recommendation"] = watering_rec

        except Exception as e:
            # If watering intelligence fails, continue without it
            from app.utils.errors import log_info
            log_info(f"Watering intelligence failed: {str(e)}")
            pass

    # Call AI with enhanced context (context_level passed to build_system_prompt)
    ai_text, provider = _ai_advice(
        question,
        plant,
        weather,
        care_context,
        user_context_data,
        context_level=context_level
    )

    if ai_text and provider:
        answer = ai_text
        source = provider  # "openai" or "gemini"
    else:
        answer = _basic_plant_tip(question, plant, care_context)
        source = "rule"

    # Weather tip is now integrated into context, but keep as fallback for non-authenticated
    if not user_id:
        hint = _weather_tip(weather, plant, care_context)
        if hint:
            city_name = weather.get("city") if weather else (city or "")
            suffix = f"\n\nWeather tip{(' for ' + city_name) if city_name else ''}: {hint}"
            answer = f"{answer}{suffix}"

    return answer, weather, source