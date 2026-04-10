# Smart Diet Suggestion Agent - Complete Project Documentation

## 📋 Project Overview

**Smart Diet Suggestion Agent** is an AI-powered knowledge-based agent that provides personalized diet suggestions using First Order Logic (FOL)-style rules. The system can run in both CLI and Web UI modes, offering customized dietary recommendations based on user profiles including health conditions, weight status, and dietary preferences.

### Key Features
- **Knowledge-Based Reasoning**: Uses FOL-style rules for diet suggestion logic
- **BMI Auto-Inference**: Automatically calculates BMI and infers weight status from height/weight
- **Multiple Interfaces**: CLI and Flask-based Web UI
- **Food Recommendations**: Intelligent food ranking based on health conditions and preferences
- **Report Generation**: Exports detailed JSON reports with recommendations
- **Real Food Database**: Integration with Open Food Facts API for 200+ food items
- **Indian Food Support**: Curated list of 30+ Indian foods with health metrics

---

## 📁 Project Structure

```
ai project smart diet/
├── LICENSE
├── README.md
├── reports/
│   └── diet_report_loki_20251014_104737.json
├── SmartDietAgent/
│   ├── agent.py                    # Main agent logic and reasoning
│   ├── knowledge_base.py           # FOL rules and food data loading
│   ├── main.py                     # CLI interface
│   ├── web.py                      # Flask web server
│   ├── requirements.txt            # Python dependencies
│   ├── README.md                   # Local documentation
│   ├── __pycache__/                # Python cache
│   ├── data/
│   │   ├── foods.csv              # 238 food items dataset
│   │   └── indian_foods.csv       # 39 curated Indian foods
│   ├── reports/                    # Generated diet reports
│   │   └── diet_report_Loki_20251016_004258.json
│   ├── scripts/
│   │   └── fetch_foods.py         # Food data scraper (Open Food Facts)
│   └── templates/
│       ├── index.html             # Web form template
│       └── results.html           # Results display template
```

---

## 🔧 Dependencies

**File: requirements.txt**
```
Flask>=3.0,<4.0
requests>=2.31,<3.0
```

- **Flask**: Web framework for the UI
- **Requests**: HTTP library for fetching data from Open Food Facts API

---

## 🧠 Core Modules

### 1. **agent.py** - Main Agent Logic

The `SmartDietAgent` class implements the core reasoning and suggestion engine.

```python
from knowledge_base import rules, CATEGORY_PRIORITY, load_foods_csv
import re
import json
import os
from datetime import datetime


class SmartDietAgent:
    def __init__(self, user_profile):
        """
        user_profile: dictionary with keys like
        'name', 'age', 'weight_status', 'health_condition', 'diet_preference'
        """
        self.user_profile = user_profile
        # load foods dataset once per instance (cheap for small CSV)
        self.foods_dataset = None

    # --- BMI utilities ---
    @staticmethod
    def compute_bmi(weight_kg: float, height_cm: float):
        try:
            h_m = float(height_cm) / 100.0
            w = float(weight_kg)
            if h_m <= 0 or w <= 0:
                return None
            return round(w / (h_m * h_m), 1)
        except Exception:
            return None

    @staticmethod
    def infer_weight_status_from_bmi(bmi: float):
        if bmi is None:
            return None
        if bmi < 18.5:
            return "Underweight"
        if bmi < 25:
            return "Normal"
        return "Overweight"

    def infer_diet(self):
        suggestions = []

        # Using First Order Logic style reasoning
        # Example: If user is diabetic -> apply diabetic rules
        condition = self.user_profile.get("health_condition", "Normal")
        weight_status = self.user_profile.get("weight_status", None)
        diet_pref = self.user_profile.get("diet_preference", None)

        # If height/weight provided and weight_status missing, infer from BMI
        if not weight_status:
            weight = self.user_profile.get("weight_kg")
            height = self.user_profile.get("height_cm")
            bmi = self.compute_bmi(weight, height) if (weight and height) else None
            inferred = self.infer_weight_status_from_bmi(bmi)
            if inferred:
                weight_status = inferred
                # persist for downstream calls
                self.user_profile["weight_status"] = inferred
                self.user_profile["bmi"] = bmi

        # Apply health condition rules
        if condition in rules:
            suggestions.extend(rules[condition])

        # Apply weight rules
        if weight_status in rules:
            suggestions.extend(rules[weight_status])

        # Apply diet preference rules (e.g., Vegetarian)
        if diet_pref in rules:
            suggestions.extend(rules[diet_pref])

        # Remove duplicates
        suggestions = sorted(set(suggestions))
        return suggestions

    def infer_diet_with_explanations(self):
        suggestions = []
        source_map = {}

        condition = self.user_profile.get("health_condition", "Normal")
        weight_status = self.user_profile.get("weight_status", None)
        diet_pref = self.user_profile.get("diet_preference", None)

        # BMI-based inference when missing
        if not weight_status:
            weight = self.user_profile.get("weight_kg")
            height = self.user_profile.get("height_cm")
            bmi = self.compute_bmi(weight, height) if (weight and height) else None
            inferred = self.infer_weight_status_from_bmi(bmi)
            if inferred:
                weight_status = inferred
                self.user_profile["weight_status"] = inferred
                self.user_profile["bmi"] = bmi

        if condition in rules:
            for s in rules[condition]:
                suggestions.append(s)
                source_map.setdefault(s, set()).add(condition)

        if weight_status in rules:
            for s in rules[weight_status]:
                suggestions.append(s)
                source_map.setdefault(s, set()).add(weight_status)

        if diet_pref in rules:
            for s in rules[diet_pref]:
                suggestions.append(s)
                source_map.setdefault(s, set()).add(diet_pref)

        suggestions = sorted(set(suggestions))
        explanations = {s: sorted(list(source_map.get(s, []))) for s in suggestions}
        return suggestions, explanations

    def rank_suggestions(self, suggestions, explanations, limit: int | None = None):
        """Rank by highest category priority, then alpha."""
        def score(s):
            cats = explanations.get(s, [])
            return max((CATEGORY_PRIORITY.get(c, 0) for c in cats), default=0)
        ranked = sorted(suggestions, key=lambda s: (-score(s), s))
        if limit is not None:
            return ranked[:limit]
        return ranked

    # --- Food recommendations from dataset ---
    def _get_foods_dataset(self):
        if self.foods_dataset is None:
            # try local data file
            csv_path = os.path.join(os.path.dirname(__file__), "data", "foods.csv")
            self.foods_dataset = load_foods_csv(csv_path)
        return self.foods_dataset or []

    def recommend_foods(self, max_items: int = 6):
        foods = self._get_foods_dataset()
        if not foods:
            return []
        condition = (self.user_profile.get("health_condition") or "Normal")
        diet_pref = (self.user_profile.get("diet_preference") or "Normal")
        weight_status = self.user_profile.get("weight_status")

        # Map weight status to goal
        goal = None
        if weight_status == "Overweight":
            goal = "loss"
        elif weight_status == "Underweight":
            goal = "gain"
        else:
            goal = "maintain"

        # preference toward Indian and global staples; demote brand/barcode-like
        staple_keywords = [
            "idli","dosa","upma","poha","ragi","roti","chapati","paratha","bajra","jowar","khichdi","dal","rajma","chole","curd","yogurt","sambar","rasam","paneer","palak","bhindi","baingan","sprout","oats","brown rice","millet","quinoa","salad","soup","grilled chicken","tandoori","fish","egg","lentil","lentils","whole wheat","wholegrain","bread","bagel"
        ]
        staple_regex = re.compile(r"(" + r"|".join(re.escape(k) for k in staple_keywords) + r")", re.IGNORECASE)
        barcode_like = re.compile(r"^[0-9\s\-()]+$")
        size_like = re.compile(r"\b(\d+\s?(ml|l|cl|g|kg))\b", re.IGNORECASE)

        def score(food):
            name = (food.get("name") or "").strip()
            s = 0
            # health alignment
            if diet_pref == "Vegetarian" and food.get("vegetarian"):
                s += 2
            if condition == "Diabetic" and food.get("diabetic_friendly"):
                s += 3
            if condition == "Hypertension" and food.get("hypertension_friendly"):
                s += 3
            if goal and food.get("weight_goal") == goal:
                s += 2
            # food familiarity boost
            if staple_regex.search(name):
                s += 3
            # demotions for low-quality names
            if barcode_like.match(name):
                s -= 5
            if size_like.search(name):
                s -= 2
            return s

        ranked = sorted(foods, key=lambda f: (-score(f), f.get("name", "")))
        names = [f.get("name") for f in ranked if score(f) > 0]
        # fallback: if strict filter empty, return top general foods
        if not names:
            names = [f.get("name") for f in ranked]
        # final dedupe while preserving order
        seen = set()
        result = []
        for n in names:
            if not n:
                continue
            ln = n.lower()
            if ln in seen:
                continue
            seen.add(ln)
            result.append(n)
            if len(result) >= max_items:
                break
        return result

    def export_report(self, suggestions, explanations, out_dir="reports"):
        os.makedirs(out_dir, exist_ok=True)
        profile = dict(self.user_profile)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = (profile.get("name") or "user").replace(" ", "_")
        path = os.path.join(out_dir, f"diet_report_{name}_{ts}.json")
        ranked = self.rank_suggestions(suggestions, explanations)
        data = {
            "profile": profile,
            "ranked_suggestions": [
                {"suggestion": s, "categories": explanations.get(s, [])}
                for s in ranked
            ],
            "recommended_foods": self.recommend_foods(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path
```

**Key Methods:**
- `compute_bmi()`: Calculates BMI from weight and height
- `infer_weight_status_from_bmi()`: Maps BMI to weight category
- `infer_diet()`: Generates suggestions without explanations
- `infer_diet_with_explanations()`: Generates suggestions with source tracking
- `rank_suggestions()`: Ranks suggestions by priority score
- `recommend_foods()`: Intelligent food ranking based on user profile
- `export_report()`: Exports results to JSON file

---

### 2. **knowledge_base.py** - FOL Rules and Data Loading

Implements the knowledge base with First Order Logic rules and food data utilities.

```python
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
```

**Features:**
- **Rules Dictionary**: 10+ health conditions and preferences with multiple suggestions each
- **Priority Scoring**: Diabetic (100) → Hypertension (95) → Normal (50)
- **Extensibility**: `load_additional_rules()` for custom JSON rule files
- **CSV Parsing**: `load_foods_csv()` handles food data with health attributes

---

### 3. **main.py** - CLI Interface

Command-line interface for running the agent interactively or with arguments.

```python
from agent import SmartDietAgent
import argparse
import sys


def run():
    parser = argparse.ArgumentParser(description="Smart Diet Suggestion Agent")
    parser.add_argument("--name", type=str, help="User name")
    parser.add_argument("--age", type=int, help="Age in years")
    parser.add_argument("--weight_status", type=str, choices=["Underweight", "Overweight", "Normal"], help="Weight status; leave unset to infer via BMI if possible")
    parser.add_argument("--health_condition", type=str, choices=["Diabetic", "Hypertension", "Normal"], help="Health condition")
    parser.add_argument("--diet_preference", type=str, choices=["Vegetarian", "NonVegetarian"], help="Diet preference")
    parser.add_argument("--weight_kg", type=float, help="Weight in kilograms (optional; enables BMI inference)")
    parser.add_argument("--height_cm", type=float, help="Height in centimeters (optional; enables BMI inference)")
    parser.add_argument("--export", action="store_true", help="Export JSON report to ./reports")
    parser.add_argument("--no_input", action="store_true", help="Disable interactive prompts; use CLI args/defaults")
    args, unknown = parser.parse_known_args()

    weight_opts = {"Underweight", "Overweight", "Normal"}
    condition_opts = {"Diabetic", "Hypertension", "Normal"}
    diet_opts = {"Vegetarian", "NonVegetarian"}
    interactive = (not args.no_input) and sys.stdin.isatty()

    if args.name is not None:
        name = args.name
    else:
        name = (input("Name [John]: ").strip() or "John") if interactive else "John"
    while True:
        if args.age is not None:
            age = args.age
            break
        if interactive:
            age_raw = input("Age [30]: ").strip() or "30"
            try:
                age = int(age_raw)
                break
            except ValueError:
                print("Enter a valid integer for age.")
        else:
            age = 30
            break

    if args.weight_status is not None:
        ws = args.weight_status
    else:
        if interactive:
            ws = input("Weight status (Underweight/Overweight/Normal) [Overweight or leave blank to auto]: ").strip()
            if ws == "":
                ws = None  # allow BMI inference
            while ws is not None and ws not in weight_opts:
                print("Choose from Underweight, Overweight, Normal or leave blank to auto.")
                tmp = input("Weight status: ").strip()
                ws = tmp if tmp != "" else None
        else:
            ws = None  # non-interactive: allow BMI inference if weight/height provided

    if args.health_condition is not None:
        cond = args.health_condition
    else:
        if interactive:
            cond = (input("Health condition (Diabetic/Hypertension/Normal) [Diabetic]: ").strip() or "Diabetic")
            while cond not in condition_opts:
                print("Choose from Diabetic, Hypertension, Normal.")
                cond = input("Health condition: ").strip()
        else:
            cond = "Diabetic"

    if args.diet_preference is not None:
        dp = args.diet_preference
    else:
        if interactive:
            dp = (input("Diet preference (Vegetarian/NonVegetarian) [Vegetarian]: ").strip() or "Vegetarian")
            while dp not in diet_opts:
                print("Choose from Vegetarian, NonVegetarian.")
                dp = input("Diet preference: ").strip()
        else:
            dp = "Vegetarian"

    # Optional BMI inputs
    if args.weight_kg is not None or args.height_cm is not None:
        weight_kg = args.weight_kg
        height_cm = args.height_cm
    else:
        if interactive:
            weight_in = input("Weight in kg (optional, enables BMI auto) []: ").strip()
            height_in = input("Height in cm (optional, enables BMI auto) []: ").strip()
            weight_kg = float(weight_in) if weight_in else None
            height_cm = float(height_in) if height_in else None
        else:
            weight_kg = None
            height_cm = None

    user_profile = {
        "name": name,
        "age": age,
        "weight_status": ws,
        "health_condition": cond,
        "diet_preference": dp,
    }
    if weight_kg and height_cm:
        user_profile["weight_kg"] = weight_kg
        user_profile["height_cm"] = height_cm

    agent = SmartDietAgent(user_profile)
    suggestions, explanations = agent.infer_diet_with_explanations()

    # Rank by category priorities
    ranked = agent.rank_suggestions(suggestions, explanations, limit=6)

    print(f"\nDiet Suggestions for {user_profile['name']}:\n")
    for s in ranked:
        cats = ", ".join(explanations.get(s, []))
        print(f"- {s} ({cats})")

    # Show BMI if computed
    bmi = agent.user_profile.get("bmi")
    if bmi is not None:
        print(f"\nBMI inferred: {bmi} → weight status: {agent.user_profile.get('weight_status')}")

    # Also show recommended foods from dataset
    foods = agent.recommend_foods(max_items=6)
    if foods:
        print("\nRecommended foods:")
        for f in foods:
            print(f"- {f}")

    # Optional export
    do_export = args.export
    if do_export or (interactive and (input("\nExport JSON report to ./reports? (y/N): ").strip().lower() == "y")):
        path = agent.export_report(ranked, explanations, out_dir="reports")
        print(f"Report saved to: {path}")


if __name__ == "__main__":
    run()
```

**Features:**
- Interactive prompts with sensible defaults
- Command-line argument support for automation
- BMI inference when weight/height provided
- JSON report export with prompting
- Non-interactive mode for scripting

---

### 4. **web.py** - Flask Web Interface

Flask application serving the web UI with form and results pages.

```python
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
```

**Routes:**
- `GET /`: Renders form page
- `POST /suggest`: Processes form, generates suggestions, renders results

---

### 5. **scripts/fetch_foods.py** - Food Data Scraper

Fetches real food data from Open Food Facts API and merges with curated Indian foods.

```python
import csv
import json
import os
import sys
from typing import Dict, Any, Iterable
import re

import requests


OFF_SEARCH_URL = (
    "https://world.openfoodfacts.org/cgi/search.pl"
)


FIELDS = [
    "product_name",
    "product_name_en",
    "brands",
    "categories_tags",
    "ingredients_tags",
    "ingredients_analysis_tags",
    "nutrition_grades_tags",
    "nutriments",
]


def fetch_off_products(page_size: int = 250, pages: int = 20) -> Iterable[Dict[str, Any]]:
    session = requests.Session()
    # two passes: strict (nutrition-facts-completed) then broad
    strategies = [
        {"label": "en:nutrition-facts-completed"},
        None,
    ]
    for strategy in strategies:
        for page in range(1, pages + 1):
            params = {
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page": page,
                "page_size": page_size,
                "fields": ",".join(FIELDS),
            }
            if strategy and strategy.get("label"):
                params.update({
                    "tagtype_0": "labels",
                    "tag_contains_0": "contains",
                    "tag_0": strategy["label"],
                })
            try:
                resp = session.get(OFF_SEARCH_URL, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                products = data.get("products") or []
                for p in products:
                    yield p
            except Exception:
                continue


def normalize_name(p: Dict[str, Any]) -> str:
    name = (p.get("product_name_en") or p.get("product_name") or "").strip()
    brand = (p.get("brands") or "").split(",")[0].strip()
    if not name:
        return ""
    if brand and brand.lower() not in name.lower():
        return f"{name} ({brand})"
    return name


def to_bool(val) -> bool:
    return bool(val)


def get_bool(field: Any, default: bool = False) -> bool:
    try:
        return bool(field)
    except Exception:
        return default


def extract_flags(p: Dict[str, Any]) -> Dict[str, Any]:
    analysis = set((p.get("ingredients_analysis_tags") or []))
    categories = set((p.get("categories_tags") or []))
    nutr = p.get("nutriments") or {}

    # vegetarian heuristic
    vegetarian = (
        ("en:vegan" in analysis) or ("en:vegetarian" in analysis)
        or not any(t in "|".join(categories) for t in ["meat", "fish", "seafood", "poultry"])
    )

    # numerics
    def num(key: str, default=None):
        try:
            v = nutr.get(key)
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    energy_kcal_100g = num("energy-kcal_100g", num("energy-kcal_serving", None))
    if energy_kcal_100g is None and nutr.get("energy_100g") is not None:
        # convert kJ to kcal approximately
        try:
            energy_kj_100g = float(nutr.get("energy_100g"))
            energy_kcal_100g = round(energy_kj_100g / 4.184, 1)
        except Exception:
            energy_kcal_100g = None
    sugars_100g = num("sugars_100g")
    sodium_100g = num("sodium_100g")
    salt_100g = num("salt_100g")
    fat_100g = num("fat_100g")

    # diabetic friendly heuristic
    diabetic_friendly = False
    if sugars_100g is not None and energy_kcal_100g is not None:
        diabetic_friendly = (sugars_100g <= 5.0 and energy_kcal_100g <= 150)

    # hypertension friendly heuristic
    hypertension_friendly = False
    if sodium_100g is not None:
        hypertension_friendly = sodium_100g <= 0.12  # 120 mg/100g
    elif salt_100g is not None:
        hypertension_friendly = salt_100g <= 0.3  # ~120 mg sodium eq

    # weight goal
    weight_goal = "maintain"
    if energy_kcal_100g is not None and fat_100g is not None:
        if energy_kcal_100g <= 120 and fat_100g <= 5:
            weight_goal = "loss"
        elif energy_kcal_100g >= 250 or fat_100g >= 15:
            weight_goal = "gain"

    return {
        "vegetarian": vegetarian,
        "diabetic_friendly": diabetic_friendly,
        "hypertension_friendly": hypertension_friendly,
        "weight_goal": weight_goal,
    }


EXCLUDE_CATEGORY_TERMS = {
    "en:beverages", "en:waters", "en:water", "en:soft-drinks", "en:sodas",
    "en:teas", "en:coffees"
}

EXCLUDE_NAME_PATTERNS = [
    re.compile(r"^[0-9\s\-()]+$"),  # barcode-like or numeric-only
]

EXCLUDE_NAME_TERMS = {"water", "eau", "mineral water", "aqua", "soda"}


def build_csv(out_path: str, min_rows: int = 200):
    seen = set()
    rows = []
    for p in fetch_off_products(page_size=250, pages=30):
        name = normalize_name(p)
        if not name or name.lower() in seen:
            continue
        # filter out beverages/waters and barcode-like entries
        categories = set((p.get("categories_tags") or []))
        if any(term in categories for term in EXCLUDE_CATEGORY_TERMS):
            continue
        lower_name = name.lower()
        if any(pat.match(name) for pat in EXCLUDE_NAME_PATTERNS):
            continue
        if any(t in lower_name for t in EXCLUDE_NAME_TERMS):
            continue
        # require nutriments present to avoid low-quality rows
        if not p.get("nutriments"):
            continue
        flags = extract_flags(p)
        rows.append({
            "name": name,
            "vegetarian": "true" if flags["vegetarian"] else "false",
            "diabetic_friendly": "true" if flags["diabetic_friendly"] else "false",
            "hypertension_friendly": "true" if flags["hypertension_friendly"] else "false",
            "weight_goal": flags["weight_goal"],
        })
        seen.add(name.lower())
        if len(rows) >= min_rows:
            break

    # Merge curated Indian foods to ensure local relevance
    try:
        root = os.path.dirname(os.path.dirname(__file__))
        curated_path = os.path.join(root, "data", "indian_foods.csv")
        if os.path.exists(curated_path):
            with open(curated_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("name") or "").strip()
                    if not name or name.lower() in seen:
                        continue
                    rows.append({
                        "name": name,
                        "vegetarian": row.get("vegetarian", "true"),
                        "diabetic_friendly": row.get("diabetic_friendly", "false"),
                        "hypertension_friendly": row.get("hypertension_friendly", "false"),
                        "weight_goal": row.get("weight_goal", "maintain"),
                    })
                    seen.add(name.lower())
    except Exception:
        pass

    # Write CSV
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "vegetarian", "diabetic_friendly", "hypertension_friendly", "weight_goal"])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Built CSV with {len(rows)} foods at {out_path}")
```

**Functionality:**
- Fetches from Open Food Facts API in two passes (strict then broad)
- Extracts nutrition data and infers health attributes
- Merges curated Indian foods dataset
- Filters out beverages and low-quality entries
- Generates clean CSV with 200+ foods

---

## 🎨 Templates

### index.html - Input Form

```html
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Smart Diet Agent</title>
    <style>
      :root {
        --red-600: #dc2626;
        --red-700: #b91c1c;
        --red-100: #fee2e2;
        --border: #e5e7eb;
        --muted: #6b7280;
      }
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #fff; color: #111827; }
      .container { max-width: 840px; margin: 0 auto; padding: 2rem 1rem 3rem; }
      .header { display: flex; align-items: center; gap: .75rem; margin-bottom: 1rem; }
      .badge { background: var(--red-100); color: var(--red-700); font-weight: 700; padding: .25rem .5rem; border-radius: 6px; font-size: .85rem; }
      h1 { margin: 0; font-size: 1.75rem; color: var(--red-700); }
      p.lead { margin: .25rem 0 1.25rem; color: var(--muted); }
      .card { padding: 1.5rem; border: 1px solid var(--border); border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,.04); background: #fff; }
      .section-title { margin: 1rem 0 .5rem; font-size: 1rem; color: var(--red-700); }
      label { display: block; margin-top: .5rem; font-weight: 600; }
      .hint { display: block; font-weight: 400; color: var(--muted); font-size: .85rem; margin-top: .125rem; }
      input, select { width: 100%; padding: .625rem .75rem; margin-top: .25rem; border: 1px solid #d1d5db; border-radius: 8px; }
      .grid { display: grid; gap: 1rem; }
      .grid-2 { grid-template-columns: 1fr 1fr; }
      .actions { display: flex; gap: .75rem; margin-top: 1.25rem; }
      button { background: var(--red-700); color: white; padding: .75rem 1rem; border: 0; border-radius: 8px; cursor: pointer; font-weight: 600; }
      button:hover { background: var(--red-600); }
      .note { margin-top: .75rem; color: var(--muted); font-size: .9rem; }
      @media (max-width: 640px) { .grid-2 { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="header">
        <span class="badge">Diet Agent</span>
        <h1>Personalized diet suggestions</h1>
      </div>
      <p class="lead">Enter a few details. We'll infer BMI-weight status if you provide weight and height, and tailor suggestions and foods accordingly.</p>

      <div class="card">
        <form method="post" action="/suggest">
          <div class="section">
            <div class="section-title">Profile</div>
            <div class="grid grid-2">
              <div>
                <label for="name">Name
                  <input id="name" type="text" name="name" placeholder="John" />
                  <span class="hint">Used in the report and results.</span>
                </label>
              </div>
              <div>
                <label for="age">Age
                  <input id="age" type="number" name="age" placeholder="30" min="1" />
                  <span class="hint">Years</span>
                </label>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-title">Health & preferences</div>
            <div class="grid grid-2">
              <div>
                <label for="health_condition">Health Condition
                  <select id="health_condition" name="health_condition">
                    {% for o in condition_opts %}
                    <option value="{{ o }}">{{ o }}</option>
                    {% endfor %}
                  </select>
                  <span class="hint">Impacts rule priority (e.g., Diabetic, Hypertension).</span>
                </label>
              </div>
              <div>
                <label for="diet_preference">Diet Preference
                  <select id="diet_preference" name="diet_preference">
                    {% for o in diet_opts %}
                    <option value="{{ o }}">{{ o }}</option>
                    {% endfor %}
                  </select>
                  <span class="hint">Choose Vegetarian or NonVegetarian to tune foods and rules.</span>
                </label>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-title">Weight details (optional)</div>
            <div class="grid grid-2">
              <div>
                <label for="weight_status">Weight Status
                  <select id="weight_status" name="weight_status">
                    <option value="">Auto (via BMI)</option>
                    {% for o in weight_opts %}
                    <option value="{{ o }}">{{ o }}</option>
                    {% endfor %}
                  </select>
                  <span class="hint">Leave blank to infer from BMI if weight & height are provided.</span>
                </label>
              </div>
              <div></div>
            </div>
            <div class="grid grid-2">
              <div>
                <label for="weight_kg">Weight (kg)
                  <input id="weight_kg" type="number" step="any" min="0" inputmode="decimal" name="weight_kg" placeholder="92" />
                </label>
              </div>
              <div>
                <label for="height_cm">Height (cm)
                  <input id="height_cm" type="number" step="any" min="0" inputmode="decimal" name="height_cm" placeholder="172" />
                </label>
              </div>
            </div>
            <div class="note">We never store your inputs on the server. They're used only to compute suggestions in-memory.</div>
          </div>

          <div class="actions">
            <button type="submit">Get suggestions</button>
          </div>
        </form>
      </div>
    </div>
  </body>
</html>
```

### results.html - Results Display

```html
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Diet Suggestions</title>
    <style>
      :root {
        --red-600: #dc2626;
        --red-700: #b91c1c;
        --red-100: #fee2e2;
        --border: #e5e7eb;
        --muted: #6b7280;
      }
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #fff; color: #111827; }
      .container { max-width: 840px; margin: 0 auto; padding: 2rem 1rem 3rem; }
      .title { display: flex; align-items: baseline; gap: .5rem; color: var(--red-700); }
      .card { padding: 1.5rem; border: 1px solid var(--border); border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,.04); background: #fff; }
      .muted { color: var(--muted); }
      h2 { margin: .25rem 0 1rem; color: var(--red-700); }
      h3 { margin-top: 1.25rem; color: var(--red-700); }
      ul { padding-left: 1.25rem; }
      .badge { background: var(--red-100); color: var(--red-700); font-weight: 700; padding: .25rem .5rem; border-radius: 6px; font-size: .85rem; }
      a.button { display: inline-block; margin-top: 1rem; background: var(--red-700); color: white; padding: .5rem .75rem; border-radius: 8px; text-decoration: none; font-weight: 600; }
      a.button:hover { background: var(--red-600); }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="title">
        <span class="badge">Diet Agent</span>
        <h2>Diet suggestions for {{ name }}</h2>
      </div>
      <div class="card">
        {% if bmi %}
          <p class="muted">BMI inferred: {{ bmi }}{% if inferred_weight_status %} → weight status: {{ inferred_weight_status }}{% endif %}</p>
        {% endif %}

        <h3>Rule-based suggestions (top 6)</h3>
        <ul>
        {% for s in ranked %}
          <li>
            {{ s }}
            {% set cats = explanations.get(s, []) %}
            {% if cats and cats|length %}
              <span class="muted"> ({{ ", ".join(cats) }})</span>
            {% endif %}
          </li>
        {% endfor %}
        </ul>

        {% if recommended_foods and recommended_foods|length %}
          <h3>Recommended foods (top 6)</h3>
          <ul>
          {% for f in recommended_foods %}
            <li>{{ f }}</li>
          {% endfor %}
          </ul>
        {% endif %}

        <a class="button" href="/">Back</a>
      </div>
    </div>
  </body>
</html>
```

---

## 📊 Data Files

### foods.csv (238 rows)

Sample entries showing the food dataset structure:

| name | vegetarian | diabetic_friendly | hypertension_friendly | weight_goal |
|------|------------|-------------------|----------------------|-------------|
| Perly (Jaouda) | true | false | false | loss |
| Lait (Jaouda) | true | true | true | loss |
| Fromage blanc nature | true | true | true | maintain |
| Yaourt nature | true | true | true | loss |
| Brown Rice | true | true | true | maintain |

### indian_foods.csv (39 rows)

Curated Indian foods with health attributes:

| name | vegetarian | diabetic_friendly | hypertension_friendly | weight_goal |
|------|------------|-------------------|----------------------|-------------|
| Idli | true | true | true | loss |
| Dosa | true | true | true | maintain |
| Upma | true | true | true | maintain |
| Roti (Whole Wheat) | true | true | true | maintain |
| Dal Tadka | true | true | true | maintain |
| Paneer Tikka | true | true | true | maintain |
| Rasam | true | true | true | loss |

---

## 🚀 Usage Guide

### Installation

```bash
# Install dependencies
pip install -r SmartDietAgent/requirements.txt
```

### CLI Usage (Interactive)

```bash
# Run interactive mode
python SmartDietAgent/main.py

# With arguments (non-interactive)
python SmartDietAgent/main.py \
  --name Loki \
  --age 30 \
  --health_condition Diabetic \
  --diet_preference Vegetarian \
  --weight_kg 92 \
  --height_cm 172 \
  --export \
  --no_input
```

### Web UI

```bash
# Start Flask server
python SmartDietAgent/web.py

# Visit http://127.0.0.1:5000 in browser
```

### Generate Food Database

```bash
# Download 200+ foods from Open Food Facts
python SmartDietAgent/scripts/fetch_foods.py
```

---

## 🔍 How It Works

### 1. **User Profile Input**
- Collects: name, age, health condition, diet preference
- Optional: weight (kg) and height (cm) for BMI calculation

### 2. **BMI Inference**
- If weight + height provided: BMI = weight / (height/100)²
- Maps BMI to weight status: <18.5 (Underweight), 18.5-25 (Normal), >25 (Overweight)

### 3. **Rule Application (FOL-style)**
```
IF health_condition = "Diabetic" THEN suggest all Diabetic rules
IF weight_status = "Overweight" THEN suggest all Overweight rules
IF diet_preference = "Vegetarian" THEN suggest all Vegetarian rules
```

### 4. **Suggestion Ranking**
- Score by category priority: Diabetic (100) > Hypertension (95) > Normal (50)
- Break ties alphabetically
- Return top 6 ranked suggestions

### 5. **Food Recommendation**
- Load foods from CSV dataset
- Score each food by:
  - Health alignment (diabetic/hypertension friendly): +3
  - Diet preference match (vegetarian): +2
  - Weight goal match: +2
  - Staple familiarity: +3
  - Penalties for low-quality names: -5
- Return top 6 unique foods with score > 0

### 6. **Report Export**
JSON structure:
```json
{
  "profile": { "name": "Loki", "age": 30, ... },
  "ranked_suggestions": [
    { "suggestion": "Avoid sugar", "categories": ["Diabetic"] },
    ...
  ],
  "recommended_foods": ["Idli", "Rasam", "Dal Tadka", ...]
}
```

---

## 📈 Example Output

### CLI Output
```
Diet Suggestions for Loki:

- Avoid sugar (Diabetic)
- Prefer low-glycemic index foods (Diabetic)
- Include whole grains (Diabetic)
- Limit sugary beverages (Overweight)
- Prefer high-fiber, low-calorie density foods (Overweight)
- Low-calorie diet (Overweight)

BMI inferred: 31.2 → weight status: Overweight

Recommended foods:
- Idli
- Dosa
- Rasam
- Upma
- Roti (Whole Wheat)
- Brown Rice

Report saved to: reports/diet_report_Loki_20251016_004258.json
```

### JSON Report
```json
{
  "profile": {
    "name": "Loki",
    "age": 30,
    "weight_status": "Overweight",
    "health_condition": "Diabetic",
    "diet_preference": "Vegetarian",
    "weight_kg": 92,
    "height_cm": 172,
    "bmi": 31.2
  },
  "ranked_suggestions": [
    {
      "suggestion": "Avoid sugar",
      "categories": ["Diabetic"]
    },
    {
      "suggestion": "Prefer low-glycemic index foods",
      "categories": ["Diabetic"]
    }
  ],
  "recommended_foods": [
    "Idli",
    "Dosa",
    "Rasam",
    "Upma"
  ]
}
```

---

## 🎯 Key Algorithms

### BMI Calculation
$$BMI = \frac{weight_{kg}}{(height_{cm}/100)^2}$$

### Food Scoring
$$score(food) = \sum_{attributes} weights \times conditions$$

Where conditions are:
- Vegetarian match: +2
- Diabetic friendly: +3
- Hypertension friendly: +3
- Weight goal match: +2
- Staple keyword: +3
- Quality penalties: -2 to -5

### Ranking Function
```
rank = (-priority_score, alphabetical_order)
```

---

## 🔐 Privacy & Security

- **No data storage**: User inputs only used in-memory
- **No tracking**: No cookies or user tracking
- **Open Food Facts**: Uses public API only
- **Local CSV**: Can run fully offline with provided datasets

---

## 🎓 Educational Value

This project demonstrates:
1. **Knowledge Representation**: FOL-style rules in Python
2. **Inference Engines**: Rule-based reasoning
3. **Web Development**: Flask with form handling
4. **Data Processing**: CSV parsing and filtering
5. **API Integration**: Fetching from Open Food Facts
6. **UI/UX**: Form design with responsive layout
7. **Software Architecture**: Separation of concerns (agent, KB, web)

---

## 📝 License

MIT License (see LICENSE file)

---

## 🤝 Contributing

The codebase is extensible:
- Add new health conditions to `rules` in `knowledge_base.py`
- Extend food dataset with `fetch_foods.py`
- Customize rankings in `agent.py`'s `score()` function
- Load custom rules via `load_additional_rules(json_path)`

---

**Last Updated:** January 30, 2026
**Status:** Production Ready
**Python Version:** 3.8+
