"""LLM-based OCR extraction of recipe titles from scanned PDF files.

This module uses Claude's vision capabilities for more accurate text extraction
compared to traditional OCR tools like pytesseract.
"""

import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Any

try:
    from pdf2image import convert_from_path
    from PIL import Image
    from anthropic import Anthropic
except ImportError as e:
    raise ImportError(
        f"Required dependencies not installed. Run: pip install pdf2image pillow anthropic\n"
        f"Missing: {e.name}"
    ) from e

from dotenv import load_dotenv

load_dotenv()


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """Convert PIL Image to base64 string."""
    buffer = BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode()


def extract_title_with_claude(
    image: Image.Image,
    client: Anthropic,
    model: str = "claude-3-5-haiku-20241022",
) -> dict[str, Any]:
    """Extract recipe title from image using Claude vision.

    Args:
        image: PIL Image of the recipe card
        client: Anthropic client instance
        model: Claude model to use (haiku is cost-effective for this task)

    Returns:
        Dict with extracted_title and confidence (high/medium/low)
    """
    # Convert image to base64
    image_data = image_to_base64(image, format="PNG")

    # Prompt Claude to extract the title
    prompt = """You are analyzing a HelloFresh recipe card image. 

Your task is to extract ONLY the recipe title. The title is usually:
- At the top of the card in large, bold text
- The main dish name (e.g., "Honey Garlic Chicken & Veggie Rice")
- May include protein, preparation style, and sides

DO NOT include:
- "HELLO" or "HelloFresh" branding
- Cook time, difficulty level, or serving size
- "Grab your Meal Kit" or similar instructions
- Ingredient lists or instructions
- Icons, symbols, or decorative elements

Return your response as JSON with this exact format:
{
  "title": "The exact recipe title",
  "confidence": "high|medium|low"
}

Set confidence to:
- "high": Title is clear and fully readable
- "medium": Some minor OCR uncertainty but title is mostly clear
- "low": Image quality poor or title obscured
- If no title is visible, return {"title": null, "confidence": "low"}
"""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        # Parse response
        response_text = response.content[0].text.strip()
        
        # Extract JSON from response (Claude might wrap it in markdown)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response_text)
        
        return {
            "extracted_title": result.get("title"),
            "confidence": result.get("confidence", "low"),
            "raw_response": response.content[0].text,
        }

    except Exception as e:
        return {
            "extracted_title": None,
            "confidence": "low",
            "error": str(e),
        }


def extract_titles_from_pdf_llm(
    pdf_path: str | Path,
    dpi: int = 300,
    model: str = "claude-3-5-haiku-20241022",
    batch_size: int = 10,
) -> list[dict]:
    """Extract recipe titles from PDF using Claude vision.

    Args:
        pdf_path: Path to the scanned PDF file
        dpi: DPI for PDF to image conversion (higher = better quality)
        model: Claude model to use
        batch_size: Process images in batches with progress updates

    Returns:
        List of dicts with page_number, extracted_title, confidence
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    client = Anthropic()  # Uses ANTHROPIC_API_KEY from environment

    print(f"Converting PDF to images at {dpi} DPI...")
    images = convert_from_path(str(pdf_path), dpi=dpi)
    print(f"Processing {len(images)} pages with Claude vision...")

    results = []
    for i, image in enumerate(images, start=1):
        print(f"  Processing page {i}/{len(images)}...", end="\r")

        result = extract_title_with_claude(image, client, model)
        result["page_number"] = i
        results.append(result)

        # Show progress every batch_size pages
        if i % batch_size == 0:
            successful = sum(1 for r in results if r.get("extracted_title"))
            print(f"\n  Progress: {i}/{len(images)} pages, {successful} titles extracted")

    print(f"\nCompleted: Extracted {sum(1 for r in results if r['extracted_title'])} titles from {len(images)} pages")
    
    # Print confidence breakdown
    high = sum(1 for r in results if r.get("confidence") == "high")
    medium = sum(1 for r in results if r.get("confidence") == "medium")
    low = sum(1 for r in results if r.get("confidence") == "low")
    print(f"  Confidence: {high} high, {medium} medium, {low} low")

    return results


def extract_titles_from_images_llm(
    image_paths: list[str | Path],
    model: str = "claude-3-5-haiku-20241022",
) -> list[dict]:
    """Extract recipe titles from individual images using Claude vision.

    Args:
        image_paths: List of paths to image files
        model: Claude model to use

    Returns:
        List of dicts with filename, extracted_title, confidence
    """
    client = Anthropic()
    results = []

    for i, path in enumerate(image_paths, start=1):
        path = Path(path)
        if not path.exists():
            print(f"  Warning: Image not found: {path}")
            continue

        print(f"  Processing {path.name} ({i}/{len(image_paths)})...", end="\r")

        image = Image.open(path)
        result = extract_title_with_claude(image, client, model)
        result["filename"] = path.name
        result["path"] = str(path)
        results.append(result)

    print(f"\nExtracted {sum(1 for r in results if r['extracted_title'])} titles from {len(image_paths)} images")
    return results


if __name__ == "__main__":
    import sys
    from datetime import datetime

    if len(sys.argv) < 2:
        print("Usage: python ocr_llm.py <pdf_file> [output.json]")
        sys.exit(1)

    pdf_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    # Extract titles
    results = extract_titles_from_pdf_llm(pdf_file)

    # Format for matching (compatible with existing matcher)
    formatted = [
        {
            "index": r["page_number"],
            "title": r["extracted_title"] or "NO_TITLE_FOUND",
            "confidence": r["confidence"],
            "page": r["page_number"],
        }
        for r in results
    ]

    # Save results
    if output_file:
        output_path = Path(output_file)
    else:
        pdf_name = Path(pdf_file).stem
        output_path = Path(f"{pdf_name}_titles_llm.json")

    with open(output_path, "w") as f:
        json.dump(formatted, f, indent=2)

    print(f"\nSaved results to: {output_path}")
    
    # Show sample
    print("\nSample titles:")
    for r in formatted[:5]:
        print(f"  Page {r['page']}: {r['title']} ({r['confidence']})")
