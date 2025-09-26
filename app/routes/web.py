"""
Implements UI routes: home page, question submission, debug info, and clearing
history. Orchestrates validation, moderation, weather retrieval, AI fallback,
and renders template context. Maintains an in-memory Q&A history.
"""

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from datetime import datetime
from collections import deque

from ..extensions import limiter
from ..services.weather import get_weather_for_city
from ..services.ai import ai_advice, AI_LAST_ERROR
from ..services.moderation import run_moderation
from ..utils.validation import validate_inputs, looks_sensitive, redact_pii, display_sanitize_short

# Blueprint must be defined before using it in decorators.
web_bp = Blueprint("web", __name__)

# Ephemeral history (resets on process restart).
HISTORY = deque(maxlen=25)

def basic_plant_tip(q, p):
    """Small ruleset for resilient fallback answers."""
    q = (q or "").lower()
    p = (p or "").strip() or "your plant"
    if "water" in q:
        return f"For {p}, water when the top 2–3 cm of soil is dry. Soak thoroughly; empty the saucer."
    if "light" in q or "sun" in q:
        return f"{p.capitalize()} typically prefers bright, indirect light. Avoid harsh midday sun behind glass."
    if "fertil" in q or "feed" in q:
        return f"Feed {p} at 1/4–1/2 strength every 4–6 weeks during active growth; pause in winter."
    if "repot" in q or "pot" in q:
        return f"Repot {p} only when rootbound; choose a pot 2–5 cm wider with a free-draining mix."
    return f"For {p}, keep it simple: bright-indirect light, water when the top inch is dry, and ensure drainage."

def weather_adjustment_tip(weather, plant):
    """Append a concise temperature-aware tip when data is available."""
    if not weather or weather.get("temp_c") is None:
        return None
    t = weather["temp_c"]; p = plant or "your plant"
    if t >= 32:
        return f"It’s hot (~{t:.0f}°C). Check {p} more often; water may evaporate quickly. Avoid midday repotting."
    if t <= 5:
        return f"It’s cold (~{t:.0f}°C). Keep {p} away from drafts/windows and reduce watering frequency."
    return f"Current temp ~{t:.0f}°C. Maintain your usual schedule; always verify soil moisture first."

@web_bp.route("/healthz")
def healthz():
    return "OK", 200

@web_bp.route("/debug")
def debug_info():
    import os
    loaded = [k for k in ("FLASK_SECRET_KEY","OPENWEATHER_API_KEY","OPENAI_API_KEY") if os.getenv(k)]
    return {
        "loaded_env_vars": loaded,
        "history_len": len(HISTORY),
        "ai_last_error": AI_LAST_ERROR,
        "rate_limit_default": current_app.config.get("RATE_LIMIT_DEFAULT"),
        "rate_limit_ask": current_app.config.get("RATE_LIMIT_ASK"),
        "rate_limit_enabled": current_app.config.get("RATE_LIMIT_ENABLED"),
    }

@web_bp.route("/history/clear")
def clear_history():
    HISTORY.clear()
    return redirect(url_for("web.index"))

@web_bp.route("/", methods=["GET"])
def index():
    """Render the main page. JavaScript handles presets and the loading UI."""
    return render_template(
        "index.html",
        answer=None,
        history=list(HISTORY),
        ai_error=None,
        source=None,
        form_values=None,
        weather=None
    )

@web_bp.route("/ask", methods=["POST"])
@limiter.limit(lambda: current_app.config.get("RATE_LIMIT_ASK", "20 per minute;200 per day"))
def ask():
    """Validate → moderate → get weather → ask AI with fallback → render answer."""
    question = request.form.get("question", "") or ""
    plant = request.form.get("plant", "") or ""
    city = request.form.get("city", "") or ""

    # 1) Validation
    ok, err = validate_inputs(plant, city, question)
    if not ok:
        answer, weather, source = err, None, "rule"
    # 2) Pre-check for obviously sensitive content
    elif looks_sensitive(question):
        answer, weather, source = "I can’t help with requests for confidential access or illegal activities.", None, "rule"
    else:
        # 3) Moderation (input)
        allowed, reason = run_moderation(question)
        if not allowed:
            answer, weather, source = "Your question can’t be answered due to content restrictions.", None, "rule"
        else:
            # 4) Weather (best-effort) and 5) AI with graceful fallback
            weather = get_weather_for_city(city)
            ai = ai_advice(question, plant, weather)
            if ai:
                answer, source = ai, "ai"
                # 6) Moderation (output) to prevent unsafe model responses
                allowed_out, reason_out = run_moderation(answer)
                if not allowed_out:
                    answer, source = basic_plant_tip(question, plant), "rule"
            else:
                answer, source = basic_plant_tip(question, plant), "rule"

            # Consistent context: include a short weather note when possible.
            w_tip = weather_adjustment_tip(weather, plant)
            if w_tip:
                city_name = weather.get("city") if weather else city
                answer += f"\n\nWeather tip for {city_name}: {w_tip}"

    # Record a sanitized copy in history (for the sidebar).
    HISTORY.appendleft({
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plant": display_sanitize_short(redact_pii(plant)) if plant else plant,
        "city": display_sanitize_short(redact_pii(city)) if city else city,
        "question": redact_pii(question),
        "answer": answer,
        "weather": weather if 'weather' in locals() else None,
        "source": source,
    })

    return render_template(
        "index.html",
        answer=answer,
        weather=weather if 'weather' in locals() else None,
        form_values={"question": question, "plant": plant, "city": city},
        history=list(HISTORY),
        source=source,
        ai_error=AI_LAST_ERROR,
    )
