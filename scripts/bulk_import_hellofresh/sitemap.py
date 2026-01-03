"""Fetch and parse HelloFresh sitemap to extract all recipe URLs."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

# Sitemap URLs by country code
SITEMAP_URLS = {
    "au": "https://www.hellofresh.com.au/sitemap_recipe_pages.xml",
    "uk": "https://www.hellofresh.co.uk/sitemap_recipe_pages.xml",
    "us": "https://www.hellofresh.com/sitemap_recipe_pages.xml",
    "de": "https://www.hellofresh.de/sitemap_recipe_pages.xml",
    "nz": "https://www.hellofresh.co.nz/sitemap_recipe_pages.xml",
}

# Cache directory for sitemap data
CACHE_DIR = Path(__file__).parent / ".cache"


def extract_recipe_name_from_url(url: str) -> str:
    """Extract a human-readable recipe name from HelloFresh URL.

    URLs follow patterns like:
    - /recipes/6-ingredients-texan-chicken-pita-pockets-68be74849f91a82a63be9274
    - /recipes/fancify-r50298-1-cheddar-cheese-coriander-and-lime-68bf8dd03cfb1178587558b5

    Args:
        url: Full HelloFresh recipe URL

    Returns:
        Human-readable recipe name
    """
    # Extract slug after /recipes/
    match = re.search(r"/recipes/(.+)$", url)
    if not match:
        return url

    slug = match.group(1)

    # Remove the hash suffix (24 char hex at end)
    # Pattern: everything after last hyphen if it's a 24-char hex string
    parts = slug.rsplit("-", 1)
    if len(parts) == 2 and re.match(r"^[a-f0-9]{24}$", parts[1]):
        slug = parts[0]

    # Remove common prefixes like "fancify-r50298-1-"
    slug = re.sub(r"^fancify-r\d+-\d+-", "", slug)
    slug = re.sub(r"^6-ingredients-", "6 Ingredients ", slug)

    # Convert hyphens to spaces and title case
    name = slug.replace("-", " ").title()

    return name


async def fetch_sitemap(country: str = "au", timeout: float = 60.0) -> str:
    """Fetch raw sitemap XML from HelloFresh.

    Args:
        country: Country code (au, uk, us, de, nz)
        timeout: Request timeout in seconds

    Returns:
        Raw XML string

    Raises:
        ValueError: If country code is not supported
        httpx.HTTPError: On network errors
    """
    if country not in SITEMAP_URLS:
        raise ValueError(f"Unsupported country: {country}. Supported: {list(SITEMAP_URLS.keys())}")

    url = SITEMAP_URLS[country]

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def parse_sitemap(xml_content: str) -> list[dict]:
    """Parse sitemap XML and extract recipe information.

    Args:
        xml_content: Raw XML string from sitemap

    Returns:
        List of dicts with keys: url, name, slug, lastmod
    """
    root = ET.fromstring(xml_content)

    # Sitemap namespace - try both http and https variants
    # Some regions use http://, others use https://
    namespaces = [
        {"s": "https://www.sitemaps.org/schemas/sitemap/0.9"},
        {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"},
    ]

    recipes = []
    for ns in namespaces:
        for url_elem in root.findall("s:url", ns):
            loc_elem = url_elem.find("s:loc", ns)
            lastmod_elem = url_elem.find("s:lastmod", ns)

            if loc_elem is None or loc_elem.text is None:
                continue

            url = loc_elem.text
            lastmod = lastmod_elem.text if lastmod_elem is not None else None

            # Extract slug from URL
            slug_match = re.search(r"/recipes/(.+)$", url)
            slug = slug_match.group(1) if slug_match else ""

            recipes.append({
                "url": url,
                "name": extract_recipe_name_from_url(url),
                "slug": slug,
                "lastmod": lastmod,
            })

    return recipes


async def fetch_and_parse_sitemap(
    country: str = "au",
    use_cache: bool = True,
    cache_hours: int = 24,
) -> list[dict]:
    """Fetch and parse HelloFresh sitemap, with optional caching.

    Args:
        country: Country code (au, uk, us, de, nz)
        use_cache: Whether to use cached sitemap data
        cache_hours: Cache validity in hours

    Returns:
        List of recipe dicts with url, name, slug, lastmod
    """
    import time

    cache_file = CACHE_DIR / f"sitemap_{country}.json"

    # Check cache
    if use_cache and cache_file.exists():
        cache_age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
        if cache_age_hours < cache_hours:
            with open(cache_file) as f:
                return json.load(f)

    # Fetch fresh data
    xml_content = await fetch_sitemap(country)
    recipes = parse_sitemap(xml_content)

    # Save to cache
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(recipes, f, indent=2)

    return recipes


def load_cached_sitemap(country: str = "au") -> list[dict] | None:
    """Load sitemap from cache if available.

    Args:
        country: Country code

    Returns:
        Cached recipe list or None if not cached
    """
    cache_file = CACHE_DIR / f"sitemap_{country}.json"

    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    return None


async def fetch_all_sitemaps(
    countries: list[str] | None = None,
    use_cache: bool = True,
    deduplicate: bool = True,
) -> list[dict]:
    """Fetch and combine recipes from multiple HelloFresh regional sitemaps.

    Args:
        countries: List of country codes to fetch. Defaults to all.
        use_cache: Whether to use cached sitemap data
        deduplicate: Remove duplicate recipes (by name)

    Returns:
        Combined list of recipe dicts
    """
    if countries is None:
        countries = list(SITEMAP_URLS.keys())

    all_recipes = []
    for country in countries:
        try:
            recipes = await fetch_and_parse_sitemap(country, use_cache=use_cache)
            # Add country to each recipe
            for r in recipes:
                r["country"] = country
            all_recipes.extend(recipes)
            print(f"  {country.upper()}: {len(recipes)} recipes")
        except Exception as e:
            print(f"  {country.upper()}: Error - {e}")

    if deduplicate:
        # Deduplicate by lowercase name, keeping first occurrence
        seen_names = set()
        unique_recipes = []
        for r in all_recipes:
            name_lower = r["name"].lower()
            if name_lower not in seen_names:
                seen_names.add(name_lower)
                unique_recipes.append(r)
        print(f"  Deduplicated: {len(all_recipes)} → {len(unique_recipes)} unique recipes")
        return unique_recipes

    return all_recipes


if __name__ == "__main__":
    import asyncio

    async def main():
        print("Fetching HelloFresh AU sitemap...")
        recipes = await fetch_and_parse_sitemap("au")
        print(f"Found {len(recipes)} recipes")

        # Show first 10
        print("\nFirst 10 recipes:")
        for r in recipes[:10]:
            print(f"  - {r['name']}")
            print(f"    URL: {r['url']}")

    asyncio.run(main())
