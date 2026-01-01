"""Main MCP server entry point for Mealie integration."""

import os
import sys

from dotenv import load_dotenv
from fastmcp import FastMCP

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

# Load environment variables
load_dotenv()

# Create the MCP server
mcp = FastMCP(
    name="mealie",
    instructions="""You are connected to a personal Mealie recipe library.
You can search recipes, view full recipe details, manage meal plans, and work with shopping lists.

When helping with meal planning:
- Use search_recipes to find suitable recipes based on ingredients, tags, or categories
- Use get_recipe to get full details including ingredients and instructions
- Use create_meal_plan_entry to add recipes to the meal plan
- Use get_meal_plan to see what's already planned

For shopping:
- Use get_shopping_list to see current items
- Use add_to_shopping_list to add ingredients or items
- Use clear_checked_items to clean up purchased items""",
)


# Register recipe tools
@mcp.tool()
async def tool_search_recipes(
    query: str | None = None,
    tags: list[str] | None = None,
    categories: list[str] | None = None,
    limit: int = 20,
) -> list[dict] | dict:
    """Search the recipe library with optional filters.

    Args:
        query: Text search term to find recipes by name or description
        tags: Filter by tag slugs (e.g., ["quick", "vegetarian"])
        categories: Filter by category slugs (e.g., ["dinner", "desserts"])
        limit: Maximum number of results to return (default 20)

    Returns:
        List of recipe summaries with id, slug, name, description, tags, and timing info
    """
    return await search_recipes(query, tags, categories, limit)


@mcp.tool()
async def tool_get_recipe(slug: str) -> dict:
    """Get full recipe details including ingredients and instructions.

    Args:
        slug: Recipe slug or ID (e.g., "spaghetti-carbonara")

    Returns:
        Complete recipe with ingredients, instructions, nutrition, prep time, etc.
    """
    return await get_recipe(slug)


@mcp.tool()
async def tool_list_tags() -> list[dict] | dict:
    """Get all available tags for filtering recipes.

    Returns:
        List of tag objects with id, slug, and name
    """
    return await list_tags()


@mcp.tool()
async def tool_list_categories() -> list[dict] | dict:
    """Get all available categories for filtering recipes.

    Returns:
        List of category objects with id, slug, and name
    """
    return await list_categories()


# Register meal plan tools
@mcp.tool()
async def tool_get_meal_plan(start_date: str, end_date: str) -> list[dict] | dict:
    """Retrieve meal plan for a date range.

    Args:
        start_date: Start date in ISO format (YYYY-MM-DD)
        end_date: End date in ISO format (YYYY-MM-DD)

    Returns:
        List of meal plan entries with date, meal type, and recipe details
    """
    return await get_meal_plan(start_date, end_date)


@mcp.tool()
async def tool_create_meal_plan_entry(
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
    return await create_meal_plan_entry(date, recipe_slug, meal_type)


@mcp.tool()
async def tool_delete_meal_plan_entry(entry_id: str) -> dict:
    """Remove an entry from the meal plan.

    Args:
        entry_id: Meal plan entry ID to delete

    Returns:
        Success status with confirmation message
    """
    return await delete_meal_plan_entry(entry_id)


# Register shopping list tools
@mcp.tool()
async def tool_get_shopping_lists() -> list[dict] | dict:
    """Get all shopping lists.

    Returns:
        List of shopping list summaries with id and name
    """
    return await get_shopping_lists()


@mcp.tool()
async def tool_get_shopping_list(list_id: str | None = None) -> dict:
    """Get items from a specific shopping list.

    Args:
        list_id: Shopping list ID. If not provided, uses the first available list.

    Returns:
        Shopping list with all items including their checked status
    """
    return await get_shopping_list(list_id)


@mcp.tool()
async def tool_add_to_shopping_list(
    items: list[str],
    list_id: str | None = None,
) -> dict:
    """Add items to a shopping list.

    Args:
        items: List of item descriptions to add (e.g., ["2 cups flour", "1 dozen eggs"])
        list_id: Target shopping list ID. If not provided, uses the first available list.

    Returns:
        Summary of added items with the updated list info
    """
    return await add_to_shopping_list(items, list_id)


@mcp.tool()
async def tool_clear_checked_items(list_id: str | None = None) -> dict:
    """Remove all checked items from a shopping list.

    Args:
        list_id: Shopping list ID. If not provided, uses the first available list.

    Returns:
        Summary of removed items count
    """
    return await clear_checked_items(list_id)


def main():
    """Run the MCP server."""
    # Validate required environment variables
    if not os.getenv("MEALIE_URL"):
        print("Warning: MEALIE_URL not set, using default http://localhost:9000/api", file=sys.stderr)

    if not os.getenv("MEALIE_TOKEN"):
        print("Error: MEALIE_TOKEN environment variable is required", file=sys.stderr)
        sys.exit(1)

    # Run the server
    # For stdio transport (Claude Desktop), just run directly
    # For SSE transport (remote), use: mcp.run(transport="sse", host="0.0.0.0", port=8080)
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "sse":
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8080"))
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
