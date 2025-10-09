"""
UI routes and request flow.

Renders the main page, handles submissions, validates input, runs moderation,
invokes the advice engine, and records an in-memory history. Keeps templates
simple by passing exactly what they need. Rate-limited for basic abuse control.
"""

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from datetime import datetime
from collections import deque

from ..extensions import limiter
from ..services.ai import generate_advice, AI_LAST_ERROR
from ..services.moderation import run_moderation
from ..utils.validation import validate_inputs, display_sanitize_short

try:
    from ..services.weather import (
        get_forecast_for_city,
        get_hourly_for_city,
        get_weather_alerts_for_city,
    )  # type: ignore
except Exception:  # pragma: no cover
    def get_forecast_for_city(city): return None
    def get_hourly_for_city(city): return None
    def get_weather_alerts_for_city(current, forecast): return []

HISTORY = deque(maxlen=25)
web_bp = Blueprint("web", __name__)

@web_bp.route("/healthz")
def healthz():
    return "OK", 200

@web_bp.route("/debug")
def debug_info():
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
@limiter.exempt
def clear_history():
    HISTORY.clear()
    return redirect(url_for("web.index"))

@web_bp.route("/", methods=["GET"])
@limiter.limit("120 per minute")
def index():
    return render_template(
        "index.html",
        answer=None,
        weather=None,
        forecast=None,
        hourly=None,
        alerts=None,
        form_values=None,
        history=list(HISTORY),
        has_history=len(HISTORY) > 0,
        source=None,
        ai_error=None,
    )

@web_bp.route("/ask", methods=["POST"])
@limiter.limit("30 per minute")
def ask():
    payload, err_msg = validate_inputs(request.form)

    if err_msg:
        return render_template(
            "index.html",
            answer=display_sanitize_short(err_msg),
            weather=None,
            forecast=None,
            hourly=None,
            alerts=None,
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
        ), 400

    plant = payload["plant"]
    city = payload["city"]
    care_context = payload["care_context"]
    question = payload["question"]

    allowed, reason = run_moderation(question)
    if not allowed:
        return render_template(
            "index.html",
            answer=display_sanitize_short(f"Question blocked by content policy: {reason}"),
            weather=None,
            forecast=None,
            hourly=None,
            alerts=None,
            form_values=payload,
            history=list(HISTORY),
            has_history=len(HISTORY) > 0,
            source="rule",
            ai_error=None,
        ), 400

    answer, weather, source = generate_advice(
        question=question,
        plant=plant,
        city=city,
        care_context=care_context,
    )

    forecast = get_forecast_for_city(city) if city else None
    hourly = get_hourly_for_city(city) if city else None
    alerts = get_weather_alerts_for_city(weather, forecast)

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

    return render_template(
        "index.html",
        answer=answer,
        weather=weather,
        forecast=forecast,
        hourly=hourly,
        alerts=alerts,
        form_values={"plant": plant, "city": city, "care_context": care_context, "question": question},
        history=list(HISTORY),
        has_history=len(HISTORY) > 0,
        source=source,
        ai_error=AI_LAST_ERROR,
    )
