#!/usr/bin/env python3
"""Batch re-OCR all PDFs using LLM vision for improved accuracy."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ocr_llm import extract_titles_from_pdf_llm


def main():
    """Re-OCR all PDF files with LLM vision."""
    
    pdfs = {
        "../../recipes/Hello-Fresh-Chicken.pdf": "chicken",
        "../../recipes/Hello-Fresh-Beef.pdf": "beef",
        "../../recipes/Hello-Fresh-Veggie.pdf": "veggie",
        "../../recipes/Hello-Fresh-Seafood.pdf": "seafood",
        "../../recipes/Hello-Fresh-Lamb.pdf": "lamb",
    }
    
    print("=" * 70)
    print("BATCH LLM-BASED OCR")
    print("=" * 70)
    print(f"\nWill process {len(pdfs)} PDF files")
    print("Using: Claude 3.5 Haiku (cost-effective vision model)")
    print("Estimated cost: ~$0.01 per 100 images ($0.25 per 1M input tokens)\n")
    
    # Estimate total pages
    total_pages = 272  # We know this from the original import
    estimated_cost = (total_pages / 100) * 0.01
    print(f"Estimated total cost: ~${estimated_cost:.2f} for {total_pages} pages\n")
    
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled")
        return
    
    all_results = {}
    
    for pdf_name, source in pdfs.items():
        pdf_path = Path(pdf_name)
        
        if not pdf_path.exists():
            print(f"\n⚠ Skipping {pdf_name} - file not found")
            continue
        
        print(f"\n{'=' * 70}")
        print(f"Processing: {source.upper()} ({pdf_name})")
        print('=' * 70)
        
        # Extract titles
        results = extract_titles_from_pdf_llm(
            pdf_path,
            dpi=200,  # Lower DPI is sufficient for Claude
            model="claude-3-5-haiku-20241022",
            batch_size=10
        )
        
        # Format results
        formatted = [
            {
                "index": r["page_number"],
                "title": r["extracted_title"] or "NO_TITLE_FOUND",
                "confidence": r["confidence"],
                "page": r["page_number"],
            }
            for r in results
        ]
        
        # Save individual file
        output_file = Path(f"../../recipes/{source}_titles_llm.json")
        with open(output_file, "w") as f:
            json.dump(formatted, f, indent=2)
        
        print(f"✓ Saved to: {output_file}")
        all_results[source] = formatted
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total_extracted = 0
    high_conf = 0
    medium_conf = 0
    low_conf = 0
    
    for source, results in all_results.items():
        extracted = sum(1 for r in results if r['title'] != 'NO_TITLE_FOUND')
        high = sum(1 for r in results if r['confidence'] == 'high')
        medium = sum(1 for r in results if r['confidence'] == 'medium')
        low = sum(1 for r in results if r['confidence'] == 'low')
        
        total_extracted += extracted
        high_conf += high
        medium_conf += medium
        low_conf += low
        
        print(f"\n{source.capitalize()}:")
        print(f"  Titles extracted: {extracted}/{len(results)}")
        print(f"  Confidence: {high} high, {medium} medium, {low} low")
    
    print(f"\nOverall:")
    print(f"  Total titles: {total_extracted}")
    print(f"  High confidence: {high_conf}")
    print(f"  Medium confidence: {medium_conf}")
    print(f"  Low confidence: {low_conf}")
    
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("\n1. Review LLM OCR results in recipes/*_titles_llm.json")
    print("2. Run matcher.py with new titles to find matches:")
    print("   python matcher.py recipes/chicken_titles_llm.json chicken_matches_llm.json")
    print("3. Compare match rates with original OCR")
    print("4. Import newly matched recipes with importer.py")


if __name__ == "__main__":
    main()
