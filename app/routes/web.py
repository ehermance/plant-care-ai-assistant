"""
UI routes and request flow.

Serves the main page, handles submissions, validates input, runs moderation,
invokes the advice engine, and records in-memory history. Keeps templates
simple by providing all variables the UI needs.
"""

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from datetime import datetime
from collections import deque

from ..extensions import limiter
from ..services.ai import generate_advice, AI_LAST_ERROR
from ..services.moderation import run_moderation
from ..utils.validation import validate_inputs, display_sanitize_short

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
    return render_template(
        "index.html",
        answer=None,
        weather=None,
        form_values=None,
        history=list(HISTORY),
        has_history=len(HISTORY) > 0,
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
    - Store a compact history item
    - Re-render the page with the answer and context
    """
    payload, err_msg = validate_inputs(request.form)

    if err_msg:
        # Return a friendly message and keep the fields so the user can fix & resubmit.
        return render_template(
            "index.html",
            answer=display_sanitize_short(err_msg),
            weather=None,
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

    # Light, fast moderation pass before any external calls/logging.
    allowed, reason = run_moderation(question)
    if not allowed:
        return render_template(
            "index.html",
            answer=display_sanitize_short(f"Question blocked by content policy: {reason}"),
            weather=None,
            form_values=payload,
            history=list(HISTORY),
            has_history=len(HISTORY) > 0,
            source="rule",
            ai_error=None,
        ), 400

    # Advice engine performs best-effort weather fetch internally and picks AI or rule-based output.
    answer, weather, source = generate_advice(
        question=question,
        plant=plant,
        city=city,
        care_context=care_context,
    )

    # Minimal history item for recall; avoids storing secrets or long blobs.
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
        form_values={"plant": plant, "city": city, "care_context": care_context, "question": question},
        history=list(HISTORY),
        has_history=len(HISTORY) > 0,
        source=source,
        ai_error=AI_LAST_ERROR,  # non-empty if AI failed and fallback triggered
    )
