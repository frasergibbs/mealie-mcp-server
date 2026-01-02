"""Main MCP server entry point for Mealie integration."""

import os
import sys
from typing import Any

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
from mealie_mcp.tools.recipes_write import (
    add_recipe_note,
    create_recipe,
    delete_recipe,
    get_recipe_timeline,
    import_recipe_from_url,
    mark_recipe_made,
    update_recipe,
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
You can search recipes, view details, create/edit recipes, manage meal plans, and work with shopping lists.

RECIPE MANAGEMENT:
- Use search_recipes to find recipes by name, tags, or categories
- Use get_recipe to get full details including ingredients and instructions
- Use create_recipe to add new recipes with full structured data (ingredients, instructions, nutrition)
- Use update_recipe to modify existing recipes
- Use import_recipe_from_url to import from websites with good schema.org markup
- Use delete_recipe to remove recipes

COOKING TRACKING:
- Use mark_recipe_made when someone cooks a recipe (updates last-made timestamp)
- Use add_recipe_note to record cooking notes, modifications, or observations
- Use get_recipe_timeline to see a recipe's history

MEAL PLANNING:
- Use get_meal_plan to see what's planned for a date range
- Use create_meal_plan_entry to add recipes to the meal plan
- Use delete_meal_plan_entry to remove from meal plan

SHOPPING:
- Use get_shopping_list to see current items
- Use add_to_shopping_list to add ingredients or items
- Use clear_checked_items to clean up purchased items

When parsing recipes from text, images, or URLs for create_recipe, structure the data carefully:
- Extract quantities, units, and food names from ingredient text
- Number instructions sequentially
- Estimate nutrition per serving when not provided (calories, protein, carbs, fat)""",
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


# Register recipe write tools
@mcp.tool()
async def tool_create_recipe(
    name: str,
    description: str | None = None,
    ingredients: list[dict[str, Any]] | None = None,
    instructions: list[dict[str, Any]] | None = None,
    nutrition: dict[str, str] | None = None,
    prep_time: str | None = None,
    cook_time: str | None = None,
    total_time: str | None = None,
    recipe_yield: str | None = None,
    tags: list[str] | None = None,
    categories: list[str] | None = None,
    source_url: str | None = None,
) -> dict:
    """Create a new recipe with full structured data.

    Claude can parse recipes from any source (text, images, URLs, verbal descriptions)
    and provide structured data for this tool.

    Args:
        name: Recipe name (required)
        description: Brief description of the dish
        ingredients: List of ingredient objects with display, quantity, unit, food, note
        instructions: List of instruction objects with text and optional title
        nutrition: Nutrition per serving (calories, proteinContent, carbohydrateContent, etc.)
        prep_time: Preparation time (e.g., "15 minutes")
        cook_time: Cooking time (e.g., "30 minutes")
        total_time: Total time (e.g., "45 minutes")
        recipe_yield: Serving size (e.g., "4 servings")
        tags: List of tag names to apply
        categories: List of category names to apply
        source_url: Original recipe URL if imported from web

    Returns:
        Created recipe details with slug for future reference
    """
    return await create_recipe(
        name=name,
        description=description,
        ingredients=ingredients,
        instructions=instructions,
        nutrition=nutrition,
        prep_time=prep_time,
        cook_time=cook_time,
        total_time=total_time,
        recipe_yield=recipe_yield,
        tags=tags,
        categories=categories,
        source_url=source_url,
    )


@mcp.tool()
async def tool_update_recipe(
    slug: str,
    name: str | None = None,
    description: str | None = None,
    ingredients: list[dict[str, Any]] | None = None,
    instructions: list[dict[str, Any]] | None = None,
    nutrition: dict[str, str] | None = None,
    prep_time: str | None = None,
    cook_time: str | None = None,
    total_time: str | None = None,
    recipe_yield: str | None = None,
    tags: list[str] | None = None,
    categories: list[str] | None = None,
    rating: int | None = None,
) -> dict:
    """Update an existing recipe.

    Args:
        slug: Recipe slug or ID (required)
        name: New recipe name
        description: Updated description
        ingredients: Complete ingredient list (replaces existing)
        instructions: Complete instruction list (replaces existing)
        nutrition: Updated nutrition info
        prep_time: New preparation time
        cook_time: New cooking time
        total_time: New total time
        recipe_yield: New serving size
        tags: New tag list (replaces existing)
        categories: New category list (replaces existing)
        rating: Recipe rating (1-5)

    Returns:
        Updated recipe details
    """
    return await update_recipe(
        slug=slug,
        name=name,
        description=description,
        ingredients=ingredients,
        instructions=instructions,
        nutrition=nutrition,
        prep_time=prep_time,
        cook_time=cook_time,
        total_time=total_time,
        recipe_yield=recipe_yield,
        tags=tags,
        categories=categories,
        rating=rating,
    )


@mcp.tool()
async def tool_delete_recipe(slug: str) -> dict:
    """Delete a recipe from the database.

    Args:
        slug: Recipe slug or ID

    Returns:
        Deletion status
    """
    return await delete_recipe(slug)


@mcp.tool()
async def tool_import_recipe_from_url(url: str, include_tags: bool = False) -> dict:
    """Import a recipe from a URL using Mealie's built-in scraper.

    Use this for sites with good structured data. For sites without good markup,
    have Claude parse the page and use create_recipe instead.

    Args:
        url: Recipe URL to import
        include_tags: Whether to import tags from the source site

    Returns:
        Created recipe details with slug
    """
    return await import_recipe_from_url(url, include_tags)


@mcp.tool()
async def tool_mark_recipe_made(
    slug: str,
    timestamp: str | None = None,
    notes: str | None = None,
) -> dict:
    """Mark a recipe as made, updating its last-made timestamp.

    This tracks cooking history and can optionally add notes about the session.

    Args:
        slug: Recipe slug or ID
        timestamp: When made (ISO format, defaults to now)
        notes: Optional cooking notes (modifications, results, etc.)

    Returns:
        Confirmation with updated timestamp
    """
    return await mark_recipe_made(slug, timestamp, notes)


@mcp.tool()
async def tool_add_recipe_note(
    slug: str,
    subject: str,
    message: str | None = None,
    event_type: str = "comment",
) -> dict:
    """Add a note or comment to a recipe's timeline.

    Use to record cooking notes, modifications, substitutions, or observations.

    Args:
        slug: Recipe slug or ID
        subject: Note title/subject
        message: Detailed note content
        event_type: Type - "comment" (default), "info", or "system"

    Returns:
        Created timeline event details
    """
    return await add_recipe_note(slug, subject, message, event_type)


@mcp.tool()
async def tool_get_recipe_timeline(slug: str, limit: int = 20) -> list[dict] | dict:
    """Get the timeline/history of a recipe.

    Shows when made, notes, modifications, and other events.

    Args:
        slug: Recipe slug or ID
        limit: Maximum number of events to return

    Returns:
        List of timeline events
    """
    return await get_recipe_timeline(slug, limit)


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
