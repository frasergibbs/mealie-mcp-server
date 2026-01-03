"""Phase 3: Apply intelligent tags and categories to recipes."""

import json
import os
from typing import Any

import anthropic

# Model for tagging
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 8192

# Valid tags per category
VALID_TAGS = {
    # Primary proteins
    "proteins": ["beef", "chicken", "pork", "lamb", "seafood", "vegetarian"],
    
    # Protein sub-types
    "beef_subtypes": ["steak", "mince", "rump", "sirloin", "brisket", "ribs"],
    "chicken_subtypes": ["breast", "thigh", "drumstick", "schnitzel", "tenders", "wings"],
    "pork_subtypes": ["chops", "mince", "tenderloin", "bacon", "sausage", "belly"],
    "lamb_subtypes": ["cutlets", "mince", "leg", "shoulder", "chops"],
    "seafood_subtypes": ["fish", "prawns", "salmon", "barramundi", "tuna", "cod", "snapper"],
    "vegetarian_subtypes": ["tofu", "halloumi", "legumes", "tempeh", "eggs"],
    
    # Cuisines
    "cuisines": [
        "mexican", "italian", "asian", "indian", "mediterranean",
        "american", "greek", "thai", "chinese", "japanese",
        "korean", "vietnamese", "middle-eastern", "french", "spanish",
        "south-american", "australian", "british",
    ],
    
    # Effort levels
    "effort": ["quick-easy", "moderate", "involved"],
    
    # Meal prep suitability
    "meal_prep": ["meal-prep-friendly", "freezer-friendly", "keeps-well"],
    
    # Dietary tags
    "dietary": ["low-carb", "high-protein", "dairy-free", "gluten-free"],
}

# Valid categories
VALID_CATEGORIES = {
    "source": ["HelloFresh"],
    "meal_type": ["Dinner", "Lunch", "Meal Prep"],
}


def _build_tagging_prompt(recipes: list[dict]) -> str:
    """Build prompt for tagging and categorization.
    
    Args:
        recipes: List of recipe dicts to tag
        
    Returns:
        Formatted prompt string
    """
    prompt = """You are categorizing recipes for a meal planning system.

## Categories (assign exactly 2 per recipe)

1. **Source category** (always): `HelloFresh`
2. **Meal type** (choose one):
   - `Dinner` - Standard evening meals
   - `Lunch` - Lighter meals, good for midday
   - `Meal Prep` - Recipes specifically designed for batch cooking

## Tags (assign all that apply)

### Primary Protein (choose one)
`beef`, `chicken`, `pork`, `lamb`, `seafood`, `vegetarian`

### Protein Sub-type (choose one matching primary)
- Beef: `steak`, `mince`, `rump`, `sirloin`, `brisket`, `ribs`
- Chicken: `breast`, `thigh`, `drumstick`, `schnitzel`, `tenders`, `wings`
- Pork: `chops`, `mince`, `tenderloin`, `bacon`, `sausage`, `belly`
- Lamb: `cutlets`, `mince`, `leg`, `shoulder`, `chops`
- Seafood: `fish`, `prawns`, `salmon`, `barramundi`, `tuna`, `cod`, `snapper`
- Vegetarian: `tofu`, `halloumi`, `legumes`, `tempeh`, `eggs`

### Cuisine (choose one or two)
`mexican`, `italian`, `asian`, `indian`, `mediterranean`, `american`, `greek`, 
`thai`, `chinese`, `japanese`, `korean`, `vietnamese`, `middle-eastern`, 
`french`, `spanish`, `south-american`, `australian`, `british`

### Effort Level (choose one)
- `quick-easy`: Prep + cook ≤ 25 min, ≤ 8 instruction steps, simple techniques
- `moderate`: 25-45 min total, standard home cooking complexity
- `involved`: 45+ min or complex techniques (marinating, multiple components)

### Meal Prep Suitability (if applicable)
- `meal-prep-friendly`: Good for Sunday batch cooking, reheats well
- `freezer-friendly`: Can be frozen and reheated
- `keeps-well`: Stays fresh in fridge for 3-5 days

### Dietary (if applicable)
- `high-protein`: 30g+ protein per serving
- `low-carb`: Under 30g carbs per serving
- `dairy-free`: No dairy products
- `gluten-free`: No gluten-containing ingredients

## Output Format

Return a JSON array using the EXACT recipe index number provided:
```json
[
  {
    "index": 1,
    "categories": ["HelloFresh", "Dinner"],
    "tags": ["chicken", "breast", "asian", "chinese", "quick-easy", "meal-prep-friendly", "high-protein"]
  }
]
```

IMPORTANT: Use the recipe index number (1, 2, 3, etc.) - do NOT include or modify slugs.

## Recipes to Tag

"""
    
    for i, recipe in enumerate(recipes, 1):
        prompt += f"\n### Recipe {i} (index={i}): {recipe.get('name', 'Unknown')}\n"
        
        # Include timing info
        prep_time = recipe.get("prepTime", "")
        cook_time = recipe.get("cookTime", "")
        total_time = recipe.get("totalTime", "")
        if prep_time or cook_time or total_time:
            prompt += f"**Times:** Prep: {prep_time or 'N/A'}, Cook: {cook_time or 'N/A'}, Total: {total_time or 'N/A'}\n"
        
        prompt += "**Ingredients:**\n"
        ingredients = recipe.get("recipeIngredient", [])
        for ing in ingredients[:15]:  # Limit to first 15 to save tokens
            display = ing.get("display") or ing.get("note") or ing.get("originalText") or ""
            if display:
                prompt += f"- {display}\n"
        if len(ingredients) > 15:
            prompt += f"- ... and {len(ingredients) - 15} more\n"
        
        # Include instruction count
        instructions = recipe.get("recipeInstructions", [])
        prompt += f"**Steps:** {len(instructions)} instruction steps\n"
        
        prompt += "\n"
    
    prompt += "\nTag all recipes above. Return ONLY the JSON array, no other text. Use index numbers, not slugs."
    
    return prompt


async def apply_tags_batch(
    recipes: list[dict],
    dry_run: bool = False,
) -> list[dict]:
    """Apply tags and categories to a batch of recipes.
    
    Args:
        recipes: List of recipe dicts from Mealie
        dry_run: If True, return what would be tagged without making changes
        
    Returns:
        List of tagging results with slugs
    """
    if not recipes:
        return []
    
    if dry_run:
        return [{"slug": r.get("slug"), "would_tag": True} for r in recipes]
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable required")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = _build_tagging_prompt(recipes)
    
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    
    # Parse response
    content = response.content[0].text
    
    # Extract JSON from response
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    
    try:
        results = json.loads(content.strip())
    except json.JSONDecodeError as e:
        print(f"Failed to parse tagging response: {e}")
        print(f"Response: {content[:500]}")
        return []
    
    # Validate tags and map index back to original slug
    all_valid_tags = set()
    for tag_list in VALID_TAGS.values():
        all_valid_tags.update(tag_list)
    
    for result in results:
        valid_tags = [t for t in result.get("tags", []) if t in all_valid_tags]
        result["tags"] = valid_tags
        
        # Map index back to original slug
        idx = result.get("index")
        if idx is not None and 1 <= idx <= len(recipes):
            result["slug"] = recipes[idx - 1].get("slug")
        elif "slug" not in result:
            # No index and no slug - mark for filtering
            result["_invalid"] = True
        # Remove index from result
        result.pop("index", None)
    
    # Filter out invalid results
    valid_results = [r for r in results if not r.get("_invalid") and r.get("slug")]
    return valid_results


async def apply_tags_for_recipes(
    recipes: list[dict],
    batch_size: int = 15,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[dict]:
    """Apply tags to multiple recipes in batches.
    
    Args:
        recipes: List of recipe dicts
        batch_size: Number of recipes per LLM call
        dry_run: If True, don't make actual LLM calls
        verbose: Print progress
        
    Returns:
        List of all tagging results
    """
    if verbose:
        print(f"Tagging {len(recipes)} recipes...")
    
    if not recipes:
        return []
    
    all_results = []
    
    for i in range(0, len(recipes), batch_size):
        batch = recipes[i:i + batch_size]
        
        if verbose:
            print(f"Processing batch {i // batch_size + 1} ({len(batch)} recipes)...")
        
        results = await apply_tags_batch(batch, dry_run=dry_run)
        all_results.extend(results)
    
    return all_results
