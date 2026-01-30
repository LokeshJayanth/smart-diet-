import csv
import json
import os


# Knowledge Base (FOL rules as dictionary)
rules = {
    "Diabetic": [
        "Avoid sugar",
        "Include whole grains",
        "Eat more vegetables",
        "Prefer low-glycemic index foods",
        "Distribute carbs evenly across meals",
    ],
    "Underweight": [
        "High protein diet",
        "Frequent meals",
        "Include nuts and seeds",
        "Add calorie-dense healthy fats (olive oil, nut butters)",
    ],
    "Overweight": [
        "Low-calorie diet",
        "Exercise regularly",
        "Avoid fried foods",
        "Prefer high-fiber, low-calorie density foods",
        "Limit sugary beverages",
    ],
    "Vegetarian": [
        "Avoid meat",
        "Include pulses and legumes",
        "Eat more vegetables",
        "Ensure B12 sources (fortified foods or supplements)",
    ],
    "NonVegetarian": [
        "Prefer lean meats (chicken, turkey)",
        "Include fish rich in omega-3",
        "Limit processed meats",
        "Balance plate with vegetables and whole grains",
    ],
    "Hypertension": [
        "Low salt diet",
        "Avoid processed food",
        "Include fruits and vegetables",
        "Prefer DASH-style diet",
        "Limit alcohol",
    ],
    "Normal": [
        "Balanced diet",
        "Include fruits, vegetables, proteins, and carbs",
        "Stay hydrated",
    ],
    # Additional conditions
    "Anemia": [
        "Increase iron-rich foods",
        "Include vitamin C for iron absorption",
        "Consider leafy greens",
        "Prefer heme iron sources if non-vegetarian",
    ],
    "HighCholesterol": [
        "Prefer unsaturated fats",
        "Increase soluble fiber",
        "Limit red meat",
        "Avoid trans fats",
        "Include plant sterols/stanols",
    ],
    "KidneyFriendly": [
        "Control protein intake",
        "Limit sodium",
        "Monitor potassium and phosphorus",
        "Stay within fluid limits if prescribed",
    ],
}

# Category priorities (higher value = higher priority)
# These help rank suggestions when multiple categories apply
CATEGORY_PRIORITY = {
    "Diabetic": 100,
    "Hypertension": 95,
    "HighCholesterol": 90,
    "KidneyFriendly": 85,
    "Overweight": 80,
    "Underweight": 80,
    "Anemia": 75,
    "Vegetarian": 60,
    "NonVegetarian": 60,
    "Normal": 50,
}


def load_additional_rules(json_path: str | None = None):
    """Optionally extend rules from a JSON file with structure {category: [rules...]}."""
    if not json_path:
        return
    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for key, values in data.items():
                    if not isinstance(values, list):
                        continue
                    existing = set(rules.get(key, []))
                    merged = sorted(existing.union(values))
                    rules[key] = merged
    except Exception:
        # Silently ignore malformed files in production usage; keep core KB
        pass


def load_foods_csv(csv_path: str | None = None):
    """Load a simple foods dataset with boolean diet flags.

    Expected CSV headers (case-insensitive):
      name, vegetarian, diabetic_friendly, hypertension_friendly, weight_goal
    - vegetarian: true/false
    - diabetic_friendly: true/false
    - hypertension_friendly: true/false
    - weight_goal: one of {loss, gain, maintain}
    """
    foods = []
    if not csv_path or not os.path.exists(csv_path):
        return foods
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row:
                    continue
                def to_bool(val):
                    return str(val).strip().lower() in {"1", "true", "yes", "y"}
                foods.append({
                    "name": (row.get("name") or "").strip(),
                    "vegetarian": to_bool(row.get("vegetarian")),
                    "diabetic_friendly": to_bool(row.get("diabetic_friendly")),
                    "hypertension_friendly": to_bool(row.get("hypertension_friendly")),
                    "weight_goal": (row.get("weight_goal") or "").strip().lower(),
                })
    except Exception:
        return []
    return foods
