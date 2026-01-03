"""CLI orchestrator for bulk importing HelloFresh recipes."""

import asyncio
import json
import sys
from pathlib import Path

try:
    import click
except ImportError:
    raise ImportError("Click not installed. Run: pip install 'mealie-mcp[bulk-import]'")

from . import sitemap, ocr, matcher, importer
from .qa import runner as qa_runner


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Bulk import HelloFresh recipes from scanned recipe cards.

    Workflow:
    1. fetch-sitemap: Download HelloFresh recipe URLs
    2. ocr: Extract titles from scanned PDF
    3. match: Match titles to URLs using Claude
    4. import: Import matched recipes into Mealie

    Or use 'run' for the complete pipeline.
    """
    pass


@cli.command()
@click.option(
    "--country", "-c",
    default="au",
    type=click.Choice(["au", "uk", "us", "de", "nz", "all"]),
    help="HelloFresh country or 'all' for combined (default: au)",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Output JSON file (default: .cache/sitemap_<country>.json)",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Force fresh fetch, ignore cache",
)
def fetch_sitemap(country: str, output: str | None, no_cache: bool):
    """Fetch HelloFresh recipe sitemap.

    Downloads all recipe URLs from the HelloFresh sitemap for the specified
    country and caches them locally. Use --country all to fetch from all regions.
    """
    async def run():
        if country == "all":
            click.echo("Fetching HelloFresh sitemaps from ALL regions...")
            recipes = await sitemap.fetch_all_sitemaps(use_cache=not no_cache)
        else:
            click.echo(f"Fetching HelloFresh {country.upper()} sitemap...")
            recipes = await sitemap.fetch_and_parse_sitemap(
                country=country,
                use_cache=not no_cache,
            )

        click.echo(f"Found {len(recipes)} recipes")

        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(recipes, f, indent=2)
            click.echo(f"Saved to {output_path}")

        # Show sample
        click.echo("\nSample recipes:")
        for r in recipes[:5]:
            click.echo(f"  - {r['name']}")

    asyncio.run(run())


@cli.command()
@click.argument("pdf_file", type=click.Path(exists=True))
@click.option(
    "--output", "-o",
    type=click.Path(),
    default="titles.json",
    help="Output JSON file (default: titles.json)",
)
@click.option(
    "--dpi",
    default=300,
    type=int,
    help="DPI for PDF conversion (default: 300)",
)
def ocr_pdf(pdf_file: str, output: str, dpi: int):
    """Extract recipe titles from scanned PDF.

    Uses OCR to extract recipe titles from each page of a scanned PDF file.
    HelloFresh recipe cards typically have the title at the top of the card.
    """
    click.echo(f"Processing {pdf_file} at {dpi} DPI...")

    results = ocr.extract_titles_from_pdf(pdf_file, dpi=dpi)

    # Save results
    ocr.save_titles_to_file(results, output)

    # Show summary
    extracted = sum(1 for r in results if r["extracted_title"])
    click.echo(f"\nExtracted {extracted}/{len(results)} titles")

    # Show first few
    click.echo("\nFirst 10 titles:")
    for r in results[:10]:
        title = r["extracted_title"] or "(not found)"
        click.echo(f"  Page {r['page_number']}: {title}")


@cli.command()
@click.argument("titles_file", type=click.Path(exists=True))
@click.option(
    "--output", "-o",
    type=click.Path(),
    default="matches.json",
    help="Output JSON file (default: matches.json)",
)
@click.option(
    "--country", "-c",
    default="all",
    type=click.Choice(["au", "uk", "us", "de", "nz", "all"]),
    help="HelloFresh country or 'all' for combined sitemaps (default: all)",
)
@click.option(
    "--batch-size",
    default=30,
    type=int,
    help="Titles per LLM request (default: 30)",
)
@click.option(
    "--model",
    default="claude-haiku-4-5-20251001",
    help="Anthropic model to use",
)
def match(titles_file: str, output: str, country: str, batch_size: int, model: str):
    """Match OCR'd titles to HelloFresh URLs using Claude.

    Reads a JSON file of extracted titles and uses Claude to match them
    against the HelloFresh sitemap. Results are saved with confidence levels.
    """
    async def run():
        # Load titles
        with open(titles_file) as f:
            titles_data = json.load(f)

        titles = [item["title"] for item in titles_data if item.get("title")]
        click.echo(f"Loaded {len(titles)} titles from {titles_file}")

        # Load sitemap
        if country == "all":
            click.echo("Loading HelloFresh sitemaps from ALL regions...")
            recipes = await sitemap.fetch_all_sitemaps()
        else:
            click.echo(f"Loading HelloFresh {country.upper()} sitemap...")
            recipes = await sitemap.fetch_and_parse_sitemap(country=country)
        click.echo(f"Loaded {len(recipes)} recipes from sitemap")

        # Match
        click.echo(f"\nMatching titles using {model}...")
        matches = await matcher.match_all_titles(
            titles,
            recipes,
            batch_size=batch_size,
            model=model,
        )

        # Save results
        matcher.save_matches(matches, output)

        # Summary
        summary = matcher.summarize_matches(matches)
        click.echo(f"\nMatch rate: {summary['match_rate']}")

    asyncio.run(run())


@cli.command(name="import")
@click.argument("matches_file", type=click.Path(exists=True))
@click.option(
    "--min-confidence",
    type=click.Choice(["high", "medium", "low"]),
    default="medium",
    help="Minimum confidence to import (default: medium)",
)
@click.option(
    "--delay",
    default=1.0,
    type=float,
    help="Delay between imports in seconds (default: 1.0)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be imported without importing",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Save results to JSON file",
)
def import_recipes(
    matches_file: str,
    min_confidence: str,
    delay: float,
    dry_run: bool,
    output: str | None,
):
    """Import matched recipes into Mealie.

    Reads a matches JSON file and imports recipes into Mealie using the
    import_recipe_from_url API. Requires MEALIE_URL and MEALIE_TOKEN env vars.
    """
    async def run():
        # Load matches
        with open(matches_file) as f:
            matches = json.load(f)

        click.echo(f"Loaded {len(matches)} matches from {matches_file}")

        if dry_run:
            click.echo("[DRY RUN MODE]")

        # Import
        results = await importer.bulk_import(
            matches,
            min_confidence=min_confidence,
            delay_seconds=delay,
            dry_run=dry_run,
        )

        # Summary
        importer.summarize_results(results)

        # Save results
        if output:
            importer.save_results(results, output)

    asyncio.run(run())


@cli.command()
@click.argument("pdf_file", type=click.Path(exists=True))
@click.option(
    "--country", "-c",
    default="au",
    type=click.Choice(["au", "uk", "us", "de", "nz"]),
    help="HelloFresh country (default: au)",
)
@click.option(
    "--min-confidence",
    type=click.Choice(["high", "medium", "low"]),
    default="medium",
    help="Minimum confidence to import (default: medium)",
)
@click.option(
    "--dpi",
    default=300,
    type=int,
    help="DPI for PDF conversion (default: 300)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Match but don't import",
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(),
    default=".",
    help="Directory for intermediate files (default: current)",
)
def run(
    pdf_file: str,
    country: str,
    min_confidence: str,
    dpi: int,
    dry_run: bool,
    output_dir: str,
):
    """Complete pipeline: OCR → Match → Import.

    Runs the full import pipeline:
    1. Extract recipe titles from scanned PDF
    2. Fetch HelloFresh sitemap
    3. Match titles to URLs using Claude
    4. Import matched recipes into Mealie
    """
    async def run_pipeline():
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Step 1: OCR
        click.echo("=" * 50)
        click.echo("STEP 1: OCR - Extracting titles from PDF")
        click.echo("=" * 50)

        ocr_results = ocr.extract_titles_from_pdf(pdf_file, dpi=dpi)
        titles = [r["extracted_title"] for r in ocr_results if r["extracted_title"]]

        titles_file = output_path / "titles.json"
        ocr.save_titles_to_file(ocr_results, titles_file)

        click.echo(f"Extracted {len(titles)} titles\n")

        # Step 2: Fetch sitemap
        click.echo("=" * 50)
        click.echo("STEP 2: Fetching HelloFresh sitemap")
        click.echo("=" * 50)

        recipes = await sitemap.fetch_and_parse_sitemap(country=country)
        click.echo(f"Loaded {len(recipes)} recipes from sitemap\n")

        # Step 3: Match
        click.echo("=" * 50)
        click.echo("STEP 3: Matching titles to URLs with Claude")
        click.echo("=" * 50)

        matches = await matcher.match_all_titles(titles, recipes)

        matches_file = output_path / "matches.json"
        matcher.save_matches(matches, matches_file)

        summary = matcher.summarize_matches(matches)
        click.echo(f"Match rate: {summary['match_rate']}\n")

        # Step 4: Import
        click.echo("=" * 50)
        click.echo("STEP 4: Importing to Mealie")
        click.echo("=" * 50)

        if dry_run:
            click.echo("[DRY RUN - Skipping actual import]")

        results = await importer.bulk_import(
            matches,
            min_confidence=min_confidence,
            dry_run=dry_run,
        )

        results_file = output_path / "results.json"
        importer.save_results(results, results_file)
        importer.summarize_results(results)

    asyncio.run(run_pipeline())


@cli.command()
@click.option(
    "--country", "-c",
    default="au",
    type=click.Choice(["au", "uk", "us", "de", "nz"]),
    help="HelloFresh country (default: au)",
)
@click.argument("search_term")
def search_sitemap(country: str, search_term: str):
    """Search the sitemap for recipes matching a term.

    Useful for testing if specific recipes exist in the sitemap.
    """
    async def run():
        recipes = await sitemap.fetch_and_parse_sitemap(country=country)

        search_lower = search_term.lower()
        matches = [r for r in recipes if search_lower in r["name"].lower()]

        click.echo(f"Found {len(matches)} recipes matching '{search_term}':\n")
        for r in matches[:20]:
            click.echo(f"  - {r['name']}")
            click.echo(f"    {r['url']}")
        if len(matches) > 20:
            click.echo(f"\n  ... and {len(matches) - 20} more")

    asyncio.run(run())


@cli.command()
@click.option(
    "--phase", "-p",
    type=click.Choice(["nutrition", "measurements", "tags"]),
    help="Run specific phase only (default: all phases)",
)
@click.option(
    "--category", "-c",
    default="hellofresh",
    help="Category slug to filter recipes (default: hellofresh)",
)
@click.option(
    "--limit",
    type=int,
    help="Maximum number of recipes to process",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be changed without making changes",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Directory to save QA results",
)
def qa(
    phase: str | None,
    category: str | None,
    limit: int | None,
    dry_run: bool,
    output: str | None,
):
    """Run QA/QC pipeline on imported recipes.

    Post-import quality enhancement:
    
    \b
    Phase 1 - nutrition:     Calculate missing nutrition data
    Phase 2 - measurements:  Normalize sachets/packets to standard units  
    Phase 3 - tags:          Apply protein, cuisine, effort tags

    Examples:
    
    \b
    # Run full QA on HelloFresh recipes
    python -m scripts.bulk_import_hellofresh.cli qa
    
    \b
    # Dry run to see what would change
    python -m scripts.bulk_import_hellofresh.cli qa --dry-run
    
    \b
    # Run only nutrition phase
    python -m scripts.bulk_import_hellofresh.cli qa --phase nutrition
    
    \b
    # Process first 10 recipes
    python -m scripts.bulk_import_hellofresh.cli qa --limit 10
    """
    async def run():
        if dry_run:
            click.echo("[DRY RUN MODE - no changes will be made]\n")
        
        results = await qa_runner.run_qa_pipeline(
            phase=phase,
            category=category,
            limit=limit,
            dry_run=dry_run,
            verbose=True,
            output_dir=output,
        )
        
        if "error" in results:
            click.echo(f"Error: {results['error']}", err=True)
            return
        
        # Final summary
        click.echo("\n" + "=" * 50)
        click.echo("SUMMARY")
        click.echo("=" * 50)
        click.echo(f"Total recipes processed: {results.get('total_recipes', 0)}")
        for phase_name, phase_results in results.get("phases", {}).items():
            click.echo(f"\n{phase_name.title()}:")
            for key, value in phase_results.items():
                click.echo(f"  {key}: {value}")

    asyncio.run(run())


@cli.command()
@click.option(
    "--category", "-c",
    default="hellofresh",
    help="Category slug to filter recipes (default: hellofresh)",
)
@click.option(
    "--limit",
    type=int,
    default=5,
    help="Number of recipes to analyze (default: 5)",
)
def qa_preview(category: str | None, limit: int):
    """Preview recipes that need QA processing.

    Shows which recipes need nutrition calculation, measurement normalization,
    and tagging before running the full QA pipeline.
    """
    async def run():
        from .qa.nutrition import needs_nutrition
        from .qa.measurements import has_proprietary_measurements
        
        client = qa_runner.MealieClient()
        
        try:
            click.echo(f"Fetching recipes (category: {category})...")
            recipes = await qa_runner.fetch_recipes_by_category(client, category, limit)
            
            if not recipes:
                click.echo("No recipes found")
                return
            
            click.echo(f"\nAnalyzing {len(recipes)} recipes:\n")
            
            needs_nutr = 0
            needs_meas = 0
            
            for recipe in recipes:
                name = recipe.get("name", "Unknown")
                slug = recipe.get("slug", "")
                
                nutr = needs_nutrition(recipe)
                meas = has_proprietary_measurements(recipe)
                
                if nutr:
                    needs_nutr += 1
                if meas:
                    needs_meas += 1
                
                flags = []
                if nutr:
                    flags.append("📊 needs nutrition")
                if meas:
                    flags.append("📏 has proprietary measurements")
                flags.append("🏷️ needs tagging")  # All need tags
                
                click.echo(f"• {name}")
                click.echo(f"  Slug: {slug}")
                for flag in flags:
                    click.echo(f"  {flag}")
                click.echo()
            
            click.echo("=" * 50)
            click.echo(f"Summary ({len(recipes)} recipes):")
            click.echo(f"  Need nutrition: {needs_nutr}")
            click.echo(f"  Have proprietary measurements: {needs_meas}")
            click.echo(f"  Need tagging: {len(recipes)} (all)")
        
        finally:
            await client.close()

    asyncio.run(run())


def main():
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()
