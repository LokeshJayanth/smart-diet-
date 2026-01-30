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
