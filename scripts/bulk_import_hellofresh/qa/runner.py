"""QA pipeline runner - orchestrates all phases."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment variables from repo root
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

# Add src to path for MealieClient
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from mealie_mcp.client import MealieClient

from .nutrition import calculate_nutrition_for_recipes, needs_nutrition
from .measurements import normalize_measurements_for_recipes, has_proprietary_measurements
from .tagging import apply_tags_for_recipes


class TagCategoryCache:
    """Cache for existing tags and categories to avoid repeated API calls."""
    
    def __init__(self):
        self.tags: dict[str, dict] = {}  # slug -> full tag object
        self.categories: dict[str, dict] = {}  # slug -> full category object
        self.group_id: str | None = None
        self._loaded = False
    
    async def load(self, client: MealieClient) -> None:
        """Load all existing tags and categories."""
        if self._loaded:
            return
        
        self.group_id = await client.get_group_id()
        
        # Load tags
        tags_result = await client._request("GET", "/organizers/tags", params={"perPage": 500})
        if isinstance(tags_result, dict) and "items" in tags_result:
            for tag in tags_result["items"]:
                self.tags[tag["slug"]] = tag
        
        # Load categories
        cats_result = await client._request("GET", "/organizers/categories", params={"perPage": 500})
        if isinstance(cats_result, dict) and "items" in cats_result:
            for cat in cats_result["items"]:
                self.categories[cat["slug"]] = cat
        
        self._loaded = True
    
    async def get_or_create_tag(self, client: MealieClient, name: str) -> dict:
        """Get existing tag or create new one."""
        slug = name.lower().replace(" ", "-")
        
        if slug in self.tags:
            return self.tags[slug]
        
        # Create new tag
        result = await client._request("POST", "/organizers/tags", json={"name": name})
        if isinstance(result, dict) and "id" in result:
            self.tags[slug] = result
            return result
        
        # If creation failed, return minimal object (will likely fail on update)
        return {"name": name, "slug": slug, "groupId": self.group_id}
    
    async def get_or_create_category(self, client: MealieClient, name: str) -> dict:
        """Get existing category or create new one."""
        slug = name.lower().replace(" ", "-")
        
        if slug in self.categories:
            return self.categories[slug]
        
        # Create new category
        result = await client._request("POST", "/organizers/categories", json={"name": name})
        if isinstance(result, dict) and "id" in result:
            self.categories[slug] = result
            return result
        
        # If creation failed, return minimal object
        return {"name": name, "slug": slug, "groupId": self.group_id}


async def fetch_recipes_by_category(
    client: MealieClient,
    category: str | None = None,
    limit: int | None = None,
    verbose: bool = False,
) -> list[dict]:
    """Fetch recipes from Mealie, optionally filtered by category.
    
    Args:
        client: MealieClient instance
        category: Category slug to filter by (e.g., "hellofresh"), empty string for all
        limit: Maximum number of recipes to fetch
        verbose: Print progress
        
    Returns:
        List of full recipe dicts
    """
    # Search with category filter if provided (empty string means no filter)
    categories = [category] if category else None
    
    # Fetch recipe summaries
    summaries = await client.search_recipes(
        query="",
        categories=categories,
        per_page=limit or 500,
    )
    
    if hasattr(summaries, "model_dump"):
        # ErrorResponse
        print(f"Error fetching recipes: {summaries}")
        return []
    
    # Fetch full details for each recipe, skipping any that fail
    recipes = []
    skipped = 0
    for summary in summaries:
        slug = summary.slug if hasattr(summary, "slug") else summary.get("slug")
        try:
            recipe = await client.get_recipe(slug)
            
            # Check if it's an error response
            if hasattr(recipe, "error") and recipe.error:
                skipped += 1
                if verbose:
                    print(f"  Skipping {slug} (error loading)")
                continue
            
            if not hasattr(recipe, "model_dump"):
                skipped += 1
                continue
            
            recipe_dict = recipe.model_dump(by_alias=True)
            
            # Double-check for error in dict
            if recipe_dict.get("error"):
                skipped += 1
                if verbose:
                    print(f"  Skipping {slug} (error in data)")
                continue
            
            # IMPORTANT: Use the API slug (from summary) not the recipe's internal slug
            # These can differ due to Mealie data inconsistencies
            recipe_dict["slug"] = slug
            
            recipes.append(recipe_dict)
            
        except Exception as e:
            skipped += 1
            if verbose:
                print(f"  Skipping {slug} (exception: {e})")
            continue
    
    if skipped > 0 and verbose:
        print(f"  Skipped {skipped} recipes due to errors")
    
    return recipes


async def apply_updates_to_mealie(
    client: MealieClient,
    updates: list[dict],
    update_type: str,
    tag_cache: TagCategoryCache | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Apply QA updates to Mealie recipes.
    
    Args:
        client: MealieClient instance
        updates: List of update dicts from QA phases
        update_type: One of "nutrition", "measurements", "tags"
        tag_cache: Cache for tags/categories (required for tags update_type)
        dry_run: If True, don't make actual updates
        verbose: Print progress
        
    Returns:
        Summary of updates applied
    """
    success = 0
    failed = 0
    
    for update in updates:
        slug = update.get("slug") or update.get("recipe_slug")
        if not slug:
            failed += 1
            continue
        
        try:
            update_data = {}
            
            if update_type == "nutrition":
                if "nutrition" in update:
                    update_data["nutrition"] = update["nutrition"]
            
            elif update_type == "measurements":
                # For measurements, reformat ALL ingredients uniformly like MCP tool
                if "ingredients" in update:
                    import uuid
                    recipe = await client.get_recipe(slug)
                    if hasattr(recipe, "model_dump"):
                        recipe_dict = recipe.model_dump(by_alias=True)
                        current_ingredients = recipe_dict.get("recipeIngredient", [])
                        
                        # Create a map of index -> normalized text for ingredients we're updating
                        updates_map = {
                            ing_update.get("index"): ing_update.get("normalized")
                            for ing_update in update["ingredients"]
                            if ing_update.get("index") is not None
                        }
                        
                        # Reformat ALL ingredients uniformly (critical for validation)
                        formatted_ingredients = []
                        for idx, ing in enumerate(current_ingredients):
                            # Use normalized text if we have an update, otherwise preserve display
                            display_text = updates_map.get(idx, ing.get("display", ing.get("note", "")))
                            
                            # Format exactly like MCP tool does
                            formatted_ing = {
                                "referenceId": str(uuid.uuid4()),
                                "display": display_text,
                                "note": display_text,
                            }
                            formatted_ingredients.append(formatted_ing)
                        
                        update_data["recipeIngredient"] = formatted_ingredients
            
            elif update_type == "tags":
                if tag_cache is None:
                    raise ValueError("tag_cache required for tags update")
                
                # Fetch current recipe to get existing tags/categories
                recipe = await client.get_recipe(slug)
                if not hasattr(recipe, "model_dump"):
                    failed += 1
                    if verbose:
                        print(f"  ✗ Failed to fetch {slug}")
                    continue
                
                recipe_dict = recipe.model_dump(by_alias=True)
                
                if "tags" in update:
                    # Merge with existing tags to avoid duplicates
                    existing_tag_names = {tag.get("name") or tag.get("slug", "") 
                                         for tag in recipe_dict.get("tags", [])}
                    new_tag_names = set(update["tags"])
                    
                    # Combine and deduplicate
                    all_tag_names = existing_tag_names | new_tag_names
                    
                    # Get or create each tag with full object including ID
                    tag_objects = []
                    for tag_name in all_tag_names:
                        if tag_name:  # Skip empty strings
                            tag_obj = await tag_cache.get_or_create_tag(client, tag_name)
                            tag_objects.append(tag_obj)
                    update_data["tags"] = tag_objects
                
                if "categories" in update:
                    # Merge with existing categories to avoid duplicates
                    existing_cat_names = {cat.get("name") or cat.get("slug", "") 
                                         for cat in recipe_dict.get("recipeCategory", [])}
                    new_cat_names = set(update["categories"])
                    
                    # Combine and deduplicate
                    all_cat_names = existing_cat_names | new_cat_names
                    
                    # Get or create each category with full object including ID
                    cat_objects = []
                    for cat_name in all_cat_names:
                        if cat_name:  # Skip empty strings
                            cat_obj = await tag_cache.get_or_create_category(client, cat_name)
                            cat_objects.append(cat_obj)
                    update_data["recipeCategory"] = cat_objects
            
            if update_data:
                if dry_run:
                    if verbose:
                        print(f"  [DRY RUN] Would update {slug}: {list(update_data.keys())}")
                    success += 1
                else:
                    result = await client.update_recipe(slug, update_data)
                    if hasattr(result, "slug"):
                        success += 1
                        if verbose:
                            print(f"  ✓ Updated {slug}")
                    else:
                        failed += 1
                        if verbose:
                            print(f"  ✗ Failed to update {slug}: {result}")
            
        except Exception as e:
            failed += 1
            if verbose:
                print(f"  ✗ Error updating {slug}: {e}")
    
    return {"success": success, "failed": failed}


async def run_qa_pipeline(
    phase: str | None = None,
    category: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    verbose: bool = True,
    output_dir: str | None = None,
) -> dict:
    """Run the full QA pipeline or a specific phase.
    
    Args:
        phase: Specific phase to run ("nutrition", "measurements", "tags") or None for all
        category: Category slug to filter recipes (e.g., "hellofresh")
        limit: Maximum number of recipes to process
        dry_run: If True, don't make actual updates
        verbose: Print progress
        output_dir: Directory to save QA results (optional)
        
    Returns:
        Summary of QA results
    """
    # Run all phases by default: measurements, nutrition, and tags
    phases = ["measurements", "nutrition", "tags"] if phase is None else [phase]
    
    if verbose:
        print(f"Starting QA pipeline - phases: {phases}")
        if dry_run:
            print("[DRY RUN MODE - no changes will be made]")
    
    # Initialize client
    client = MealieClient()
    
    try:
        # Fetch recipes
        if verbose:
            print(f"\nFetching recipes (category: {category or 'all'})...")
        
        recipes = await fetch_recipes_by_category(client, category, limit, verbose=verbose)
        
        if verbose:
            print(f"Fetched {len(recipes)} recipes")
        
        if not recipes:
            return {"error": "No recipes found"}
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_recipes": len(recipes),
            "phases": {},
        }
        
        # Phase 1: Nutrition
        if "nutrition" in phases:
            if verbose:
                print("\n" + "=" * 50)
                print("PHASE 1: Nutrition Calculation")
                print("=" * 50)
            
            nutrition_results = await calculate_nutrition_for_recipes(
                recipes,
                dry_run=dry_run,
                verbose=verbose,
            )
            
            if nutrition_results and not dry_run:
                update_summary = await apply_updates_to_mealie(
                    client, nutrition_results, "nutrition",
                    dry_run=dry_run, verbose=verbose,
                )
                results["phases"]["nutrition"] = {
                    "calculated": len(nutrition_results),
                    **update_summary,
                }
            else:
                results["phases"]["nutrition"] = {
                    "would_calculate": len(nutrition_results) if dry_run else 0,
                }
            
            if verbose:
                print(f"Nutrition: {results['phases']['nutrition']}")
        
        # Phase 2: Measurements
        if "measurements" in phases:
            if verbose:
                print("\n" + "=" * 50)
                print("PHASE 2: Measurement Normalization")
                print("=" * 50)
            
            measurement_results = await normalize_measurements_for_recipes(
                recipes,
                dry_run=dry_run,
                verbose=verbose,
            )
            
            if measurement_results and not dry_run:
                update_summary = await apply_updates_to_mealie(
                    client, measurement_results, "measurements",
                    dry_run=dry_run, verbose=verbose,
                )
                results["phases"]["measurements"] = {
                    "normalized": len(measurement_results),
                    **update_summary,
                }
            else:
                results["phases"]["measurements"] = {
                    "would_normalize": len(measurement_results) if dry_run else 0,
                }
            
            if verbose:
                print(f"Measurements: {results['phases']['measurements']}")
        
        # Phase 3: Tagging
        if "tags" in phases:
            if verbose:
                print("\n" + "=" * 50)
                print("PHASE 3: Tagging & Categorization")
                print("=" * 50)
            
            # Initialize tag/category cache
            tag_cache = TagCategoryCache()
            if not dry_run:
                if verbose:
                    print("Loading existing tags and categories...")
                await tag_cache.load(client)
                if verbose:
                    print(f"  Found {len(tag_cache.tags)} tags, {len(tag_cache.categories)} categories")
            
            tagging_results = await apply_tags_for_recipes(
                recipes,
                dry_run=dry_run,
                verbose=verbose,
            )
            
            if tagging_results and not dry_run:
                update_summary = await apply_updates_to_mealie(
                    client, tagging_results, "tags",
                    tag_cache=tag_cache,
                    dry_run=dry_run, verbose=verbose,
                )
                results["phases"]["tags"] = {
                    "tagged": len(tagging_results),
                    **update_summary,
                }
            else:
                results["phases"]["tags"] = {
                    "would_tag": len(tagging_results) if dry_run else 0,
                }
            
            if verbose:
                print(f"Tags: {results['phases']['tags']}")
        
        # Save results if output dir specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = output_path / f"qa_results_{timestamp}.json"
            
            with open(result_file, "w") as f:
                json.dump(results, f, indent=2)
            
            if verbose:
                print(f"\nResults saved to: {result_file}")
        
        if verbose:
            print("\n" + "=" * 50)
            print("QA PIPELINE COMPLETE")
            print("=" * 50)
        
        return results
    
    finally:
        await client.close()


# Allow running as script
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run QA pipeline on recipes")
    parser.add_argument("--phase", choices=["nutrition", "measurements", "tags"],
                        help="Specific phase to run")
    parser.add_argument("--category", default="hellofresh",
                        help="Category to filter by")
    parser.add_argument("--limit", type=int, help="Max recipes to process")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't make actual updates")
    parser.add_argument("--output", help="Directory to save results")
    
    args = parser.parse_args()
    
    asyncio.run(run_qa_pipeline(
        phase=args.phase,
        category=args.category,
        limit=args.limit,
        dry_run=args.dry_run,
        output_dir=args.output,
    ))
