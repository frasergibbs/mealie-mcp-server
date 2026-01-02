"""Recipe-related MCP tools."""

from mealie_mcp.client import get_client
from mealie_mcp.models import ErrorResponse


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
