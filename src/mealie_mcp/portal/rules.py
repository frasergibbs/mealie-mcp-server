"""Meal planning rules storage and retrieval."""

import json
import os
from pathlib import Path

DEFAULT_RULES = """\
## Master Requirements
- Meal plan must meet macronutrient and calorie requirements for Fraser
- Requirements should be adjustable for each day of the planning week

## Breakfast
- Monday - Friday breakfast should always be basic (not requiring extensive preparation)
- Breakfast repetition is acceptable Monday - Friday

## Lunches
- Monday - Friday lunches need to be meal prepped on Sundays
- Lunches must be meals that keep well throughout the week

## Dinner
- Protein repetition should be avoided on consecutive days (e.g., if chicken breast was cooked today, tomorrow's dinner should not be chicken breast)
- Mondays and Tuesdays should be easy-to-cook meals:
  - Maximum 20 minutes preparation time
  - Simple or pre-prepped ingredients (pre-cut veggies, pre-marinated proteins)
  - Minimal dishes/cleanup required
- User should be prompted for takeout days (default: Thursday and Friday nights)
"""

DEFAULT_MACROS = {
    "monday": {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70},
    "tuesday": {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70},
    "wednesday": {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70},
    "thursday": {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70},
    "friday": {"calories": 2000, "protein": 150, "carbs": 200, "fat": 70},
    "saturday": {"calories": 2200, "protein": 150, "carbs": 250, "fat": 80},
    "sunday": {"calories": 2200, "protein": 150, "carbs": 250, "fat": 80},
}


def _get_data_path() -> Path:
    """Get the path to the rules data file."""
    data_dir = Path(os.getenv("RULES_DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "meal_planning_rules.json"


def _load_data() -> dict:
    """Load rules data from file or return defaults."""
    path = _get_data_path()
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"rules": DEFAULT_RULES, "macros": DEFAULT_MACROS}


def _save_data(data: dict) -> None:
    """Save rules data to file."""
    path = _get_data_path()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_rules() -> str:
    """Get the current meal planning rules."""
    return _load_data().get("rules", DEFAULT_RULES)


def set_rules(rules: str) -> None:
    """Update the meal planning rules."""
    data = _load_data()
    data["rules"] = rules
    _save_data(data)


def get_macros() -> dict:
    """Get the per-day macronutrient requirements."""
    return _load_data().get("macros", DEFAULT_MACROS)


def set_macros(macros: dict) -> None:
    """Update the per-day macronutrient requirements."""
    data = _load_data()
    data["macros"] = macros
    _save_data(data)


def get_all() -> dict:
    """Get all meal planning configuration."""
    return _load_data()
