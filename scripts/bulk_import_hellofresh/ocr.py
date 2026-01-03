"""OCR extraction of recipe titles from scanned PDF files."""

import re
from pathlib import Path

try:
    from pdf2image import convert_from_path
    import pytesseract
    from PIL import Image
except ImportError as e:
    raise ImportError(
        "OCR dependencies not installed. Run: pip install 'mealie-mcp[bulk-import]'\n"
        f"Missing: {e.name}"
    ) from e


def extract_titles_from_pdf(
    pdf_path: str | Path,
    dpi: int = 300,
    first_n_lines: int = 3,
    min_title_length: int = 5,
    max_title_length: int = 100,
) -> list[dict]:
    """Extract recipe titles from a scanned PDF.

    HelloFresh recipe cards typically have the title prominently at the top.
    This function OCRs each page and extracts the likely title.

    Args:
        pdf_path: Path to the scanned PDF file
        dpi: DPI for PDF to image conversion (higher = better quality, slower)
        first_n_lines: Number of lines from top to consider for title
        min_title_length: Minimum characters for a valid title
        max_title_length: Maximum characters for a valid title

    Returns:
        List of dicts with page_number, raw_text, extracted_title
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    print(f"Converting PDF to images at {dpi} DPI...")
    images = convert_from_path(str(pdf_path), dpi=dpi)
    print(f"Processing {len(images)} pages...")

    results = []
    for i, image in enumerate(images, start=1):
        print(f"  OCR page {i}/{len(images)}...", end="\r")

        # OCR the full page
        raw_text = pytesseract.image_to_string(image)

        # Extract candidate title from first few lines
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        candidate_lines = lines[:first_n_lines]

        # Find best title candidate
        title = None
        for line in candidate_lines:
            # Clean up OCR artifacts
            cleaned = clean_ocr_text(line)

            # Check length constraints
            if min_title_length <= len(cleaned) <= max_title_length:
                # Skip lines that look like metadata (dates, numbers, etc.)
                if not looks_like_metadata(cleaned):
                    title = cleaned
                    break

        results.append({
            "page_number": i,
            "raw_text": raw_text[:500],  # First 500 chars for debugging
            "extracted_title": title,
            "candidate_lines": candidate_lines,
        })

    print(f"\nExtracted {sum(1 for r in results if r['extracted_title'])} titles from {len(images)} pages")
    return results


def extract_titles_from_images(
    image_paths: list[str | Path],
    first_n_lines: int = 3,
    min_title_length: int = 5,
    max_title_length: int = 100,
) -> list[dict]:
    """Extract recipe titles from individual image files.

    Args:
        image_paths: List of paths to image files
        first_n_lines: Number of lines from top to consider for title
        min_title_length: Minimum characters for a valid title
        max_title_length: Maximum characters for a valid title

    Returns:
        List of dicts with filename, raw_text, extracted_title
    """
    results = []

    for path in image_paths:
        path = Path(path)
        if not path.exists():
            print(f"  Warning: Image not found: {path}")
            continue

        print(f"  OCR {path.name}...", end="\r")

        image = Image.open(path)
        raw_text = pytesseract.image_to_string(image)

        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        candidate_lines = lines[:first_n_lines]

        title = None
        for line in candidate_lines:
            cleaned = clean_ocr_text(line)
            if min_title_length <= len(cleaned) <= max_title_length:
                if not looks_like_metadata(cleaned):
                    title = cleaned
                    break

        results.append({
            "filename": path.name,
            "raw_text": raw_text[:500],
            "extracted_title": title,
            "candidate_lines": candidate_lines,
        })

    print(f"\nExtracted {sum(1 for r in results if r['extracted_title'])} titles from {len(image_paths)} images")
    return results


def clean_ocr_text(text: str) -> str:
    """Clean common OCR artifacts from text.

    Args:
        text: Raw OCR text

    Returns:
        Cleaned text
    """
    # Common OCR substitutions
    replacements = [
        (r"[|]", "I"),  # | often misread as I
        (r"0(?=[a-zA-Z])", "O"),  # 0 before letter → O
        (r"(?<=[a-zA-Z])0", "O"),  # 0 after letter → O
        (r"1(?=[a-zA-Z])", "l"),  # 1 before letter → l
        (r"\s+", " "),  # Multiple spaces → single
    ]

    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)

    # Remove leading/trailing non-alphanumeric
    result = re.sub(r"^[^a-zA-Z0-9]+", "", result)
    result = re.sub(r"[^a-zA-Z0-9]+$", "", result)

    return result.strip()


def looks_like_metadata(text: str) -> bool:
    """Check if text looks like metadata rather than a recipe title.

    Args:
        text: Text to check

    Returns:
        True if text looks like metadata
    """
    # Patterns that indicate metadata, not title
    metadata_patterns = [
        r"^\d+$",  # Just numbers
        r"^[A-Z]{2,3}\s*\d+$",  # Code like "WK 23"
        r"^\d+\s*(min|minutes|mins)$",  # Time like "30 min"
        r"^(week|wk)\s*\d+",  # Week numbers
        r"^(serves?|serving)\s*\d+",  # Servings
        r"^\d+\s*cal",  # Calories
        r"^(easy|medium|hard)$",  # Difficulty
        r"^hellofresh",  # Brand name
        r"^\d{1,2}/\d{1,2}/\d{2,4}$",  # Date
    ]

    text_lower = text.lower()
    for pattern in metadata_patterns:
        if re.match(pattern, text_lower):
            return True

    return False


def save_titles_to_file(results: list[dict], output_path: str | Path) -> None:
    """Save extracted titles to a JSON file.

    Args:
        results: OCR results from extract_titles_from_pdf
        output_path: Path for output JSON file
    """
    import json

    output_path = Path(output_path)

    # Create simple list of titles for matching
    titles = [
        {
            "page": r.get("page_number", r.get("filename")),
            "title": r["extracted_title"],
        }
        for r in results
        if r["extracted_title"]
    ]

    with open(output_path, "w") as f:
        json.dump(titles, f, indent=2)

    print(f"Saved {len(titles)} titles to {output_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m scripts.bulk_import_hellofresh.ocr <pdf_file>")
        sys.exit(1)

    pdf_file = sys.argv[1]
    results = extract_titles_from_pdf(pdf_file)

    print("\nExtracted titles:")
    for r in results:
        title = r["extracted_title"] or "(no title found)"
        print(f"  Page {r['page_number']}: {title}")
