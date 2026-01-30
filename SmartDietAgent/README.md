# Smart Diet Suggestion Agent

A simple knowledge-based agent that provides diet suggestions using FOL-style rules.

## Project Structure
```
SmartDietAgent/
├── knowledge_base.py   # Stores all rules
├── agent.py            # Main agent code (reasoning & suggestions)
├── main.py             # Run this to start the agent
└── README.md           # Project info
```

## Run (Interactive CLI)
- Ensure you have Python 3.8+
- From the parent folder, you can run directly via relative path:
```
py -3 .\SmartDietAgent\main.py
```
- Or `cd` into `SmartDietAgent/` and run:
```
py -3 main.py
```

You will be prompted for name, age, weight status, health condition, and diet preference. Suggestions are printed in a deterministic order and annotated with the rule categories that triggered them.

## Customize
You can still hardcode a profile in `main.py` if preferred. Valid options include:
- `weight_status`: `Underweight` | `Overweight` | `Normal`
- `health_condition`: `Diabetic` | `Hypertension` | `Normal`
- `diet_preference`: `Vegetarian` | `Normal`

## Web UI

### Install
```
py -3 -m pip install -r .\SmartDietAgent\requirements.txt
```

### Run the server
```
py -3 .\SmartDietAgent\web.py
```

Open `http://127.0.0.1:5000/` in your browser. Fill the form and submit to view ranked diet suggestions. BMI-based weight status will be inferred automatically if weight and height are provided.

## Datasets and extended recommendations

- Built-in rules expanded in `knowledge_base.py`.
- Optional datasets:
  - `data/foods.csv` with simple nutrition-friendly flags.
  - You can extend rules via a JSON file using `load_additional_rules(path)` structure: `{ "Category": ["Rule 1", "Rule 2"] }`.

### Build a 200+ foods.csv from Open Food Facts
```
py -3 -m pip install -r .\SmartDietAgent\requirements.txt
py -3 .\SmartDietAgent\scripts\fetch_foods.py
```
This script downloads real product records from Open Food Facts (public dataset) and converts them into the schema:
`name,vegetarian,diabetic_friendly,hypertension_friendly,weight_goal`

### Where foods are used
- CLI and Web outputs now show a "Recommended foods" section ranked by:
  - diet preference match (vegetarian)
  - diabetic/hypertension friendliness based on selected condition
  - weight goal inferred from weight status (loss/gain/maintain)
