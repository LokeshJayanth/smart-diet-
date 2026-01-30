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
        print(f"\nBMI inferred: {bmi} -> weight status: {agent.user_profile.get('weight_status')}")

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
