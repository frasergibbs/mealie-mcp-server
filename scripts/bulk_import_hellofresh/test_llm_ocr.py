#!/usr/bin/env python3
"""Test LLM-based OCR on a sample of failed recipes."""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ocr_llm import extract_titles_from_pdf_llm


def main():
    """Re-OCR PDFs with poor traditional OCR results."""
    
    # Test with chicken recipes (19 bad OCR results)
    pdf_path = Path("../../recipes/Hello-Fresh-Chicken.pdf")
    
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        print("Please ensure PDFs are in the recipes directory")
        return
    
    print("=" * 70)
    print("LLM-BASED OCR TEST")
    print("=" * 70)
    print(f"\nProcessing: {pdf_path}")
    print("This will use Claude Haiku vision to extract recipe titles...")
    print("Expected improvement: ~45 failed titles → high-quality extraction\n")
    
    # Extract titles using LLM
    results = extract_titles_from_pdf_llm(
        pdf_path,
        dpi=200,  # Lower DPI is fine for Claude vision
        model="claude-3-5-haiku-20241022"
    )
    
    # Load original OCR results for comparison
    original_file = Path("../../recipes/chicken_titles.json")
    if original_file.exists():
        with open(original_file) as f:
            original_results = json.load(f)
        
        print("\n" + "=" * 70)
        print("COMPARISON WITH ORIGINAL OCR")
        print("=" * 70)
        
        improvements = 0
        for llm_result in results[:20]:  # Show first 20
            page = llm_result['page_number']
            llm_title = llm_result.get('extracted_title', 'NO_TITLE')
            
            # Find original result
            orig_result = next((r for r in original_results if r['page'] == page), None)
            orig_title = orig_result.get('title', 'NO_TITLE') if orig_result else 'NO_TITLE'
            
            # Check if this was a bad OCR case
            was_bad = (len(orig_title) < 15 or 
                      any(x in orig_title.lower() for x in ['grab your', 'hello fresh', 'meal kit', 'cook time', 'with this']))
            
            if was_bad and llm_title and llm_title != 'NO_TITLE_FOUND':
                print(f"\n✓ Page {page} IMPROVED:")
                print(f"  Old: \"{orig_title}\"")
                print(f"  New: \"{llm_title}\" ({llm_result.get('confidence')})")
                improvements += 1
            elif not was_bad:
                # Show a few good matches for comparison
                if page <= 5:
                    print(f"\n  Page {page}:")
                    print(f"  Old: \"{orig_title}\"")
                    print(f"  New: \"{llm_title}\" ({llm_result.get('confidence')})")
        
        print(f"\n\nImproved {improvements} titles out of ~19 bad OCR cases in first 20 pages")
    
    # Save results
    output_file = Path("../../recipes/chicken_titles_llm.json")
    formatted = [
        {
            "index": r["page_number"],
            "title": r["extracted_title"] or "NO_TITLE_FOUND",
            "confidence": r["confidence"],
            "page": r["page_number"],
        }
        for r in results
    ]
    
    with open(output_file, "w") as f:
        json.dump(formatted, f, indent=2)
    
    print(f"\n\nSaved LLM OCR results to: {output_file}")
    print("\nNext steps:")
    print("  1. Review the results in recipes/chicken_titles_llm.json")
    print("  2. If quality is good, run matcher.py with the new titles")
    print("  3. Import newly matched recipes with importer.py")


if __name__ == "__main__":
    main()
