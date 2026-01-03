#!/usr/bin/env python3
"""Fast LLM OCR using cached images (no PDF re-conversion needed)."""

import json
from pathlib import Path
from PIL import Image
from anthropic import Anthropic
import sys

sys.path.insert(0, str(Path(__file__).parent))
from ocr_llm import extract_title_with_claude


def main():
    """Run LLM OCR on cached images."""
    
    # First, let's save images from PDFs to a cache directory
    script_dir = Path(__file__).parent
    cache_dir = script_dir / ".image_cache"
    cache_dir.mkdir(exist_ok=True)
    
    recipes_dir = script_dir.parent.parent / "recipes"
    
    print("=" * 70)
    print("FAST LLM OCR (Using Image Cache)")
    print("=" * 70)
    
    # Check if we need to extract images
    pdfs = {
        recipes_dir / "Hello-Fresh-Chicken.pdf": "chicken",
        recipes_dir / "Hello-Fresh-Beef.pdf": "beef",
        recipes_dir / "Hello-Fresh-Veggie.pdf": "veggie",
        recipes_dir / "Hello-Fresh-Seafood.pdf": "seafood",
        recipes_dir / "Hello-Fresh-Lamb.pdf": "lamb",
    }
    
    client = Anthropic()
    
    for pdf_path, source in pdfs.items():
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            print(f"\nSkipping {source} - PDF not found")
            continue
        
        source_cache = cache_dir / source
        
        # Check if images are already cached
        if source_cache.exists() and list(source_cache.glob("*.png")):
            print(f"\n✓ Using cached images for {source}")
            images = sorted(source_cache.glob("*.png"))
        else:
            print(f"\nConverting {source} PDF to images (one-time)...")
            source_cache.mkdir(exist_ok=True)
            
            from pdf2image import convert_from_path
            pil_images = convert_from_path(str(pdf_file), dpi=200)
            
            # Save for future use
            images = []
            for i, img in enumerate(pil_images, 1):
                img_path = source_cache / f"page_{i:03d}.png"
                img.save(img_path, "PNG")
                images.append(img_path)
            
            print(f"  Saved {len(images)} images to cache")
        
        # Now process with Claude
        print(f"Processing {len(images)} pages with Claude vision...")
        
        results = []
        for i, img_path in enumerate(images, 1):
            print(f"  Page {i}/{len(images)}...", end="\r")
            
            image = Image.open(img_path)
            result = extract_title_with_claude(image, client)
            result["page_number"] = i
            results.append(result)
            
            if i % 10 == 0:
                successful = sum(1 for r in results if r.get("extracted_title"))
                print(f"  Progress: {i}/{len(images)} pages, {successful} titles extracted")
        
        print(f"\n  Completed: {sum(1 for r in results if r['extracted_title'])}/{len(images)} titles")
        
        # Save results
        formatted = [
            {
                "index": r["page_number"],
                "title": r["extracted_title"] or "NO_TITLE_FOUND",
                "confidence": r["confidence"],
                "page": r["page_number"],
            }
            for r in results
        ]
        
        output_file = recipes_dir / f"{source}_titles_llm.json"
        with open(output_file, "w") as f:
            json.dump(formatted, f, indent=2)
        
        print(f"  Saved to: {output_file}")
        
        # Show confidence breakdown
        high = sum(1 for r in results if r.get("confidence") == "high")
        medium = sum(1 for r in results if r.get("confidence") == "medium")
        low = sum(1 for r in results if r.get("confidence") == "low")
        print(f"  Confidence: {high} high, {medium} medium, {low} low")
    
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("\n1. Run matcher on LLM results:")
    print("   python matcher.py ../../recipes/chicken_titles_llm.json ../../recipes/chicken_matches_llm.json")
    print("\n2. Compare with original matches to see improvements")


if __name__ == "__main__":
    main()
