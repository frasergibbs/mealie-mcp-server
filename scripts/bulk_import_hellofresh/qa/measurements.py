"""Phase 2: Normalize proprietary measurements to standard cooking units."""

import json
import os
import re
from typing import Any

import anthropic

# Model for measurement normalization
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 8192

# Patterns indicating proprietary measurements
PROPRIETARY_PATTERNS = [
    r"\bsachet\b",
    r"\bpacket\b",
    r"\bpunnet\b",
    r"\bbunch\b",
    r"\bblock\b",
    r"\bbag\s+of\b",
    r"\btin\b",
    r"\bcan\b",
    r"\bjar\b",
    r"\btub\b",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in PROPRIETARY_PATTERNS]


def has_proprietary_measurements(recipe: dict) -> bool:
    """Check if a recipe has proprietary measurement terms.
    
    Args:
        recipe: Recipe dict from Mealie API
        
    Returns:
        True if any ingredient contains proprietary terms
    """
    ingredients = recipe.get("recipeIngredient", [])
    
    for ing in ingredients:
        display = ing.get("display") or ing.get("note") or ing.get("originalText") or ""
        display_lower = display.lower()
        
        for pattern in COMPILED_PATTERNS:
            if pattern.search(display_lower):
                return True
    
    return False


def _get_proprietary_ingredients(recipe: dict) -> list[dict]:
    """Extract ingredients with proprietary measurements.
    
    Args:
        recipe: Recipe dict
        
    Returns:
        List of ingredient dicts with proprietary terms
    """
    result = []
    ingredients = recipe.get("recipeIngredient", [])
    
    for i, ing in enumerate(ingredients):
        display = ing.get("display") or ing.get("note") or ing.get("originalText") or ""
        
        for pattern in COMPILED_PATTERNS:
            if pattern.search(display):
                result.append({
                    "index": i,
                    "original": display,
                    "ingredient": ing,
                })
                break
    
    return result


def _build_measurement_prompt(recipes_with_ingredients: list[dict]) -> str:
    """Build prompt for measurement normalization.
    
    Args:
        recipes_with_ingredients: List of dicts with recipe info and proprietary ingredients
        
    Returns:
        Formatted prompt string
    """
    prompt = """You are a cooking expert converting proprietary meal-kit measurements to standard cooking units.

## HelloFresh/Meal Kit Typical Sizes

Based on HelloFresh AU/NZ typical portions:
- **Spice sachets**: 10-15g (1-2 tbsp of mixed spices)
- **Paste sachets**: 20-30g (1-2 tbsp)
- **Cheese packets**: 50-100g depending on type
- **Herb bunches**: 20-30g fresh herbs
- **Punnets**: 200-250g (cherry tomatoes, berries)
- **Tins/cans**: Usually 400g for tomatoes, 125-200g for tuna
- **Blocks**: Feta 100-150g, tofu 200-300g

## Task

For each ingredient below, provide:
1. The normalized measurement in standard units (g, tbsp, tsp, cups, etc.)
2. For spice blends, optionally expand to component spices if you know the blend

## Output Format

Return a JSON array using the EXACT recipe index number provided:
```json
[
  {
    "recipe_index": 1,
    "ingredients": [
      {
        "index": 0,
        "original": "1 sachet Mexican spice blend",
        "normalized": "15g (1 tbsp) Mexican spice blend",
        "components": ["1 tsp cumin", "1 tsp paprika", "½ tsp chili powder", "¼ tsp garlic powder"]
      },
      {
        "index": 2,
        "original": "1 packet shredded cheese",
        "normalized": "100g shredded cheese",
        "components": null
      }
    ]
  }
]
```

IMPORTANT: Use the recipe index number (1, 2, 3, etc.) - do NOT include or modify slugs.

## Recipes to Normalize

"""
    
    for i, item in enumerate(recipes_with_ingredients, 1):
        recipe = item["recipe"]
        ingredients = item["proprietary_ingredients"]
        
        prompt += f"\n### Recipe {i} (index={i}): {recipe.get('name', 'Unknown')}\n"
        prompt += "**Ingredients to normalize:**\n"
        
        for ing in ingredients:
            prompt += f"- [index {ing['index']}] {ing['original']}\n"
        
        prompt += "\n"
    
    prompt += "\nNormalize all ingredients above. Return ONLY the JSON array, no other text. Use recipe_index, not slugs."
    
    return prompt, recipes_with_ingredients


async def normalize_measurements_batch(
    recipes: list[dict],
    dry_run: bool = False,
) -> list[dict]:
    """Normalize proprietary measurements for a batch of recipes.
    
    Args:
        recipes: List of recipe dicts from Mealie
        dry_run: If True, return what would be normalized without making changes
        
    Returns:
        List of normalization results with slugs and updated ingredients
    """
    if not recipes:
        return []
    
    # Build list of recipes with their proprietary ingredients
    recipes_with_ingredients = []
    for recipe in recipes:
        proprietary = _get_proprietary_ingredients(recipe)
        if proprietary:
            recipes_with_ingredients.append({
                "recipe": recipe,
                "proprietary_ingredients": proprietary,
            })
    
    if not recipes_with_ingredients:
        return []
    
    if dry_run:
        return [
            {
                "slug": item["recipe"].get("slug"),
                "ingredients_to_normalize": len(item["proprietary_ingredients"]),
                "would_normalize": True,
            }
            for item in recipes_with_ingredients
        ]
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable required")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt, indexed_recipes = _build_measurement_prompt(recipes_with_ingredients)
    
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
        print(f"Failed to parse measurement response: {e}")
        print(f"Response: {content[:500]}")
        return []
    
    # Map recipe_index back to slug
    for result in results:
        idx = result.get("recipe_index")
        if idx is not None and 1 <= idx <= len(indexed_recipes):
            result["slug"] = indexed_recipes[idx - 1]["recipe"].get("slug")
        # Remove recipe_index from result
        result.pop("recipe_index", None)
    
    return results


async def normalize_measurements_for_recipes(
    recipes: list[dict],
    batch_size: int = 10,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[dict]:
    """Normalize measurements for multiple recipes in batches.
    
    Args:
        recipes: List of recipe dicts
        batch_size: Number of recipes per LLM call
        dry_run: If True, don't make actual LLM calls
        verbose: Print progress
        
    Returns:
        List of all normalization results
    """
    # Filter to only recipes with proprietary measurements
    recipes_needing = [r for r in recipes if has_proprietary_measurements(r)]
    
    if verbose:
        print(f"Found {len(recipes_needing)}/{len(recipes)} recipes with proprietary measurements")
    
    if not recipes_needing:
        return []
    
    all_results = []
    
    for i in range(0, len(recipes_needing), batch_size):
        batch = recipes_needing[i:i + batch_size]
        
        if verbose:
            print(f"Processing batch {i // batch_size + 1} ({len(batch)} recipes)...")
        
        results = await normalize_measurements_batch(batch, dry_run=dry_run)
        all_results.extend(results)
    
    return all_results
