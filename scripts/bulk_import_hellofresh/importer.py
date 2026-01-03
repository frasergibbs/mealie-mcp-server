from __future__ import annotations

"""Bulk import matched recipes into Mealie."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for mealie_mcp imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from mealie_mcp.client import MealieClient
from mealie_mcp.models import ErrorResponse


async def import_recipe(
    client: MealieClient,
    url: str,
    include_tags: bool = False,
) -> dict:
    """Import a single recipe from URL.

    Args:
        client: Mealie client instance
        url: Recipe URL to import
        include_tags: Whether to include tags from source

    Returns:
        Result dict with status and details
    """
    result = await client.import_recipe_from_url(url, include_tags)

    if isinstance(result, ErrorResponse):
        return {
            "success": False,
            "url": url,
            "error": result.message,
            "code": result.code,
        }

    return {
        "success": True,
        "url": url,
        "slug": result,
    }


async def bulk_import(
    matches: list[dict],
    min_confidence: str = "medium",
    include_tags: bool = False,
    delay_seconds: float = 1.0,
    dry_run: bool = False,
    progress_callback: callable | None = None,
) -> dict:
    """Bulk import matched recipes into Mealie.

    Args:
        matches: List of match results from matcher
        min_confidence: Minimum confidence level to import
        include_tags: Whether to include tags from source
        delay_seconds: Delay between imports (rate limiting)
        dry_run: If True, don't actually import
        progress_callback: Optional callback(current, total, result)

    Returns:
        Summary dict with imported, skipped, failed lists
    """
    confidence_levels = {"high": 3, "medium": 2, "low": 1}
    min_level = confidence_levels.get(min_confidence, 2)

    # Filter by confidence
    to_import = [
        m for m in matches
        if m.get("matched_url")
        and confidence_levels.get(m.get("confidence"), 0) >= min_level
    ]

    skipped_no_match = [m for m in matches if not m.get("matched_url")]
    skipped_low_confidence = [
        m for m in matches
        if m.get("matched_url")
        and confidence_levels.get(m.get("confidence"), 0) < min_level
    ]

    results = {
        "imported": [],
        "failed": [],
        "skipped_no_match": skipped_no_match,
        "skipped_low_confidence": skipped_low_confidence,
        "dry_run": dry_run,
    }

    if dry_run:
        print(f"\n[DRY RUN] Would import {len(to_import)} recipes:")
        for m in to_import[:10]:
            print(f"  - {m.get('scanned')} → {m.get('matched_name')}")
        if len(to_import) > 10:
            print(f"  ... and {len(to_import) - 10} more")
        results["would_import"] = to_import
        return results

    # Initialize client
    client = MealieClient()

    try:
        total = len(to_import)
        for i, match in enumerate(to_import):
            url = match["matched_url"]

            if progress_callback:
                progress_callback(i, total, None)

            print(f"  [{i+1}/{total}] Importing: {match.get('matched_name', url)[:50]}...")

            result = await import_recipe(client, url, include_tags)

            if result["success"]:
                results["imported"].append({
                    **match,
                    "imported_slug": result["slug"],
                })
                print(f"    ✓ Imported as: {result['slug']}")
            else:
                results["failed"].append({
                    **match,
                    "error": result["error"],
                    "error_code": result.get("code"),
                })
                print(f"    ✗ Failed: {result['error']}")

            if progress_callback:
                progress_callback(i + 1, total, result)

            # Rate limiting
            if i < total - 1:
                await asyncio.sleep(delay_seconds)

    finally:
        await client.close()

    return results


def summarize_results(results: dict) -> None:
    """Print a summary of import results.

    Args:
        results: Results dict from bulk_import
    """
    imported = len(results.get("imported", []))
    failed = len(results.get("failed", []))
    skipped_no_match = len(results.get("skipped_no_match", []))
    skipped_low_conf = len(results.get("skipped_low_confidence", []))

    total = imported + failed + skipped_no_match + skipped_low_conf

    print("\n" + "=" * 50)
    print("IMPORT SUMMARY")
    print("=" * 50)

    if results.get("dry_run"):
        print("[DRY RUN - No actual imports performed]")
        would_import = len(results.get("would_import", []))
        print(f"Would import: {would_import}")

    print(f"Total recipes processed: {total}")
    print(f"  ✓ Imported:              {imported}")
    print(f"  ✗ Failed:                {failed}")
    print(f"  ○ Skipped (no match):    {skipped_no_match}")
    print(f"  ○ Skipped (low conf):    {skipped_low_conf}")

    if failed > 0:
        print("\nFailed imports:")
        for f in results.get("failed", [])[:5]:
            print(f"  - {f.get('scanned')}: {f.get('error')}")
        if failed > 5:
            print(f"  ... and {failed - 5} more")


def save_results(results: dict, output_path: str | Path) -> None:
    """Save import results to JSON file.

    Args:
        results: Results dict from bulk_import
        output_path: Path for output file
    """
    output_path = Path(output_path)

    # Add metadata
    results_with_meta = {
        "timestamp": datetime.now().isoformat(),
        **results,
    }

    with open(output_path, "w") as f:
        json.dump(results_with_meta, f, indent=2)

    print(f"\nResults saved to {output_path}")


def load_existing_recipes_for_dedup() -> set[str]:
    """Load existing recipe slugs from Mealie for deduplication.

    Returns:
        Set of existing recipe slugs
    """
    # This would need to be implemented with actual Mealie API call
    # For now, return empty set
    return set()


if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("Usage: python -m scripts.bulk_import_hellofresh.importer <matches.json>")
            print("\nOptions:")
            print("  --dry-run    Show what would be imported without importing")
            print("  --min-conf   Minimum confidence (high, medium, low)")
            sys.exit(1)

        matches_file = sys.argv[1]
        dry_run = "--dry-run" in sys.argv

        with open(matches_file) as f:
            matches = json.load(f)

        print(f"Loaded {len(matches)} matches from {matches_file}")

        results = await bulk_import(
            matches,
            min_confidence="medium",
            dry_run=dry_run,
        )

        summarize_results(results)

    asyncio.run(main())
