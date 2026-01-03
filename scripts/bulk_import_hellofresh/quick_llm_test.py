#!/usr/bin/env python3
"""Quick test of LLM-based OCR on a few failed recipe pages."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ocr_llm import extract_title_with_claude
from pdf2image import convert_from_path
from anthropic import Anthropic


def main():
    """Test LLM OCR on specific failed pages."""
    
    # Load original chicken results to find bad OCR pages
    with open("../../recipes/chicken_titles.json") as f:
        original = json.load(f)
    
    # Find pages with bad OCR
    bad_pages = []
    for r in original:
        title = r.get('title', '')
        page = r.get('page', 0)
        if (len(title) < 15 or 
            any(x in title.lower() for x in ['grab your', 'hello fresh', 'meal kit', 'cook time', 'with this'])):
            bad_pages.append(page)
    
    print("=" * 70)
    print("LLM OCR QUICK TEST")
    print("=" * 70)
    print(f"\nFound {len(bad_pages)} pages with poor OCR")
    print(f"Testing first 5 bad pages: {bad_pages[:5]}\n")
    
    # Convert PDF to images (only the bad pages)
    pdf_path = Path("../../recipes/Hello-Fresh-Chicken.pdf")
    print(f"Converting pages from PDF...")
    
    # Convert only first 30 pages to limit processing time
    images = convert_from_path(str(pdf_path), dpi=200, first_page=1, last_page=30)
    
    client = Anthropic()
    
    # Test on first 5 bad OCR pages
    results = []
    for page_num in bad_pages[:5]:
        if page_num > len(images):
            continue
            
        orig = next((r for r in original if r['page'] == page_num), None)
        
        print(f"\nPage {page_num}:")
        print(f"  Original OCR: \"{orig.get('title', 'N/A')}\"")
        print(f"  Processing with Claude...", end="")
        
        # Extract with LLM
        image = images[page_num - 1]
        llm_result = extract_title_with_claude(image, client)
        
        print(f" Done!")
        print(f"  LLM Result: \"{llm_result.get('extracted_title', 'N/A')}\"")
        print(f"  Confidence: {llm_result.get('confidence', 'unknown')}")
        
        results.append({
            'page': page_num,
            'original': orig.get('title', ''),
            'llm': llm_result.get('extracted_title', ''),
            'confidence': llm_result.get('confidence', '')
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    improved = sum(1 for r in results if r['llm'] and len(r['llm']) > 15)
    
    print(f"\nImproved: {improved}/{len(results)} pages")
    print("\nQuality looks good? Run the full batch with:")
    print("  python batch_llm_ocr.py")


if __name__ == "__main__":
    main()
