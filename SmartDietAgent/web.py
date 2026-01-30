from flask import Flask, render_template, request
from agent import SmartDietAgent


app = Flask(__name__)


@app.get("/")
def index():
    return render_template(
        "index.html",
        weight_opts=["Underweight", "Overweight", "Normal"],
        condition_opts=["Diabetic", "Hypertension", "Normal"],
        diet_opts=["Vegetarian", "NonVegetarian"],
    )


@app.post("/suggest")
def suggest():
    name = (request.form.get("name") or "John").strip()
    try:
        age = int(request.form.get("age") or 30)
    except Exception:
        age = 30

    weight_status = request.form.get("weight_status") or None
    health_condition = request.form.get("health_condition") or "Diabetic"
    diet_preference = request.form.get("diet_preference") or "Vegetarian"

    weight_raw = (request.form.get("weight_kg") or "").strip()
    height_raw = (request.form.get("height_cm") or "").strip()
    # allow comma decimals; be robust to invalid input
    def to_float_or_none(text: str):
        if not text:
            return None
        try:
            return float(text.replace(",", "."))
        except Exception:
            return None
    weight_kg = to_float_or_none(weight_raw)
    height_cm = to_float_or_none(height_raw)

    user_profile = {
        "name": name,
        "age": age,
        "weight_status": weight_status,
        "health_condition": health_condition,
        "diet_preference": diet_preference,
    }
    if weight_kg and height_cm:
        user_profile["weight_kg"] = weight_kg
        user_profile["height_cm"] = height_cm

    agent = SmartDietAgent(user_profile)
    suggestions, explanations = agent.infer_diet_with_explanations()
    ranked = agent.rank_suggestions(suggestions, explanations)

    bmi = agent.user_profile.get("bmi")
    inferred_weight_status = agent.user_profile.get("weight_status")
    recommended_foods = agent.recommend_foods()

    return render_template(
        "results.html",
        name=name,
        ranked=ranked,
        explanations=explanations,
        bmi=bmi,
        inferred_weight_status=inferred_weight_status,
        recommended_foods=recommended_foods,
    )


if __name__ == "__main__":
    # Run Flask dev server
    app.run(host="127.0.0.1", port=5000, debug=True)


