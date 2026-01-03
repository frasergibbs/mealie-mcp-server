"""Quick test of deduplication logic."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from mealie_mcp.client import MealieClient


async def test_dedup():
    """Test the deduplication check."""
    from importer import check_recipe_exists
    
    client = MealieClient()
    
    # Test with a URL that should exist if you have any recipes imported
    test_url = "https://www.hellofresh.com/recipes/all-american-honey-chicken-66ce94d39b6b80f1c74fb5e3"
    
    print(f"Checking if recipe exists: {test_url}")
    result = await check_recipe_exists(client, test_url)
    
    if result:
        print(f"✓ Recipe exists: {result}")
    else:
        print("○ Recipe not found in database")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(test_dedup())
