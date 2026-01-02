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

    IMPORTANT: Before calling this tool, apply AI intelligence to transform the recipe:

    ## Ingredient Processing Rules

    1. **Proprietary Measurements → Standard Units**:
       Convert meal-kit measurements to standard cooking units:
       - "1 packet spice blend" → estimate based on typical amounts (e.g., "2 tbsp" or "15g")
       - "1 sachet paste" → typically 20-30g, or "1-2 tbsp"
       - "1 packet cheese" → weigh estimate (e.g., "100g shredded cheese")
       - "1 tin" → specify size (e.g., "400g tin crushed tomatoes")
       Use your knowledge of typical meal-kit portions (HelloFresh, Marley Spoon, etc.)

    2. **Proprietary Blends → Component Ingredients**:
       Expand branded spice blends to their likely components:
       - "Southwest spice blend" → "1 tsp cumin, 1 tsp paprika, ½ tsp chili powder,
         ½ tsp garlic powder, ½ tsp onion powder, pinch cayenne"
       - "Italian seasoning" → "1 tsp dried oregano, 1 tsp dried basil, ½ tsp thyme"
       - "Tuscan spice mix" → "1 tsp rosemary, 1 tsp thyme, ½ tsp oregano, garlic"
       Research the specific brand/source if known for accurate substitutions.

    3. **Vague Quantities → Specific Amounts**:
       - "salt to taste" → keep as-is (this is acceptable)
       - "olive oil for cooking" → "2 tbsp olive oil" (estimate based on method)
       - "a knob of butter" → "1 tbsp butter"

    ## Instruction Enhancement

    - Add section titles where logical (Prep, Cook, Sauce, Assembly, etc.)
    - Ensure temperatures include units (180°C / 350°F)
    - Clarify timing where vague

    ## Nutrition Data (REQUIRED)

    ALWAYS include nutrition data. If not provided by source, ESTIMATE based on ingredients:

    **Required fields (per serving):**
    - calories: Total kcal (e.g., "520 kcal")
    - proteinContent: Grams of protein (e.g., "35g")
    - carbohydrateContent: Total carbs in grams (e.g., "45g")
    - fatContent: Total fat in grams (e.g., "22g")

    **Recommended fields:**
    - fiberContent: Dietary fiber (e.g., "6g")
    - sodiumContent: Sodium in mg (e.g., "800mg")
    - sugarContent: Total sugars (e.g., "8g")
    - saturatedFatContent: Saturated fat (e.g., "8g")

    **Estimation Guidelines:**
    - Protein: Chicken breast ~31g/100g, beef mince ~20g/100g, tofu ~8g/100g
    - Carbs: Rice ~28g/100g cooked, pasta ~25g/100g cooked, potato ~17g/100g
    - Fat: Olive oil ~100%, butter ~81%, cheese ~25-35%
    - Estimate per serving based on portions in recipe_yield

    Example nutrition dict:
    {
        "calories": "520 kcal",
        "proteinContent": "35g",
        "carbohydrateContent": "45g",
        "fatContent": "22g",
        "fiberContent": "6g",
        "sodiumContent": "800mg",
        "sugarContent": "5g"
    }

    ## After Creation

    If an image is available, call upload_recipe_image with the food photo.
    Crop/focus on the final plated dish, not raw ingredients.

    Args:
        name: Recipe name (required)
        description: Brief appetizing description of the dish
        ingredients: List of ingredient objects with 'display' text.
                     Apply the transformation rules above before passing.
        instructions: List with 'text' and optional 'title' for sections
        nutrition: Per-serving nutrition dict (REQUIRED - estimate if not provided).
                   Keys: calories, proteinContent, carbohydrateContent, fatContent,
                   fiberContent, sodiumContent, sugarContent, saturatedFatContent
        prep_time: Preparation time (e.g., "15 minutes")
        cook_time: Cooking time (e.g., "30 minutes")
        total_time: Total time (e.g., "45 minutes")
        recipe_yield: Servings (e.g., "4 servings")
        tags: Tags like cuisine type, dietary info, source
        categories: Categories like protein type (Beef, Chicken, Vegetarian)
        source_url: Original recipe URL if applicable

    Returns:
        Created recipe with slug for subsequent image upload
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
        # Mealie uses 'note' field to display ingredient text in the UI
        formatted_ingredients = []
        for ing in ingredients:
            display_text = ing.get("display", "")
            ingredient = {
                "referenceId": str(uuid.uuid4()),  # Required by Mealie
                "display": display_text,
                "note": ing.get("note", display_text),  # UI displays from 'note'
            }
            if "quantity" in ing and ing["quantity"] is not None:
                ingredient["quantity"] = float(ing["quantity"])
            if "unit" in ing and ing["unit"]:
                ingredient["unit"] = {"name": ing["unit"]}
            if "food" in ing and ing["food"]:
                ingredient["food"] = {"name": ing["food"]}
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

    if tags or categories:
        # Mealie requires groupId for tags and categories
        group_id = await client.get_group_id()

    if tags:
        # Tags need name, slug, and groupId
        update_data["tags"] = [
            {"name": t, "slug": _slugify(t), "groupId": group_id} for t in tags
        ]

    if categories:
        # Categories need name, slug, and groupId
        update_data["recipeCategory"] = [
            {"name": c, "slug": _slugify(c), "groupId": group_id} for c in categories
        ]

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
        # Format ingredients for Mealie API
        # Mealie uses 'note' field to display ingredient text in the UI
        formatted_ingredients = []
        for ing in ingredients:
            display_text = ing.get("display", "")
            ingredient = {
                "referenceId": str(uuid.uuid4()),  # Required by Mealie
                "display": display_text,
                "note": ing.get("note", display_text),  # UI displays from 'note'
            }
            if "quantity" in ing and ing["quantity"] is not None:
                ingredient["quantity"] = float(ing["quantity"])
            if "unit" in ing and ing["unit"]:
                ingredient["unit"] = {"name": ing["unit"]}
            if "food" in ing and ing["food"]:
                ingredient["food"] = {"name": ing["food"]}
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

    if tags or categories:
        # Mealie requires groupId for tags and categories
        group_id = await client.get_group_id()

    if tags:
        update_data["tags"] = [
            {"name": t, "slug": _slugify(t), "groupId": group_id} for t in tags
        ]

    if categories:
        update_data["recipeCategory"] = [
            {"name": c, "slug": _slugify(c), "groupId": group_id} for c in categories
        ]

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


async def upload_recipe_image(
    slug: str,
    image_base64: str,
    extension: str = "jpg",
) -> dict:
    """Upload an image for a recipe.

    Use this after creating a recipe to add a photo of the finished dish.

    ## Image Selection Guidelines

    When extracting images from PDFs or recipe cards:
    - Select the FINAL PLATED DISH photo, not raw ingredients
    - Crop to focus on the food presentation
    - Prefer landscape orientation for recipe cards
    - If multiple images exist, choose the most appetizing hero shot

    ## Supported Formats

    - JPEG (jpg) - recommended for photos
    - PNG (png) - for graphics with transparency
    - WebP (webp) - modern format, good compression

    Args:
        slug: Recipe slug (returned from create_recipe)
        image_base64: Base64-encoded image data.
                      Can include data URI prefix (data:image/jpeg;base64,...)
                      or be raw base64 string.
        extension: Image format - "jpg", "png", or "webp"

    Returns:
        Upload confirmation with image URL
    """
    client = get_client()

    result = await client.upload_recipe_image_from_base64(slug, image_base64, extension)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return {
        "success": True,
        "slug": slug,
        "message": f"Image uploaded for recipe '{slug}'",
        "image": result.get("image"),
    }
