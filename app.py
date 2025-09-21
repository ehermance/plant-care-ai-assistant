from flask import Flask, render_template, request
from dotenv import load_dotenv
import os

# ---- Bootstrapping & config ----
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-not-secret")

# ---- Health check route ----
@app.route("/healthz")
def healthz():
    return "OK", 200

# ---- Tiny rule-based "brain" (no APIs yet) ----
def basic_plant_tip(question: str, plant: str | None) -> str:
    """
    Extremely simple placeholder logic:
    - Looks for certain keywords and returns a canned tip.
    - This helps us confirm the POST cycle and template rendering before adding APIs.
    """
    q = (question or "").lower()
    p = (plant or "").strip()
    if "water" in q:
        return f"For {p or 'your plant'}, water when the top inch of soil is dry. Use a slow, deep soak and empty saucers."
    if "light" in q or "sun" in q:
        return f"{p or 'Most houseplants'} prefer bright, indirect light. Avoid harsh midday sun against glass."
    if "fertil" in q:
        return f"Feed {p or 'your plant'} at 1/4–1/2 strength every 4–6 weeks during active growth; skip in winter."
    return f"For {p or 'your plant'}, start simple: bright-indirect light, water when top inch is dry, and check drainage."

# ---- Home: shows the form and (optionally) last answer ----
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", answer=None)

# ---- Handle submissions ----
@app.route("/ask", methods=["POST"])
def ask():
    """
    1) Read inputs from the form (question, plant, city).
    2) Generate a placeholder answer with basic_plant_tip().
    3) Render the template with the answer.
    """
    question = request.form.get("question", "")
    plant = request.form.get("plant", "")
    city = request.form.get("city", "")

    # For now, ignore city (we’ll use it when we add weather).
    answer = basic_plant_tip(question, plant)

    return render_template(
        "index.html",
        answer=answer,
        form_values={"question": question, "plant": plant, "city": city},
    )

if __name__ == "__main__":
    app.run(debug=True)
