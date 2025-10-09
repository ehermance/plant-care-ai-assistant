"""
UI routes and request flow.

Serves the main page, handles submissions, validates input, runs moderation,
invokes the advice engine, and records per-user (per-session) history. Using
Flask's session ensures each visitor sees only their own history, while keeping
the payload compact and free of secrets.
"""

from __future__ import annotations

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    current_app,
    session,  # <-- per-user history lives here
)
from datetime import datetime

from ..extensions import limiter
from ..services.ai import generate_advice, AI_LAST_ERROR
from ..services.moderation import run_moderation
from ..utils.validation import validate_inputs, display_sanitize_short

# Optional forecast import (kept safe for environments/tests without it)
try:
    from ..services.weather import get_forecast_for_city  # type: ignore
except Exception:  # pragma: no cover
    def get_forecast_for_city(city):
        return None


# ----------------------------
# Per-session history helpers
# ----------------------------

_MAX_HISTORY = 25  # trim to a small number so session cookies stay small


def _get_history() -> list[dict]:
    """
    Return the current user's history list from the Flask session.
    The session is a signed cookie unique to the user's browser.
    """
    hist = session.get("history")
    return hist if isinstance(hist, list) else []


def _save_history(items: list[dict]) -> None:
    """
    Persist a compact list of dicts in the session. Avoid large blobs or secrets.
    Flask will sign the cookie to prevent tampering.
    """
    session["history"] = items[:_MAX_HISTORY]


def _append_history(item: dict) -> None:
    """
    Prepend a new item, trim to the size limit, then save back to the session.
    """
    hist = _get_history()
    hist.insert(0, item)
    _save_history(hist)


def _clear_history() -> None:
    """Remove the user's history from the session."""
    session.pop("history", None)


# ----------------------------
# Blueprint & routes
# ----------------------------

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
    loaded_keys = [
        k
        for k in ("FLASK_SECRET_KEY", "OPENWEATHER_API_KEY", "OPENAI_API_KEY")
        if current_app.config.get(k)
    ]
    info = {
        "loaded_env_vars": loaded_keys,
        "flask_secret_key_set": bool(current_app.secret_key),
        "weather_api_configured": bool(current_app.config.get("OPENWEATHER_API_KEY")),
        "openai_configured": bool(current_app.config.get("OPENAI_API_KEY")),
        "history_len": len(_get_history()),
        "ai_last_error": AI_LAST_ERROR,
    }
    return info


@web_bp.route("/history/clear")
@limiter.exempt  # optional: exempt from rate limit noise
def clear_history():
    """Clears the current user's in-session Q&A history."""
    _clear_history()
    return redirect(url_for("web.index"))


@web_bp.route("/", methods=["GET"])
@limiter.limit("120 per minute")  # modest protection for the index page
def index():
    """
    Render the main page on GET. The template uses these variables to decide
    what to show; passing explicit None keeps Jinja conditional logic simple.
    """
    history = _get_history()
    return render_template(
        "index.html",
        answer=None,
        weather=None,
        forecast=None,
        form_values=None,
        history=history,
        has_history=len(history) > 0,
        source=None,
        ai_error=None,
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
    - Store a compact, per-user history item in the session
    - Re-render the page with the answer and context
    """
    payload, err_msg = validate_inputs(request.form)

    if err_msg:
        history = _get_history()
        return render_template(
            "index.html",
            answer=display_sanitize_short(err_msg),
            weather=None,
            forecast=None,
            form_values={
                "plant": request.form.get("plant", ""),
                "city": request.form.get("city", ""),
                "care_context": request.form.get("care_context", "indoor_potted"),
                "question": request.form.get("question", ""),
            },
            history=history,
            has_history=len(history) > 0,
            source="rule",
            ai_error=None,
        ), 400

    plant = payload["plant"]
    city = payload["city"]
    care_context = payload["care_context"]
    question = payload["question"]

    allowed, reason = run_moderation(question)
    if not allowed:
        history = _get_history()
        return render_template(
            "index.html",
            answer=display_sanitize_short(f"Question blocked by content policy: {reason}"),
            weather=None,
            forecast=None,
            form_values=payload,
            history=history,
            has_history=len(history) > 0,
            source="rule",
            ai_error=None,
        ), 400

    # Advice engine returns (answer, weather, source)
    answer, weather, source = generate_advice(
        question=question,
        plant=plant,
        city=city,
        care_context=care_context,
    )

    # 5-day forecast is best-effort and independent of the advice pipeline
    forecast = get_forecast_for_city(city) if city else None

    # Save minimal, non-sensitive history data per user (session cookie)
    _append_history(
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
    history = _get_history()

    return render_template(
        "index.html",
        answer=answer,
        weather=weather,
        forecast=forecast,
        form_values={
            "plant": plant,
            "city": city,
            "care_context": care_context,
            "question": question,
        },
        history=history,
        has_history=len(history) > 0,
        source=source,
        ai_error=AI_LAST_ERROR,  # non-empty if AI failed and fallback triggered
    )
