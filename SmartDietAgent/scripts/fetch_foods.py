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
                        "vegetarian": str(row.get("vegetarian", "")).strip().lower(),
                        "diabetic_friendly": str(row.get("diabetic_friendly", "")).strip().lower(),
                        "hypertension_friendly": str(row.get("hypertension_friendly", "")).strip().lower(),
                        "weight_goal": str(row.get("weight_goal", "")).strip().lower(),
                    })
                    seen.add(name.lower())
    except Exception:
        pass

    if len(rows) < min_rows:
        print(f"Warning: only collected {len(rows)} items after merging curated foods.")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "name",
                "vegetarian",
                "diabetic_friendly",
                "hypertension_friendly",
                "weight_goal",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")


def main():
    root = os.path.dirname(os.path.dirname(__file__))
    out_path = os.path.join(root, "data", "foods.csv")
    build_csv(out_path, min_rows=200)


if __name__ == "__main__":
    main()


