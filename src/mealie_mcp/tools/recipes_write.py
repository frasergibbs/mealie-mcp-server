"""Recipe write/modification MCP tools."""

import re
import uuid
from datetime import datetime
from typing import Any

from mealie_mcp.client import get_client
from mealie_mcp.models import ErrorResponse, TimelineEventType


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug.

    Args:
        text: Text to slugify

    Returns:
        Lowercase hyphenated slug
    """
    # Convert to lowercase
    slug = text.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove non-alphanumeric characters except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Remove consecutive hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    return slug


async def create_recipe(
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
        ingredients: List of ingredient objects, each with:
            - display: Full ingredient text (e.g., "2 cups all-purpose flour")
            - quantity: Numeric amount (e.g., 2.0)
            - unit: Unit of measure (e.g., "cups")
            - food: Ingredient name (e.g., "all-purpose flour")
            - note: Additional notes (e.g., "sifted")
        instructions: List of instruction objects, each with:
            - text: Instruction text (required)
            - title: Optional section header (e.g., "For the sauce")
        nutrition: Nutrition info per serving with keys:
            - calories, proteinContent, carbohydrateContent, fatContent
            - fiberContent, sodiumContent, sugarContent, cholesterolContent
            - saturatedFatContent, transFatContent, unsaturatedFatContent
        prep_time: Preparation time (e.g., "15 minutes" or "PT15M")
        cook_time: Cooking time (e.g., "30 minutes" or "PT30M")
        total_time: Total time (e.g., "45 minutes" or "PT45M")
        recipe_yield: Serving size (e.g., "4 servings")
        tags: List of tag names to apply
        categories: List of category names to apply
        source_url: Original recipe URL if imported from web

    Returns:
        Created recipe details with slug for future reference
    """
    client = get_client()

    # First create the recipe with just the name
    result = await client.create_recipe(name)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    slug = result

    # Build update payload with all the additional data
    update_data: dict[str, Any] = {}

    if description:
        update_data["description"] = description

    if ingredients:
        # Format ingredients for Mealie API
        formatted_ingredients = []
        for ing in ingredients:
            ingredient = {
                "referenceId": str(uuid.uuid4()),  # Required by Mealie
                "display": ing.get("display", ""),
                "originalText": ing.get("display", ing.get("originalText", "")),
            }
            if "quantity" in ing and ing["quantity"] is not None:
                ingredient["quantity"] = float(ing["quantity"])
            if "unit" in ing and ing["unit"]:
                ingredient["unit"] = {"name": ing["unit"]}
            if "food" in ing and ing["food"]:
                ingredient["food"] = {"name": ing["food"]}
            if "note" in ing and ing["note"]:
                ingredient["note"] = ing["note"]
            formatted_ingredients.append(ingredient)
        update_data["recipeIngredient"] = formatted_ingredients

    if instructions:
        # Format instructions for Mealie API
        formatted_instructions = []
        for inst in instructions:
            instruction = {
                "id": str(uuid.uuid4()),  # Required by Mealie
                "text": inst.get("text", ""),
                "ingredientReferences": [],  # Required by Mealie
            }
            if "title" in inst and inst["title"]:
                instruction["title"] = inst["title"]
            formatted_instructions.append(instruction)
        update_data["recipeInstructions"] = formatted_instructions

    if nutrition:
        update_data["nutrition"] = nutrition

    if prep_time:
        update_data["prepTime"] = prep_time

    if cook_time:
        update_data["cookTime"] = cook_time

    if total_time:
        update_data["totalTime"] = total_time

    if recipe_yield:
        update_data["recipeYield"] = recipe_yield

    if tags:
        # Tags need both name and slug
        update_data["tags"] = [{"name": t, "slug": _slugify(t)} for t in tags]

    if categories:
        # Categories need both name and slug
        update_data["recipeCategory"] = [{"name": c, "slug": _slugify(c)} for c in categories]

    if source_url:
        update_data["orgURL"] = source_url

    # Update the recipe with all the data
    if update_data:
        update_result = await client.update_recipe(slug, update_data)
        if isinstance(update_result, ErrorResponse):
            return {
                "success": True,
                "slug": slug,
                "warning": f"Recipe created but update failed: {update_result.message}",
            }

    return {
        "success": True,
        "slug": slug,
        "name": name,
        "message": f"Recipe '{name}' created successfully",
    }


async def update_recipe(
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

    Claude can help modify recipes - scaling servings, substituting ingredients,
    adjusting cooking times, or adding missing nutrition data.

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
    client = get_client()

    update_data: dict[str, Any] = {}

    if name:
        update_data["name"] = name

    if description:
        update_data["description"] = description

    if ingredients:
        formatted_ingredients = []
        for ing in ingredients:
            ingredient = {
                "referenceId": str(uuid.uuid4()),  # Required by Mealie
                "display": ing.get("display", ""),
                "originalText": ing.get("display", ing.get("originalText", "")),
            }
            if "quantity" in ing and ing["quantity"] is not None:
                ingredient["quantity"] = float(ing["quantity"])
            if "unit" in ing and ing["unit"]:
                ingredient["unit"] = {"name": ing["unit"]}
            if "food" in ing and ing["food"]:
                ingredient["food"] = {"name": ing["food"]}
            if "note" in ing and ing["note"]:
                ingredient["note"] = ing["note"]
            formatted_ingredients.append(ingredient)
        update_data["recipeIngredient"] = formatted_ingredients

    if instructions:
        formatted_instructions = []
        for inst in instructions:
            instruction = {
                "id": str(uuid.uuid4()),  # Required by Mealie
                "text": inst.get("text", ""),
                "ingredientReferences": [],  # Required by Mealie
            }
            if "title" in inst and inst["title"]:
                instruction["title"] = inst["title"]
            formatted_instructions.append(instruction)
        update_data["recipeInstructions"] = formatted_instructions

    if nutrition:
        update_data["nutrition"] = nutrition

    if prep_time:
        update_data["prepTime"] = prep_time

    if cook_time:
        update_data["cookTime"] = cook_time

    if total_time:
        update_data["totalTime"] = total_time

    if recipe_yield:
        update_data["recipeYield"] = recipe_yield

    if tags:
        update_data["tags"] = [{"name": t, "slug": _slugify(t)} for t in tags]

    if categories:
        update_data["recipeCategory"] = [{"name": c, "slug": _slugify(c)} for c in categories]

    if rating is not None:
        update_data["rating"] = rating

    if not update_data:
        return ErrorResponse.validation_error("No update data provided").model_dump()

    result = await client.update_recipe(slug, update_data)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return {
        "success": True,
        "slug": result.slug,
        "name": result.name,
        "message": f"Recipe '{result.name}' updated successfully",
    }


async def delete_recipe(slug: str) -> dict:
    """Delete a recipe from the database.

    Args:
        slug: Recipe slug or ID

    Returns:
        Deletion status
    """
    client = get_client()
    result = await client.delete_recipe(slug)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return result


async def import_recipe_from_url(url: str, include_tags: bool = False) -> dict:
    """Import a recipe from a URL using Mealie's built-in scraper.

    Use this for sites with good structured data (schema.org markup).
    For sites without good markup, use create_recipe with Claude-parsed data instead.

    Args:
        url: Recipe URL to import
        include_tags: Whether to import tags from the source site

    Returns:
        Created recipe details with slug
    """
    client = get_client()
    result = await client.import_recipe_from_url(url, include_tags)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    # Get the full recipe to return details
    recipe = await client.get_recipe(result)
    if isinstance(recipe, ErrorResponse):
        return {
            "success": True,
            "slug": result,
            "message": f"Recipe imported from {url}",
        }

    return {
        "success": True,
        "slug": result,
        "name": recipe.name,
        "description": recipe.description,
        "source_url": url,
        "message": f"Recipe '{recipe.name}' imported successfully",
    }


async def mark_recipe_made(
    slug: str,
    timestamp: str | None = None,
    notes: str | None = None,
) -> dict:
    """Mark a recipe as made, updating its last-made timestamp and optionally adding notes.

    This is useful for tracking cooking history and can trigger integrations
    (e.g., logging to MacroFactor, updating Grocy inventory).

    Args:
        slug: Recipe slug or ID
        timestamp: When the recipe was made (ISO format, defaults to now)
        notes: Optional notes about this cooking session (modifications, results, etc.)

    Returns:
        Confirmation with updated timestamp
    """
    client = get_client()

    # Parse timestamp or use now
    if timestamp:
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return ErrorResponse.validation_error(
                f"Invalid timestamp format: {timestamp}"
            ).model_dump()
    else:
        ts = datetime.now()

    # Update last made timestamp
    result = await client.update_recipe_last_made(slug, ts)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    # If notes provided, add a timeline event
    if notes:
        # First get the recipe to get its ID
        recipe = await client.get_recipe(slug)
        if isinstance(recipe, ErrorResponse):
            return {
                **result,
                "warning": "Recipe marked as made but couldn't add notes (recipe not found)",
            }

        event_result = await client.create_timeline_event(
            recipe_id=recipe.id,
            subject="Made this recipe",
            event_type=TimelineEventType.COMMENT,
            event_message=notes,
            timestamp=ts,
        )

        if isinstance(event_result, ErrorResponse):
            return {
                **result,
                "warning": f"Recipe marked as made but notes failed: {event_result.message}",
            }

        return {
            **result,
            "notes_added": True,
            "timeline_event_id": event_result.id,
        }

    return result


async def add_recipe_note(
    slug: str,
    subject: str,
    message: str | None = None,
    event_type: str = "comment",
) -> dict:
    """Add a note or comment to a recipe's timeline.

    Use this to record cooking notes, modifications, substitutions,
    or any other information about a recipe.

    Args:
        slug: Recipe slug or ID
        subject: Note title/subject
        message: Detailed note content
        event_type: Type of note - "comment" (default), "info", or "system"

    Returns:
        Created timeline event details
    """
    client = get_client()

    # Get the recipe to get its ID
    recipe = await client.get_recipe(slug)
    if isinstance(recipe, ErrorResponse):
        return recipe.model_dump()

    # Map event type string to enum
    type_map = {
        "comment": TimelineEventType.COMMENT,
        "info": TimelineEventType.INFO,
        "system": TimelineEventType.SYSTEM,
    }
    evt_type = type_map.get(event_type.lower(), TimelineEventType.COMMENT)

    result = await client.create_timeline_event(
        recipe_id=recipe.id,
        subject=subject,
        event_type=evt_type,
        event_message=message,
    )

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return {
        "success": True,
        "event_id": result.id,
        "recipe": recipe.name,
        "subject": subject,
        "message": f"Note added to '{recipe.name}'",
    }


async def get_recipe_timeline(slug: str, limit: int = 20) -> list[dict] | dict:
    """Get the timeline/history of a recipe.

    Shows when the recipe was made, notes, modifications, and other events.

    Args:
        slug: Recipe slug or ID
        limit: Maximum number of events to return

    Returns:
        List of timeline events
    """
    client = get_client()

    # Get the recipe to get its ID
    recipe = await client.get_recipe(slug)
    if isinstance(recipe, ErrorResponse):
        return recipe.model_dump()

    result = await client.get_recipe_timeline(recipe.id, per_page=limit)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return [
        {
            "id": event.id,
            "subject": event.subject,
            "type": event.event_type.value,
            "message": event.event_message,
            "timestamp": event.timestamp.isoformat(),
        }
        for event in result
    ]
