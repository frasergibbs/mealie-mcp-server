"""Main MCP server entry point for Mealie integration."""

import os
import sys
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.auth import ClientRegistrationOptions
from fastmcp.server.auth.providers.in_memory import InMemoryOAuthProvider

from mealie_mcp.tools.mealplans import (
    create_meal_plan_entry,
    delete_meal_plan_entry,
    get_meal_plan,
)
from mealie_mcp.tools.planning_rules import get_meal_planning_rules
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
    upload_recipe_image,
)
from mealie_mcp.tools.shopping import (
    add_to_shopping_list,
    clear_checked_items,
    get_shopping_list,
    get_shopping_lists,
)

# Load environment variables
load_dotenv()

# Set up OAuth provider if authentication is required
auth_provider = None
if os.getenv("MCP_REQUIRE_AUTH", "false").lower() == "true":
    base_url = os.getenv("MCP_BASE_URL")
    if not base_url:
        print("Error: MCP_BASE_URL required when MCP_REQUIRE_AUTH=true", file=sys.stderr)
        print("Example: MCP_BASE_URL=https://rainworth-server.tailbf31d9.ts.net", file=sys.stderr)
        sys.exit(1)
    
    auth_provider = InMemoryOAuthProvider(
        base_url=base_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,  # Enable Dynamic Client Registration for Claude
            valid_scopes=["mcp"],  # Define available scopes
        ),
    )
    print(f"OAuth enabled with Dynamic Client Registration at {base_url}", file=sys.stderr)

# Create the MCP server
mcp = FastMCP(
    name="mealie",
    auth=auth_provider,  # Pass auth provider to FastMCP
    instructions="""You are connected to a personal Mealie recipe library.
You can search recipes, view details, create/edit recipes, manage meal plans, and work with shopping lists.

## WHEN USER PROVIDES A RECIPE URL

ALWAYS use import_recipe_from_url FIRST. This:
- Uses Mealie's reliable scraper to get all data
- Downloads and saves the recipe image automatically
- Extracts nutrition if available

### WORKFLOW:
1. Call import_recipe_from_url(url)
2. If response has requires_update=true, call update_recipe to fix:
   - Transform proprietary measurements ("1 packet" → "2 tbsp")
   - Add missing nutrition (estimate if needed)
3. Done! Image is already saved by the scraper.

## WHEN USER HAS NO URL (e.g., recipe card image)

Use create_recipe directly, but you MUST:
- Transform all proprietary measurements first
- Estimate and include nutrition data
- Then call upload_recipe_image if photo available

## TOOLS REFERENCE

**Recipe Import & Creation:**
- import_recipe_from_url: PREFERRED for URLs - scrapes data + image
- create_recipe: For manual entry from images/cards
- update_recipe: Fix imported recipes (ingredients, nutrition)
- upload_recipe_image: Add photo (only needed for manual creation)
- delete_recipe: Remove recipes

**Recipe Search:**
- search_recipes: Find by name, tags, or categories
- get_recipe: Get full details with ingredients/instructions
- list_tags, list_categories: Get available filters

**Cooking Tracking:**
- mark_recipe_made: Record when cooked
- add_recipe_note: Add cooking notes
- get_recipe_timeline: View history

**Meal Planning:**
- get_meal_plan: View planned meals
- create_meal_plan_entry: Add to meal plan
- delete_meal_plan_entry: Remove from plan
- get_meal_planning_rules: Get configured rules and macro requirements (ALWAYS call this before generating a meal plan)

**Shopping:**
- get_shopping_list, get_shopping_lists: View items
- add_to_shopping_list: Add ingredients
- clear_checked_items: Remove purchased""",
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


@mcp.tool()
async def tool_get_meal_planning_rules() -> dict:
    """Get the configured meal planning rules and daily macro requirements.

    IMPORTANT: Always call this BEFORE generating a meal plan to get the current
    constraints that must be followed.

    Returns:
        Dictionary with:
        - rules: Markdown text with meal planning rules (breakfast, lunch, dinner constraints)
        - macros: Per-day macronutrient targets (calories, protein, carbs, fat for each day)
    """
    return await get_meal_planning_rules()


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


@mcp.tool()
async def tool_upload_recipe_image(
    slug: str,
    image_base64: str,
    extension: str = "jpg",
) -> dict:
    """Upload an image for a recipe.

    Call this after create_recipe to add a photo of the finished dish.

    IMPORTANT - Image Selection:
    - Use the FINAL PLATED DISH photo, not raw ingredients
    - Crop to focus on food presentation
    - If extracting from PDF, select the hero/beauty shot

    Args:
        slug: Recipe slug (from create_recipe response)
        image_base64: Base64-encoded image data (can include data URI prefix)
        extension: Format - "jpg" (recommended), "png", or "webp"

    Returns:
        Upload confirmation
    """
    return await upload_recipe_image(slug, image_base64, extension)


def main():
    """Run the MCP server with support for multiple transports.
    
    Transports:
    - stdio: Local subprocess communication (Claude Desktop) - DEFAULT
    - http: HTTP transport with FastMCP's built-in OAuth 2.1 + DCR (Claude.ai)
    """
    # Validate required environment variables
    if not os.getenv("MEALIE_URL"):
        print("Warning: MEALIE_URL not set, using default http://localhost:9000/api", file=sys.stderr)

    if not os.getenv("MEALIE_TOKEN"):
        print("Error: MEALIE_TOKEN environment variable is required", file=sys.stderr)
        sys.exit(1)

    # Determine transport from environment
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        # Modern HTTP transport with FastMCP's built-in OAuth 2.1
        import uvicorn
        
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8080"))
        
        print(f"Starting HTTP server on {host}:{port}", file=sys.stderr)
        if mcp.auth:
            print("OAuth: enabled with Dynamic Client Registration (DCR)", file=sys.stderr)
        else:
            print("OAuth: disabled (DEVELOPMENT ONLY)", file=sys.stderr)
        
        # Create ASGI app at /mcp path
        # When adding to Claude.ai, use full URL: https://rainworth-server.tailbf31d9.ts.net/mcp
        app = mcp.http_app(path="/mcp")
        
        # Run with uvicorn
        uvicorn.run(app, host=host, port=port)
        
    elif transport == "streamable-http" or transport == "sse":
        # Deprecated transports - guide to use 'http' instead
        print(f"Error: '{transport}' transport is deprecated", file=sys.stderr)
        print("Use MCP_TRANSPORT=http with FastMCP's built-in OAuth support", file=sys.stderr)
        print("FastMCP now includes OAuth 2.1 with Dynamic Client Registration", file=sys.stderr)
        sys.exit(1)
        
    else:
        # stdio transport for Claude Desktop (default)
        print("Running in stdio mode for Claude Desktop", file=sys.stderr)
        mcp.run()


if __name__ == "__main__":
    main()
