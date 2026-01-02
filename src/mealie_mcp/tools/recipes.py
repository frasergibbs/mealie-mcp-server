"""Recipe-related MCP tools."""

import json
import re
from typing import Any

import httpx

from mealie_mcp.client import get_client
from mealie_mcp.models import ErrorResponse


# Known recipe sources with their URL patterns
RECIPE_SOURCES = {
    "hellofresh": {
        "search_url": "https://www.hellofresh.com.au/recipes/{slug}",
        "base_domain": "hellofresh.com",
    },
    "marleyspoon": {
        "search_url": "https://marleyspoon.com.au/menu/{slug}",
        "base_domain": "marleyspoon.com",
    },
    "dinnerly": {
        "search_url": "https://dinnerly.com.au/recipes/{slug}",
        "base_domain": "dinnerly.com",
    },
}


async def search_recipes(
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
    client = get_client()
    result = await client.search_recipes(
        query=query,
        tags=tags,
        categories=categories,
        per_page=limit,
    )

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return [
        {
            "id": r.id,
            "slug": r.slug,
            "name": r.name,
            "description": r.description,
            "tags": [t.name for t in r.tags],
            "categories": [c.name for c in r.recipe_category],
            "total_time": r.total_time,
            "rating": r.rating,
        }
        for r in result
    ]


async def get_recipe(slug: str) -> dict:
    """Get full recipe details including ingredients and instructions.

    Args:
        slug: Recipe slug or ID (e.g., "spaghetti-carbonara")

    Returns:
        Complete recipe with ingredients, instructions, nutrition, prep time, etc.
    """
    client = get_client()
    result = await client.get_recipe(slug)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    # Format ingredients for readability
    ingredients = []
    for ing in result.recipe_ingredient:
        parts = []
        if ing.quantity:
            parts.append(str(ing.quantity))
        if ing.unit:
            parts.append(ing.unit)
        if ing.food:
            parts.append(ing.food)
        if ing.note:
            parts.append(f"({ing.note})")

        ingredient_str = " ".join(parts) if parts else ing.display or ing.original_text or ""
        if ingredient_str:
            ingredients.append(ingredient_str)

    # Format instructions
    instructions = []
    for i, inst in enumerate(result.recipe_instructions, 1):
        step = {"step": i, "text": inst.text}
        if inst.title:
            step["title"] = inst.title
        instructions.append(step)

    return {
        "id": result.id,
        "slug": result.slug,
        "name": result.name,
        "description": result.description,
        "yield": result.recipe_yield,
        "prep_time": result.prep_time,
        "cook_time": result.cook_time,
        "total_time": result.total_time,
        "tags": [t.name for t in result.tags],
        "categories": [c.name for c in result.recipe_category],
        "ingredients": ingredients,
        "instructions": instructions,
        "nutrition": result.nutrition.model_dump() if result.nutrition else None,
        "rating": result.rating,
        "source_url": result.org_url,
    }


async def list_tags() -> list[dict] | dict:
    """Get all available tags for filtering recipes.

    Returns:
        List of tag objects with id, slug, and name
    """
    client = get_client()
    result = await client.list_tags()

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return [{"id": t.id, "slug": t.slug, "name": t.name} for t in result]


async def list_categories() -> list[dict] | dict:
    """Get all available categories for filtering recipes.

    Returns:
        List of category objects with id, slug, and name
    """
    client = get_client()
    result = await client.list_categories()

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return [{"id": c.id, "slug": c.slug, "name": c.name} for c in result]


def _slugify_recipe_name(name: str) -> str:
    """Convert a recipe name to a URL-friendly slug."""
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _extract_json_ld(html: str) -> dict[str, Any] | None:
    """Extract schema.org JSON-LD recipe data from HTML."""
    # Find all JSON-LD script blocks
    pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

    for match in matches:
        try:
            data = json.loads(match.strip())

            # Handle @graph structure
            if isinstance(data, dict) and "@graph" in data:
                for item in data["@graph"]:
                    if isinstance(item, dict) and item.get("@type") == "Recipe":
                        return item

            # Direct Recipe type
            if isinstance(data, dict) and data.get("@type") == "Recipe":
                return data

            # Array of items
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "Recipe":
                        return item
        except json.JSONDecodeError:
            continue

    return None


def _parse_json_ld_recipe(data: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON-LD recipe data into our format."""
    # Extract ingredients
    ingredients = []
    raw_ingredients = data.get("recipeIngredient", [])
    if isinstance(raw_ingredients, list):
        ingredients = [str(ing) for ing in raw_ingredients if ing]

    # Extract instructions
    instructions = []
    raw_instructions = data.get("recipeInstructions", [])
    if isinstance(raw_instructions, list):
        for i, inst in enumerate(raw_instructions, 1):
            if isinstance(inst, str):
                instructions.append({"step": i, "text": inst})
            elif isinstance(inst, dict):
                text = inst.get("text", inst.get("name", ""))
                if text:
                    instructions.append({"step": i, "text": text})

    # Extract nutrition
    nutrition = {}
    raw_nutrition = data.get("nutrition", {})
    if isinstance(raw_nutrition, dict):
        nutrition = {
            "calories": raw_nutrition.get("calories"),
            "proteinContent": raw_nutrition.get("proteinContent"),
            "carbohydrateContent": raw_nutrition.get("carbohydrateContent"),
            "fatContent": raw_nutrition.get("fatContent"),
            "fiberContent": raw_nutrition.get("fiberContent"),
            "sodiumContent": raw_nutrition.get("sodiumContent"),
            "sugarContent": raw_nutrition.get("sugarContent"),
        }

    # Extract image
    image_url = None
    raw_image = data.get("image")
    if isinstance(raw_image, str):
        image_url = raw_image
    elif isinstance(raw_image, list) and raw_image:
        image_url = raw_image[0] if isinstance(raw_image[0], str) else raw_image[0].get("url")
    elif isinstance(raw_image, dict):
        image_url = raw_image.get("url")

    return {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "ingredients": ingredients,
        "instructions": instructions,
        "prep_time": data.get("prepTime"),
        "cook_time": data.get("cookTime"),
        "total_time": data.get("totalTime"),
        "recipe_yield": data.get("recipeYield"),
        "nutrition": nutrition if any(nutrition.values()) else None,
        "image_url": image_url,
        "source_url": data.get("url") or data.get("mainEntityOfPage"),
    }


async def lookup_recipe_online(
    recipe_name: str,
    source: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Look up a recipe online from known sources like HelloFresh.

    Use this when you recognize a recipe from a meal kit card to find the
    complete online version with nutrition data and photos.

    IMPORTANT: The returned ingredients may still contain proprietary
    measurements like "1 packet spice blend". You MUST transform these
    to standard measurements before calling create_recipe.

    Args:
        recipe_name: The recipe name (e.g., "Chipotle Beef Chilli Bowls")
        source: Source provider - "hellofresh", "marleyspoon", "dinnerly", or None for direct URL
        url: Direct URL to the recipe page (if known)

    Returns:
        Structured recipe data - transform ingredients before passing to create_recipe
    """
    try:
        # If direct URL provided, use it
        if url:
            fetch_url = url
        elif source and source.lower() in RECIPE_SOURCES:
            # Build URL from source and recipe name
            src = RECIPE_SOURCES[source.lower()]
            slug = _slugify_recipe_name(recipe_name)
            fetch_url = src["search_url"].format(slug=slug)
        else:
            return {
                "error": True,
                "message": f"Unknown source '{source}'. Supported: hellofresh, marleyspoon, dinnerly. Or provide a direct URL.",
            }

        # Fetch the page
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MealieBot/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as client:
            response = await client.get(fetch_url)

            if response.status_code == 404:
                return {
                    "error": True,
                    "message": f"Recipe not found at {fetch_url}. Try a different URL or search manually.",
                    "tried_url": fetch_url,
                }

            response.raise_for_status()
            html = response.text

        # Extract JSON-LD structured data
        recipe_data = _extract_json_ld(html)

        if not recipe_data:
            return {
                "error": True,
                "message": "No structured recipe data found on page. The page may not have schema.org markup.",
                "tried_url": fetch_url,
            }

        result = _parse_json_ld_recipe(recipe_data)
        result["source_url"] = fetch_url
        result["found"] = True

        return result

    except httpx.TimeoutException:
        return {"error": True, "message": f"Timeout fetching {fetch_url}"}
    except httpx.HTTPStatusError as e:
        return {"error": True, "message": f"HTTP error {e.response.status_code} fetching recipe"}
    except Exception as e:
        return {"error": True, "message": f"Error looking up recipe: {str(e)}"}

