"""MCP tools for Mealie integration."""

from mealie_mcp.tools.mealplans import (
    create_meal_plan_entry,
    delete_meal_plan_entry,
    get_meal_plan,
)
from mealie_mcp.tools.recipes import (
    get_recipe,
    list_categories,
    list_tags,
    search_recipes,
)
from mealie_mcp.tools.shopping import (
    add_to_shopping_list,
    clear_checked_items,
    get_shopping_list,
    get_shopping_lists,
)

__all__ = [
    # Recipes
    "search_recipes",
    "get_recipe",
    "list_tags",
    "list_categories",
    # Meal Plans
    "get_meal_plan",
    "create_meal_plan_entry",
    "delete_meal_plan_entry",
    # Shopping
    "get_shopping_lists",
    "get_shopping_list",
    "add_to_shopping_list",
    "clear_checked_items",
]
