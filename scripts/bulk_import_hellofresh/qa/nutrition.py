"""Phase 1: Nutrition calculation for recipes with missing nutrition data."""

import json
import os
from typing import Any

import anthropic

# Model for nutrition calculation - needs detailed reasoning
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 8192


def needs_nutrition(recipe: dict) -> bool:
    """Check if a recipe needs nutrition data calculated.
    
    Args:
        recipe: Recipe dict from Mealie API
        
    Returns:
        True if nutrition is missing or incomplete
    """
    nutrition = recipe.get("nutrition")
    if not nutrition:
        return True
    
    # Check for required fields
    required = ["calories", "proteinContent", "carbohydrateContent", "fatContent"]
    for field in required:
        value = nutrition.get(field)
        if not value or value in ("", "0", "0g", "0 kcal"):
            return True
    
    return False


def _build_nutrition_prompt(recipes: list[dict]) -> str:
    """Build prompt for nutrition calculation.
    
    Args:
        recipes: List of recipe dicts to calculate nutrition for
        
    Returns:
        Formatted prompt string
    """
    prompt = """You are a nutritionist calculating accurate PER-SERVING nutrition for recipes.

CRITICAL: All values must be PER SINGLE SERVING, not for the entire recipe.

## Guidelines

1. **Parse each ingredient** - Extract quantity, unit, and food item
2. **Look up nutrition per 100g** for each ingredient:
   - Proteins: chicken breast 31g protein/100g, beef mince 20g/100g, salmon 25g/100g
   - Carbs: rice 28g/100g cooked, pasta 25g/100g cooked, potato 17g/100g
   - Fats: olive oil 100g fat/100g, butter 81g/100g, cheese 25-35g/100g
   - Common veggies: ~20-50 kcal/100g, low protein/fat, 5-10g carbs
3. **Calculate totals** for the ENTIRE recipe based on all ingredient quantities
4. **DIVIDE BY SERVING COUNT** to get PER-SERVING values (this step is critical!)
5. **Typical per-serving ranges**: 400-800 kcal, 25-50g protein, 40-80g carbs, 15-35g fat

## Output Format

Return a JSON array with one object per recipe, using the EXACT recipe index number provided:
```json
[
  {
    "index": 1,
    "nutrition": {
      "calories": "520 kcal",
      "proteinContent": "35g",
      "carbohydrateContent": "45g",
      "fatContent": "22g",
      "fiberContent": "6g",
      "sodiumContent": "800mg",
      "sugarContent": "8g"
    },
    "calculation_notes": "Brief notes on key ingredients"
  }
]
```

IMPORTANT: Use the recipe index number (1, 2, 3, etc.) - do NOT include or modify slugs.

## Recipes to Calculate

"""
    
    for i, recipe in enumerate(recipes, 1):
        prompt += f"\n### Recipe {i} (index={i}): {recipe.get('name', 'Unknown')}\n"
        prompt += f"**Servings:** {recipe.get('recipeYield', '2 servings')}\n"
        prompt += "**Ingredients:**\n"
        
        ingredients = recipe.get("recipeIngredient", [])
        for ing in ingredients:
            display = ing.get("display") or ing.get("note") or ing.get("originalText") or ""
            if display:
                prompt += f"- {display}\n"
        
        prompt += "\n"
    
    prompt += "\nCalculate nutrition for all recipes above. Return ONLY the JSON array, no other text. Use index numbers, not slugs."
    
    return prompt


async def calculate_nutrition_batch(
    recipes: list[dict],
    dry_run: bool = False,
) -> list[dict]:
    """Calculate nutrition for a batch of recipes using LLM.
    
    Args:
        recipes: List of recipe dicts from Mealie
        dry_run: If True, return what would be calculated without making changes
        
    Returns:
        List of nutrition results with slugs
    """
    if not recipes:
        return []
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable required")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = _build_nutrition_prompt(recipes)
    
    if dry_run:
        return [{"slug": r.get("slug"), "would_calculate": True} for r in recipes]
    
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    
    # Parse response
    content = response.content[0].text
    
    # Extract JSON from response (handle markdown code blocks)
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    
    try:
        results = json.loads(content.strip())
    except json.JSONDecodeError as e:
        print(f"Failed to parse nutrition response: {e}")
        print(f"Response: {content[:500]}")
        return []
    
    # Map index back to original slug
    for result in results:
        idx = result.get("index")
        if idx is not None and 1 <= idx <= len(recipes):
            result["slug"] = recipes[idx - 1].get("slug")
        elif "slug" not in result:
            # No index and no slug - skip this result
            continue
        # Remove index from result, keep only slug
        result.pop("index", None)
    
    # Filter out results without valid slugs
    valid_results = [r for r in results if r.get("slug")]
    return valid_results


async def calculate_nutrition_for_recipes(
    recipes: list[dict],
    batch_size: int = 8,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[dict]:
    """Calculate nutrition for multiple recipes in batches.
    
    Args:
        recipes: List of recipe dicts
        batch_size: Number of recipes per LLM call
        dry_run: If True, don't make actual LLM calls
        verbose: Print progress
        
    Returns:
        List of all nutrition results
    """
    # Filter to only recipes needing nutrition
    recipes_needing = [r for r in recipes if needs_nutrition(r)]
    
    if verbose:
        print(f"Found {len(recipes_needing)}/{len(recipes)} recipes needing nutrition")
    
    if not recipes_needing:
        return []
    
    all_results = []
    
    for i in range(0, len(recipes_needing), batch_size):
        batch = recipes_needing[i:i + batch_size]
        
        if verbose:
            print(f"Processing batch {i // batch_size + 1} ({len(batch)} recipes)...")
        
        results = await calculate_nutrition_batch(batch, dry_run=dry_run)
        all_results.extend(results)
    
    return all_results
