"""
UI routes and request flow.

Serves the main page, handles submissions, validates input, runs moderation,
invokes the advice engine, pulls best-effort forecast/hourly data, and records
in-memory history. Keeps templates simple by passing everything they need.
"""

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from datetime import datetime
from collections import deque

from ..extensions import limiter
from ..services.ai import generate_advice, AI_LAST_ERROR
from ..services.moderation import run_moderation
from ..utils.validation import validate_inputs, display_sanitize_short

# Optional forecast import (kept safe for environments/tests without it)

try:
    from ..services.weather import get_hourly_for_city
except Exception:  # pragma: no cover
    def get_hourly_for_city(city):
        return None
try:
    from ..services.weather import get_forecast_for_city
except Exception:  # pragma: no cover
    def get_forecast_for_city(city):
        return None

# Small, ephemeral history kept in memory for convenience. Clears on restart.
HISTORY = deque(maxlen=25)

web_bp = Blueprint("web", __name__)


@web_bp.route("/healthz")
def healthz():
    """Simple health endpoint to verify the server responds."""
    return "OK", 200


@web_bp.route("/debug")
def debug_info():
    """
    Lightweight status snapshot for troubleshooting. The template controls
    visibility (requires UI flag or ?debug=true); this endpoint itself stays simple.
    """
    loaded_keys = [k for k in ("FLASK_SECRET_KEY", "OPENWEATHER_API_KEY", "OPENAI_API_KEY") if current_app.config.get(k)]
    info = {
        "loaded_env_vars": loaded_keys,
        "flask_secret_key_set": bool(current_app.secret_key),
        "weather_api_configured": bool(current_app.config.get("OPENWEATHER_API_KEY")),
        "openai_configured": bool(current_app.config.get("OPENAI_API_KEY")),
        "history_len": len(HISTORY),
        "ai_last_error": AI_LAST_ERROR,
    }
    return info


@web_bp.route("/history/clear")
@limiter.exempt  # optional: exempt from rate limit noise
def clear_history():
    """Clears the in-memory Q&A history."""
    HISTORY.clear()
    return redirect(url_for("web.index"))


@web_bp.route("/", methods=["GET"])
@limiter.limit("120 per minute")  # modest protection for the index page
def index():
    """
    Render the main page on GET. The template uses these variables to decide
    what to show; passing explicit None keeps Jinja conditional logic simple.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        "index.html",
        answer=None,
        weather=None,
        forecast=None,
        hourly=None,
        form_values=None,
        history=list(HISTORY),
        has_history=len(HISTORY) > 0,
        source=None,
        ai_error=None,
        today_str=today_str,
    )


@web_bp.route("/ask", methods=["POST"])
@limiter.limit("30 per minute")  # protects the form handler from burst abuse
def ask():
    """
    Process a submission:
    - Validate/normalize form fields
    - Block unsafe content via moderation
    - Generate advice (AI-first, rule fallback)
    - Fetch a 5-day forecast (best-effort)
    - Derive an hourly list for the rest of today (best-effort)
    - Store a compact history item
    - Re-render the page with the answer and context
    """
    payload, err_msg = validate_inputs(request.form)

    if err_msg:
        today_str = datetime.now().strftime("%Y-%m-%d")
        return render_template(
            "index.html",
            answer=display_sanitize_short(err_msg),
            weather=None,
            forecast=None,
            hourly=None,
            form_values={
                "plant": request.form.get("plant", ""),
                "city": request.form.get("city", ""),
                "care_context": request.form.get("care_context", "indoor_potted"),
                "question": request.form.get("question", ""),
            },
            history=list(HISTORY),
            has_history=len(HISTORY) > 0,
            source="rule",
            ai_error=None,
            today_str=today_str,
        ), 400

    plant = payload["plant"]
    city = payload["city"]
    care_context = payload["care_context"]
    question = payload["question"]

    allowed, reason = run_moderation(question)
    if not allowed:
        today_str = datetime.now().strftime("%Y-%m-%d")
        return render_template(
            "index.html",
            answer=display_sanitize_short(f"Question blocked by content policy: {reason}"),
            weather=None,
            forecast=None,
            hourly=None,
            form_values=payload,
            history=list(HISTORY),
            has_history=len(HISTORY) > 0,
            source="rule",
            ai_error=None,
            today_str=today_str,
        ), 400

    # Advice engine returns (answer, weather, source)
    answer, weather, source = generate_advice(
        question=question,
        plant=plant,
        city=city,
        care_context=care_context,
    )

    # Hourly (best-effort): if the weather payload includes an 'hourly' list
    hourly = None
    if isinstance(weather, dict):
        raw = weather.get("hourly")
        if isinstance(raw, list) and raw:
            today_str = datetime.now().strftime("%Y-%m-%d")
            filtered = [h for h in raw if (
                (isinstance(h, dict) and (
                    h.get("date") == today_str or
                    h.get("day_iso") == today_str or
                    (isinstance(h.get("dt_iso"), str) and h["dt_iso"].startswith(today_str)) or
                    h.get("is_today") is True
                ))
            )]
            hourly = filtered if filtered else raw[:8]
    # Best-effort fetch if not present
    if (not hourly) and city:
        hourly = get_hourly_for_city(city)
    if isinstance(hourly, list) and not hourly:
        hourly = None

    # Forecast (best-effort): we will only show 5 future days in the UI (today + 5 = 6 cards)
    forecast = get_forecast_for_city(city) if city else None
    if isinstance(forecast, list):
        forecast = forecast[:5]  # enforce exactly +5 days in UI

    # Record history
    HISTORY.appendleft(
        {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plant": plant,
            "city": city,
            "care_context": care_context,
            "question": question,
            "answer": answer,
            "weather": weather,
            "source": source,
        }
    )

    today_str = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        "index.html",
        answer=answer,
        weather=weather,
        forecast=forecast,
        hourly=hourly,
        form_values={"plant": plant, "city": city, "care_context": care_context, "question": question},
        history=list(HISTORY),
        has_history=len(HISTORY) > 0,
        source=source,
        ai_error=AI_LAST_ERROR,
        today_str=today_str,
    )