from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
import os, requests, datetime
from collections import deque

# ---- Bootstrapping & config ----
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-not-secret")

# In-memory history (resets on server restart)
HISTORY = deque(maxlen=25)  # keep last 25 Q&As
# Tracks the most recent AI error (shown in UI and /debug)
AI_LAST_ERROR = None


# ---------- Small utils ----------
def _mask(s: str, keep: int = 6) -> str:
    if not s:
        return ""
    s = s.strip()
    return s[:keep] + "…" + f"({len(s)} chars)"


# ---------- OpenAI import/version helper ----------
def _openai_client_and_version():
    """
    Try to import OpenAI client and return (OpenAI_ctor, version_str).
    If only the legacy module exists, return (None, version_str).
    If not importable at all, return (None, None).
    """
    try:
        import openai  # noqa: F401
        try:
            from openai import OpenAI
            return OpenAI, getattr(openai, "__version__", "unknown")
        except Exception:
            # Legacy module present, but no OpenAI class
            return None, getattr(openai, "__version__", "unknown")
    except Exception:
        return None, None


# ---------- HEALTH & DEBUG ----------
@app.route("/healthz")
def healthz():
    return "OK", 200


@app.route("/debug")
def debug_info():
    loaded_keys = [k for k in ("FLASK_SECRET_KEY", "OPENWEATHER_API_KEY", "OPENAI_API_KEY") if os.getenv(k)]
    OpenAI_ctor, openai_ver = _openai_client_and_version()
    ai_import_ok = (OpenAI_ctor is not None or openai_ver is not None)

    key_raw = os.getenv("OPENAI_API_KEY") or app.config.get("OPENAI_API_KEY") or ""
    masked_key = _mask(key_raw, keep=6) if key_raw else ""

    info = {
        "loaded_env_vars": loaded_keys,
        "flask_secret_key_set": "FLASK_SECRET_KEY" in loaded_keys,
        "weather_api_configured": "OPENWEATHER_API_KEY" in loaded_keys,
        "openai_configured": "OPENAI_API_KEY" in loaded_keys,
        "openai_sdk_import_ok": ai_import_ok,
        "openai_sdk_version": openai_ver,
        "openai_key_masked": masked_key,
        "history_len": len(HISTORY),
        "ai_last_error": AI_LAST_ERROR,
    }

    # Optional: tiny smoke test when ?ai=1 (returns ok/error/model)
    if request.args.get("ai") == "1" and key_raw and ai_import_ok:
        ok, err, model_used = ai_smoke_test()
        info["openai_smoke_test"] = ok
        info["openai_smoke_error"] = err
        info["openai_smoke_model"] = model_used

    return info


@app.route("/history/clear")
def clear_history():
    HISTORY.clear()
    return redirect(url_for("index"))


# ---------- CORE HELPERS ----------
def get_weather_for_city(city: str) -> dict | None:
    """
    Read the OpenWeather key at call time (better for tests & runtime changes).
    Return a normalized dict or None on any error.
    """
    openweather_key = os.getenv("OPENWEATHER_API_KEY") or app.config.get("OPENWEATHER_API_KEY")
    if not city or not openweather_key:
        return None
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": openweather_key, "units": "metric"}
        r = requests.get(url, params=params, timeout=6)
        r.raise_for_status()
        data = r.json()
        return {
            "city": data.get("name", city),
            "temp_c": data.get("main", {}).get("temp"),
            "humidity": data.get("main", {}).get("humidity"),
            "conditions": (data.get("weather") or [{}])[0].get("description"),
            "wind_mps": data.get("wind", {}).get("speed"),
        }
    except Exception:
        return None


def basic_plant_tip(question: str, plant: str | None) -> str:
    q = (question or "").lower()
    p = (plant or "").strip() or "your plant"
    if "water" in q:
        return f"For {p}, water when the top 2–3 cm of soil is dry. Soak thoroughly; empty the saucer."
    if "light" in q or "sun" in q:
        return f"{p.capitalize()} typically prefers bright, indirect light. Avoid harsh midday sun behind glass."
    if "fertil" in q or "feed" in q:
        return f"Feed {p} at 1/4–1/2 strength every 4–6 weeks during active growth; pause in winter."
    if "repot" in q or "pot" in q:
        return f"Repot {p} only when rootbound; choose a pot 2–5 cm wider with a free-draining mix."
    return f"For {p}, keep it simple: bright-indirect light, water when the top inch is dry, and ensure drainage."


def weather_adjustment_tip(weather: dict | None, plant: str | None) -> str | None:
    if not weather or weather.get("temp_c") is None:
        return None
    t = weather["temp_c"]
    p = plant or "your plant"
    if t >= 32:
        return f"It’s hot (~{t:.0f}°C). Check {p} more often; water may evaporate quickly. Avoid midday repotting."
    if t <= 5:
        return f"It’s cold (~{t:.0f}°C). Keep {p} away from drafts/windows and reduce watering frequency."
    return f"Current temp ~{t:.0f}°C. Maintain your usual schedule; always verify soil moisture first."


# ---------- OPENAI (Optional) ----------
def ai_smoke_test() -> tuple[bool, str | None, str | None]:
    """
    Try a minimal AI call and report (ok, error_message, model_used).
    We try a small list of models in order to handle availability differences.
    """
    openai_key = os.getenv("OPENAI_API_KEY") or app.config.get("OPENAI_API_KEY")
    if not openai_key:
        return False, "No OPENAI_API_KEY", None

    models_to_try = ["gpt-4o-mini", "gpt-4o"]
    OpenAI_ctor, _ = _openai_client_and_version()

    try:
        if OpenAI_ctor is not None:
            client = OpenAI_ctor(api_key=openai_key)
            last_err = None
            for m in models_to_try:
                try:
                    r = client.chat.completions.create(
                        model=m,
                        temperature=0,
                        max_tokens=10,
                        messages=[{"role": "user", "content": "Say OK"}],
                    )
                    txt = (r.choices[0].message.content or "").strip().lower()
                    return ("ok" in txt, None, m)
                except Exception as e:
                    last_err = str(e)
            return False, last_err, None
        else:
            # Legacy fallback
            import openai as _openai_mod  # type: ignore
            _openai_mod.api_key = openai_key
            last_err = None
            for m in models_to_try:
                try:
                    r = _openai_mod.ChatCompletion.create(
                        model=m,
                        temperature=0,
                        max_tokens=10,
                        messages=[{"role": "user", "content": "Say OK"}],
                    )
                    txt = (r["choices"][0]["message"]["content"] or "").strip().lower()
                    return ("ok" in txt, None, m)
                except Exception as e:
                    last_err = str(e)
            return False, last_err, None
    except Exception as e:
        return False, str(e), None


def ai_advice(question: str, plant: str | None, weather: dict | None) -> str | None:
    global AI_LAST_ERROR
    AI_LAST_ERROR = None  # reset on each attempt

    openai_key = os.getenv("OPENAI_API_KEY") or app.config.get("OPENAI_API_KEY")
    if not openai_key:
        AI_LAST_ERROR = "OPENAI_API_KEY not configured"
        return None

    p = (plant or "").strip()
    parts = []
    if weather:
        if weather.get("city"): parts.append(f"city: {weather['city']}")
        if weather.get("temp_c") is not None: parts.append(f"temp_c: {weather['temp_c']}")
        if weather.get("humidity") is not None: parts.append(f"humidity: {weather['humidity']}%")
        if weather.get("conditions"): parts.append(f"conditions: {weather['conditions']}")
    w_summary = ", ".join(parts) if parts else None

    sys_msg = (
        "You are a plant-care expert. Give safe, concise, practical steps. "
        "Assume indoor care unless the user implies outdoor. If uncertain, say so."
    )
    user_msg = (
        f"Plant: {p or 'unspecified'}\n"
        f"Question: {question.strip()}\n"
        f"Weather: {w_summary or 'n/a'}\n\n"
        "Respond with 3–6 short bullet points."
    )

    models_to_try = ["gpt-4o-mini", "gpt-4o"]

    try:
        OpenAI_ctor, _ = _openai_client_and_version()
        if OpenAI_ctor is not None:
            client = OpenAI_ctor(api_key=openai_key)

            # A) Chat Completions
            last_err = None
            for m in models_to_try:
                try:
                    resp = client.chat.completions.create(
                        model=m,
                        temperature=0.3,
                        max_tokens=350,
                        messages=[{"role": "system", "content": sys_msg},
                                  {"role": "user", "content": user_msg}],
                    )
                    text = resp.choices[0].message.content.strip()
                    if text:
                        AI_LAST_ERROR = None
                        return text
                except Exception as e:
                    last_err = e

            # B) Responses API
            for m in models_to_try:
                try:
                    resp2 = client.responses.create(
                        model=m,
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
                        else:
                            txt = ""
                    if txt:
                        AI_LAST_ERROR = None
                        return txt
                except Exception as e:
                    last_err = e

            AI_LAST_ERROR = str(last_err)[:300] if last_err else "Unknown OpenAI error"
            return None

        # Legacy module-style
        try:
            import openai as _openai_mod  # type: ignore
            _openai_mod.api_key = openai_key
            last_err = None
            for m in models_to_try:
                try:
                    resp = _openai_mod.ChatCompletion.create(
                        model=m,
                        temperature=0.3,
                        max_tokens=350,
                        messages=[{"role": "system", "content": sys_msg},
                                  {"role": "user", "content": user_msg}],
                    )
                    txt = resp["choices"][0]["message"]["content"].strip()
                    if txt:
                        AI_LAST_ERROR = None
                        return txt
                except Exception as e:
                    last_err = e
            AI_LAST_ERROR = str(last_err)[:300] if last_err else "Unknown OpenAI error"
            return None
        except Exception as e:
            AI_LAST_ERROR = str(e)[:300]
            return None

    except Exception as e:
        AI_LAST_ERROR = str(e)[:300]
        return None


# ---------- ADVICE ENGINE ----------
def generate_advice(question: str, plant: str, city: str):
    """
    Pipeline:
      1) Try to fetch weather (best-effort; may be None).
      2) Try OpenAI (if configured) for the main answer.
      3) If AI not available or fails, use rule-based answer.
      4) Optionally append a small weather-specific tip for clarity.
    """
    weather = get_weather_for_city(city)

    # Try AI first for richer guidance
    ai = ai_advice(question, plant, weather)
    if ai:
        answer = ai
        source = "ai"
    else:
        # Fallback: rule-based baseline
        answer = basic_plant_tip(question, plant)
        source = "rule"

    # Add a one-liner weather tip (keeps responses consistent)
    w_tip = weather_adjustment_tip(weather, plant)
    if w_tip:
        city_name = weather.get("city") if weather else city
        suffix = f"\n\nWeather tip for {city_name}: {w_tip}"
        answer = f"{answer}{suffix}"

    return answer, weather, source


# ---------- ROUTES ----------
@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        answer=None,
        history=list(HISTORY),
        ai_error=None,
        source=None,        # keep template logic simple on first load
        form_values=None,   # avoids undefined in inputs
        weather=None,       # no weather yet
    )


@app.route("/ask", methods=["POST"])
def ask():
    question = request.form.get("question", "")
    plant = request.form.get("plant", "")
    city = request.form.get("city", "")

    answer, weather, source = generate_advice(question, plant, city)

    # Save to in-memory history
    HISTORY.appendleft({
        "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plant": plant,
        "city": city,
        "question": question,
        "answer": answer,
        "weather": weather,
        "source": source,  # "ai" or "rule"
    })

    return render_template(
        "index.html",
        answer=answer,
        weather=weather,
        form_values={"question": question, "plant": plant, "city": city},
        history=list(HISTORY),
        source=source,
        ai_error=AI_LAST_ERROR,
    )


if __name__ == "__main__":
    app.run(debug=True)
