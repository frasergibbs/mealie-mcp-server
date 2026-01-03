from __future__ import annotations

"""LLM-powered matching of OCR'd recipe titles to HelloFresh URLs."""

import json
import re
import os
from pathlib import Path

try:
    import anthropic
except ImportError:
    raise ImportError(
        "Anthropic SDK not installed. Run: pip install 'mealie-mcp[bulk-import]'"
    )


# Default model for matching - Haiku is fast/cheap and sufficient for this task
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# Batch size for LLM requests (balance context size vs API calls)
DEFAULT_BATCH_SIZE = 10

# Max candidates per title for LLM matching (to avoid rate limits)
MAX_CANDIDATES_PER_TITLE = 15


# Global inverted index cache
_keyword_index: dict[str, set[int]] | None = None
_indexed_recipes: list[dict] | None = None


def build_keyword_index(sitemap_recipes: list[dict]) -> dict[str, set[int]]:
    """Build an inverted index from keywords to recipe indices.

    This allows O(1) lookup of recipes containing a keyword.

    Args:
        sitemap_recipes: All recipes from sitemap

    Returns:
        Dict mapping keyword -> set of recipe indices
    """
    global _keyword_index, _indexed_recipes

    # Check if already cached for same recipes
    if _indexed_recipes is sitemap_recipes and _keyword_index is not None:
        return _keyword_index

    print("  Building keyword index...", flush=True)
    index: dict[str, set[int]] = {}

    for i, recipe in enumerate(sitemap_recipes):
        keywords = extract_keywords(recipe["name"])
        for kw in keywords:
            if kw not in index:
                index[kw] = set()
            index[kw].add(i)

    _keyword_index = index
    _indexed_recipes = sitemap_recipes
    print(f"  Indexed {len(sitemap_recipes)} recipes with {len(index)} unique keywords", flush=True)
    return index


def normalize_title(title: str) -> str:
    """Normalize a title for fuzzy comparison.

    Args:
        title: Raw title string

    Returns:
        Normalized lowercase string with common words removed
    """
    # Lowercase
    title = title.lower()

    # Remove common OCR artifacts and HelloFresh branding
    noise_patterns = [
        r"\bhello\b", r"\bfresh\b", r"\bgrab your\b", r"\bmeal kit\b",
        r"\bmeat kit\b", r"\bkit\b", r"@®", r"®", r"@",
    ]
    for pattern in noise_patterns:
        title = re.sub(pattern, "", title, flags=re.IGNORECASE)

    # Remove non-alphanumeric except spaces
    title = re.sub(r"[^a-z0-9\s]", " ", title)

    # Normalize whitespace
    title = " ".join(title.split())

    return title.strip()


def extract_keywords(title: str) -> set[str]:
    """Extract meaningful keywords from a title.

    Args:
        title: Normalized title string

    Returns:
        Set of keywords (words with 3+ chars)
    """
    words = normalize_title(title).split()
    # Keep words with 3+ chars, skip common words
    stop_words = {"and", "with", "the", "for", "your"}
    return {w for w in words if len(w) >= 3 and w not in stop_words}


def score_candidate(scanned_keywords: set[str], candidate_name: str) -> float:
    """Score how well a candidate matches scanned keywords.

    Args:
        scanned_keywords: Keywords from OCR'd title
        candidate_name: Recipe name from sitemap

    Returns:
        Score between 0 and 1
    """
    candidate_keywords = extract_keywords(candidate_name)

    if not scanned_keywords or not candidate_keywords:
        return 0.0

    # Count matching keywords
    matches = scanned_keywords & candidate_keywords

    # Score based on proportion of matches
    precision = len(matches) / len(scanned_keywords) if scanned_keywords else 0
    recall = len(matches) / len(candidate_keywords) if candidate_keywords else 0

    # F1 score
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


def prefilter_candidates(
    scanned_title: str,
    sitemap_recipes: list[dict],
    max_candidates: int = MAX_CANDIDATES_PER_TITLE,
) -> list[dict]:
    """Pre-filter sitemap to top candidates using keyword index.

    Args:
        scanned_title: OCR'd recipe title
        sitemap_recipes: All recipes from sitemap
        max_candidates: Maximum candidates to return

    Returns:
        Top candidates sorted by score
    """
    scanned_keywords = extract_keywords(scanned_title)

    if not scanned_keywords:
        return []

    # Build/get keyword index
    keyword_index = build_keyword_index(sitemap_recipes)

    # Find candidate indices using inverted index (fast!)
    candidate_indices: set[int] = set()
    for kw in scanned_keywords:
        if kw in keyword_index:
            candidate_indices.update(keyword_index[kw])

    if not candidate_indices:
        return []

    # Score only the candidates (not all 58K recipes)
    scored = []
    for idx in candidate_indices:
        recipe = sitemap_recipes[idx]
        score = score_candidate(scanned_keywords, recipe["name"])
        if score > 0.1:  # Minimum threshold
            scored.append((score, recipe))

    # Sort by score descending and take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:max_candidates]]


def create_matching_prompt(
    scanned_titles: list[str],
    sitemap_recipes: list[dict],
) -> str:
    """Create the prompt for LLM matching.

    Args:
        scanned_titles: List of OCR'd recipe titles
        sitemap_recipes: List of recipe dicts from sitemap

    Returns:
        Formatted prompt string
    """
    # Format scanned titles
    titles_section = "\n".join(
        f"{i+1}. {title}" for i, title in enumerate(scanned_titles)
    )

    # Format available recipes (name and URL)
    recipes_section = "\n".join(
        f"- {r['name']} | {r['url']}" for r in sitemap_recipes
    )

    return f"""You are matching OCR-scanned HelloFresh recipe titles to their official HelloFresh recipe URLs.

## Scanned Titles (may have OCR errors, typos, or partial text):
{titles_section}

## Available HelloFresh Recipes (Name | URL):
{recipes_section}

## Instructions:
For each scanned title, find the BEST matching HelloFresh recipe URL.

Consider these common OCR issues:
- Character substitutions: 0↔O, 1↔l↔I, 5↔S, 8↔B
- Missing/extra spaces
- Truncated words
- Minor spelling variations

Assign confidence levels:
- "high": Near-exact match, clearly the same recipe
- "medium": Likely match with minor differences
- "low": Possible match but uncertain
- null for matched_url if no reasonable match exists

## Response Format:
Return ONLY a JSON array (no markdown, no explanation):
[
  {{"index": 1, "scanned": "original title", "matched_url": "https://...", "matched_name": "Recipe Name", "confidence": "high"}},
  {{"index": 2, "scanned": "another title", "matched_url": null, "matched_name": null, "confidence": null}}
]"""


async def match_titles_batch(
    scanned_titles: list[str],
    sitemap_recipes: list[dict],
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """Match a batch of titles using Claude.

    Args:
        scanned_titles: List of OCR'd recipe titles
        sitemap_recipes: List of recipe dicts from sitemap
        model: Anthropic model to use

    Returns:
        List of match results
    """
    client = anthropic.Anthropic()

    prompt = create_matching_prompt(scanned_titles, sitemap_recipes)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse JSON response
    response_text = response.content[0].text.strip()

    # Handle potential markdown code blocks
    if response_text.startswith("```"):
        # Remove markdown code block
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        matches = json.loads(response_text)
        return matches
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse LLM response: {e}")
        print(f"Response was: {response_text[:500]}")
        return []


async def match_all_titles(
    scanned_titles: list[str],
    sitemap_recipes: list[dict],
    batch_size: int = DEFAULT_BATCH_SIZE,
    model: str = DEFAULT_MODEL,
    progress_callback: callable | None = None,
    use_prefilter: bool = True,
) -> list[dict]:
    """Match all scanned titles to sitemap recipes in batches.

    Args:
        scanned_titles: All OCR'd recipe titles
        sitemap_recipes: All recipes from sitemap
        batch_size: Number of titles per LLM request
        model: Anthropic model to use
        progress_callback: Optional callback(current, total)
        use_prefilter: Whether to prefilter candidates (recommended for large sitemaps)

    Returns:
        List of all match results
    """
    all_matches = []
    total = len(scanned_titles)

    # If sitemap is large, use fast prefiltering
    if use_prefilter and len(sitemap_recipes) > 500:
        print(f"  Pre-filtering {len(sitemap_recipes)} recipes...", flush=True)

        # Step 1: Fast prefilter ALL titles (uses inverted index)
        title_candidates: list[tuple[int, str, list[dict]]] = []
        skipped = 0

        for i, title in enumerate(scanned_titles):
            candidates = prefilter_candidates(title, sitemap_recipes)
            if candidates:
                title_candidates.append((i, title, candidates))
            else:
                skipped += 1
                all_matches.append({
                    "index": i + 1,
                    "scanned": title,
                    "matched_url": None,
                    "matched_name": None,
                    "confidence": None,
                })

        print(f"  Found candidates for {len(title_candidates)}/{total} titles ({skipped} skipped)", flush=True)

        # Step 2: Batch LLM calls - group titles with their candidates
        batch_num = 0
        total_batches = (len(title_candidates) + batch_size - 1) // batch_size

        for batch_start in range(0, len(title_candidates), batch_size):
            batch = title_candidates[batch_start:batch_start + batch_size]
            batch_num += 1

            # Combine all candidates from this batch (deduped by URL)
            combined_candidates: dict[str, dict] = {}
            batch_titles = []
            batch_indices = []

            for idx, title, candidates in batch:
                batch_titles.append(title)
                batch_indices.append(idx)
                for c in candidates:
                    combined_candidates[c["url"]] = c

            combined_list = list(combined_candidates.values())
            print(f"  Batch {batch_num}/{total_batches}: {len(batch_titles)} titles, {len(combined_list)} candidates", flush=True)

            if progress_callback:
                progress_callback(batch_start, len(title_candidates))

            try:
                batch_matches = await match_titles_batch(batch_titles, combined_list, model)

                # Fix indices and add to results
                for j, match in enumerate(batch_matches):
                    if j < len(batch_indices):
                        match["index"] = batch_indices[j] + 1
                    all_matches.append(match)

            except Exception as e:
                print(f"    Batch error: {e}", flush=True)
                # Add failed entries
                for idx, title, _ in batch:
                    all_matches.append({
                        "index": idx + 1,
                        "scanned": title,
                        "matched_url": None,
                        "matched_name": None,
                        "confidence": None,
                        "error": str(e),
                    })

        if progress_callback:
            progress_callback(total, total)

        # Sort by index before returning
        all_matches.sort(key=lambda x: x.get("index", 0))
        return all_matches

    # Original batch processing for smaller sitemaps
    for i in range(0, total, batch_size):
        batch = scanned_titles[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"  Matching batch {batch_num}/{total_batches} ({len(batch)} titles)...", flush=True)

        if progress_callback:
            progress_callback(i, total)

        matches = await match_titles_batch(batch, sitemap_recipes, model)
        all_matches.extend(matches)

    if progress_callback:
        progress_callback(total, total)

    return all_matches


def filter_matches_by_confidence(
    matches: list[dict],
    min_confidence: str = "medium",
) -> list[dict]:
    """Filter matches by minimum confidence level.

    Args:
        matches: List of match results
        min_confidence: Minimum confidence level (high, medium, low)

    Returns:
        Filtered list of matches
    """
    confidence_levels = {"high": 3, "medium": 2, "low": 1}
    min_level = confidence_levels.get(min_confidence, 2)

    return [
        m for m in matches
        if m.get("matched_url")
        and confidence_levels.get(m.get("confidence"), 0) >= min_level
    ]


def summarize_matches(matches: list[dict]) -> dict:
    """Summarize match results.

    Args:
        matches: List of match results

    Returns:
        Summary statistics
    """
    total = len(matches)
    matched = sum(1 for m in matches if m.get("matched_url"))
    unmatched = total - matched

    by_confidence = {"high": 0, "medium": 0, "low": 0}
    for m in matches:
        conf = m.get("confidence")
        if conf in by_confidence:
            by_confidence[conf] += 1

    return {
        "total": total,
        "matched": matched,
        "unmatched": unmatched,
        "match_rate": f"{matched/total*100:.1f}%" if total > 0 else "0%",
        "by_confidence": by_confidence,
    }


def save_matches(matches: list[dict], output_path: str | Path) -> None:
    """Save match results to JSON file.

    Args:
        matches: List of match results
        output_path: Path for output file
    """
    output_path = Path(output_path)

    with open(output_path, "w") as f:
        json.dump(matches, f, indent=2)

    summary = summarize_matches(matches)
    print(f"Saved {len(matches)} matches to {output_path}")
    print(f"  Matched: {summary['matched']}/{summary['total']} ({summary['match_rate']})")
    print(f"  By confidence: {summary['by_confidence']}")


def load_matches(input_path: str | Path) -> list[dict]:
    """Load match results from JSON file.

    Args:
        input_path: Path to matches JSON file

    Returns:
        List of match results
    """
    with open(input_path) as f:
        return json.load(f)


if __name__ == "__main__":
    import asyncio
    import sys

    # Simple test with mock data
    async def main():
        if len(sys.argv) < 2:
            print("Usage: python -m scripts.bulk_import_hellofresh.matcher <titles.json>")
            print("\nRunning with test data...")

            test_titles = [
                "Chicken Teriyaki Bowl",
                "Beef Tacos with Salsa",
                "Ch1cken Stir Fry",  # OCR error
            ]

            test_sitemap = [
                {"name": "Chicken Teriyaki Bowl With Rice", "url": "https://hellofresh.com.au/recipes/chicken-teriyaki-bowl-123"},
                {"name": "Beef Tacos With Fresh Salsa", "url": "https://hellofresh.com.au/recipes/beef-tacos-fresh-salsa-456"},
                {"name": "Chicken Stir Fry With Vegetables", "url": "https://hellofresh.com.au/recipes/chicken-stir-fry-789"},
            ]

            print(f"\nMatching {len(test_titles)} titles against {len(test_sitemap)} recipes...")
            matches = await match_all_titles(test_titles, test_sitemap)

            print("\nResults:")
            for m in matches:
                print(f"  '{m.get('scanned')}' → {m.get('matched_name')} [{m.get('confidence')}]")
            return

        # Load titles from file
        with open(sys.argv[1]) as f:
            data = json.load(f)

        titles = [item["title"] for item in data if item.get("title")]
        print(f"Loaded {len(titles)} titles from {sys.argv[1]}")

        # Would need sitemap data here
        print("Note: Sitemap data required for full matching. Use CLI for complete workflow.")

    asyncio.run(main())
