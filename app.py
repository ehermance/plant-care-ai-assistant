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

# ---------- HEALTH & DEBUG ----------
@app.route("/healthz")
def healthz():
    return "OK", 200

@app.route("/debug")
def debug_info():
    loaded_keys = [k for k in ("FLASK_SECRET_KEY", "OPENWEATHER_API_KEY", "OPENAI_API_KEY") if os.getenv(k)]
    return {
        "loaded_env_vars": loaded_keys,
        "flask_secret_key_set": "FLASK_SECRET_KEY" in loaded_keys,
        "weather_api_configured": "OPENWEATHER_API_KEY" in loaded_keys,
        "openai_configured": "OPENAI_API_KEY" in loaded_keys,
        "history_len": len(HISTORY),
    }

@app.route("/history/clear")
def clear_history():
    HISTORY.clear()
    return redirect(url_for("index"))


# ---------- CORE HELPERS ----------
def get_weather_for_city(city: str) -> dict | None:
    # Read at call time so tests (and runtime) can override easily
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
def ai_advice(question: str, plant: str | None, weather: dict | None) -> str | None:
    """
    Best-effort: if OPENAI_API_KEY is set, ask an LLM for advice.
    Returns None on any error so we can fall back gracefully.
    """
    openai_key = os.getenv("OPENAI_API_KEY") or app.config.get("OPENAI_API_KEY")
    if not openai_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        p = (plant or "").strip()
        w_summary = None
        if weather:
            parts = []
            if weather.get("city"): parts.append(f"city: {weather['city']}")
            if weather.get("temp_c") is not None: parts.append(f"temp_c: {weather['temp_c']}")
            if weather.get("humidity") is not None: parts.append(f"humidity: {weather['humidity']}%")
            if weather.get("conditions"): parts.append(f"conditions: {weather['conditions']}")
            w_summary = ", ".join(parts) if parts else None

        sys = (
            "You are a plant-care expert. Give safe, concise steps. "
            "Prefer practical, testable actions. If uncertain, say so."
        )
        usr = (
            f"Plant: {p or 'unspecified'}\n"
            f"Question: {question.strip()}\n"
            f"Weather: {w_summary or 'n/a'}\n\n"
            "Respond with 3–6 short bullet points."
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=350,
            messages=[{"role": "system", "content": sys},
                      {"role": "user", "content": usr}]
        )
        return resp.choices[0].message.content.strip()

    except Exception:
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
        # If AI already discussed weather, this still adds a clear, consistent note.
        answer = f"{answer}{suffix}"

    return answer, weather, source


# ---------- ROUTES ----------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", answer=None, history=list(HISTORY))

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
    )


if __name__ == "__main__":
    app.run(debug=True)
