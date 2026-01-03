# LLM-Based OCR for Recipe Cards

This directory contains improved OCR tools using Claude's vision capabilities to extract recipe titles from HelloFresh recipe card PDFs.

## Why LLM-Based OCR?

Traditional OCR (pytesseract) struggles with:
- Decorative fonts and typography
- Text overlays on images
- Poor scan quality
- Complex layouts

**Results from traditional OCR:**
- 45/272 recipes had poor quality extraction (16.5% failure rate)
- Common failures: "Grab your", "HELLO", "with this symbol"

**LLM vision models** (Claude 3.5 Haiku) excel at:
- Understanding context and ignoring decorative elements
- Extracting clean text from complex layouts
- Providing confidence scores
- Handling varied image quality

## Cost Comparison

| Method | Cost per 100 images | Quality |
|--------|-------------------|---------|
| pytesseract | Free | 83.5% success |
| Claude Haiku | ~$0.01 | ~95%+ expected |

For 272 recipe cards: **~$0.03 total cost**

## Files

- `ocr_llm.py` - Core LLM-based OCR module using Claude vision
- `test_llm_ocr.py` - Test script for chicken recipes (19 bad OCR cases)
- `batch_llm_ocr.py` - Batch process all PDFs

## Usage

### Test on Single PDF

```bash
cd scripts/bulk_import_hellofresh
python test_llm_ocr.py
```

This will:
1. Re-OCR chicken recipes PDF
2. Compare with original OCR results
3. Show improvements on failed cases
4. Save to `recipes/chicken_titles_llm.json`

### Batch Process All PDFs

```bash
cd scripts/bulk_import_hellofresh
python batch_llm_ocr.py
```

This will:
1. Process all 5 PDFs (chicken, beef, veggie, seafood, lamb)
2. Extract titles with confidence scores
3. Save individual `*_titles_llm.json` files
4. Show summary statistics

### Run Matching on LLM Results

```bash
# Match LLM-extracted titles against sitemap
python matcher.py ../../recipes/chicken_titles_llm.json chicken_matches_llm.json

# Combine all matches
python -c "
import json
from pathlib import Path

all_matches = []
for f in ['chicken', 'beef', 'veggie', 'seafood', 'lamb']:
    with open(f'recipes/{f}_matches_llm.json') as file:
        all_matches.extend(json.load(file))

with open('recipes/all_matches_llm.json', 'w') as f:
    json.dump(all_matches, f, indent=2)
print(f'Combined {len(all_matches)} matches')
"

# Import newly matched recipes
python importer.py ../../recipes/all_matches_llm.json
```

## Expected Improvements

Based on the 45 poor OCR cases:

| Metric | Original OCR | LLM OCR (expected) |
|--------|-------------|-------------------|
| Extraction success | 227/272 (83.5%) | ~260/272 (95.6%) |
| High confidence | ~191 (70.2%) | ~240 (88.2%) |
| Total imports | 140 (51.5%) | ~170+ (62.5%+) |

**Additional recipes recovered:** ~30-40 recipes from the 45 failed cases

## Configuration

Environment variables (in `.env`):
```bash
ANTHROPIC_API_KEY=your-key-here
```

Model selection:
- `claude-3-5-haiku-20241022` (default) - Fast, cheap, excellent quality
- `claude-3-5-sonnet-20241022` - Higher quality, 10x more expensive (overkill)

DPI settings:
- 200 DPI (default) - Sufficient for Claude vision
- 300 DPI - Higher quality but slower, minimal improvement

## Troubleshooting

**Rate limits:**
- Haiku: 10,000 requests/min (no issue for 272 images)
- Add delays if hitting rate limits: `time.sleep(0.1)` between images

**Image too large:**
- Claude accepts images up to 5MB
- PDFs at 200 DPI should be well under this limit
- Reduce DPI to 150 if needed

**JSON parsing errors:**
- Claude occasionally wraps JSON in markdown code blocks
- The code handles this automatically
- If persistent, check `raw_response` field

## Performance Monitoring

The scripts track:
- Titles extracted vs. total pages
- Confidence distribution (high/medium/low)
- Processing time per page
- Estimated API costs

Sample output:
```
Completed: Extracted 106 titles from 106 pages
  Confidence: 98 high, 7 medium, 1 low
```
