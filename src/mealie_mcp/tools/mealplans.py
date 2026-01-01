"""Meal planning MCP tools."""

from mealie_mcp.client import get_client
from mealie_mcp.models import ErrorResponse, MealType


async def get_meal_plan(start_date: str, end_date: str) -> list[dict] | dict:
    """Retrieve meal plan for a date range.

    Args:
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)

    Returns:
        List of meal plan entries with date, meal type, and recipe details
    """
    client = get_client()
    result = await client.get_meal_plan(start_date, end_date)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    entries = []
    for entry in result:
        entry_data = {
            "id": entry.id,
            "date": entry.date.isoformat(),
            "meal_type": entry.entry_type.value,
        }

        if entry.recipe:
            entry_data["recipe"] = {
                "id": entry.recipe.id,
                "slug": entry.recipe.slug,
                "name": entry.recipe.name,
                "description": entry.recipe.description,
            }
        elif entry.title:
            entry_data["title"] = entry.title
            entry_data["text"] = entry.text

        entries.append(entry_data)

    return entries


async def create_meal_plan_entry(
    date: str,
    recipe_slug: str,
    meal_type: str = "dinner",
) -> dict:
    """Add a recipe to the meal plan.

    Args:
        date: Date for the meal in ISO format (YYYY-MM-DD)
        recipe_slug: Recipe slug or ID to plan
        meal_type: Type of meal - one of: breakfast, lunch, dinner, side, snack (default: dinner)

    Returns:
        Created meal plan entry with id and details
    """
    # Validate meal type
    valid_types = [mt.value for mt in MealType]
    if meal_type not in valid_types:
        return {
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": f"Invalid meal_type '{meal_type}'. Must be one of: {', '.join(valid_types)}",
        }

    client = get_client()
    result = await client.create_meal_plan_entry(date, recipe_slug, meal_type)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    entry_data = {
        "id": result.id,
        "date": result.date.isoformat(),
        "meal_type": result.entry_type.value,
        "recipe_id": result.recipe_id,
    }

    if result.recipe:
        entry_data["recipe"] = {
            "name": result.recipe.name,
            "slug": result.recipe.slug,
        }

    return entry_data


async def delete_meal_plan_entry(entry_id: str) -> dict:
    """Remove an entry from the meal plan.

    Args:
        entry_id: Meal plan entry ID to delete

    Returns:
        Success status with confirmation message
    """
    client = get_client()
    result = await client.delete_meal_plan_entry(entry_id)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return result
