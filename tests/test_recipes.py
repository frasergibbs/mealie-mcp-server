"""Tests for recipe MCP tools."""

from unittest.mock import AsyncMock, patch

import pytest

from mealie_mcp.models import Category, ErrorResponse, Recipe, RecipeSummary, Tag
from mealie_mcp.tools.recipes import get_recipe, list_categories, list_tags, search_recipes


@pytest.fixture
def mock_client():
    """Create a mock Mealie client."""
    with patch("mealie_mcp.tools.recipes.get_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


class TestSearchRecipes:
    """Tests for search_recipes tool."""

    @pytest.mark.asyncio
    async def test_search_recipes_returns_formatted_results(self, mock_client):
        """Test that search results are properly formatted."""
        mock_client.search_recipes.return_value = [
            RecipeSummary(
                id="recipe-1",
                slug="spaghetti-carbonara",
                name="Spaghetti Carbonara",
                description="Classic Italian pasta",
                tags=[Tag(id="t1", slug="italian", name="Italian")],
                recipeCategory=[Category(id="c1", slug="dinner", name="Dinner")],
                totalTime="30 minutes",
                rating=5,
            )
        ]

        result = await search_recipes(query="pasta")

        assert len(result) == 1
        assert result[0]["name"] == "Spaghetti Carbonara"
        assert result[0]["tags"] == ["Italian"]
        assert result[0]["categories"] == ["Dinner"]

    @pytest.mark.asyncio
    async def test_search_recipes_handles_error(self, mock_client):
        """Test error handling in search."""
        mock_client.search_recipes.return_value = ErrorResponse.api_error("Connection failed")

        result = await search_recipes()

        assert result["error"] is True
        assert result["code"] == "API_ERROR"


class TestGetRecipe:
    """Tests for get_recipe tool."""

    @pytest.mark.asyncio
    async def test_get_recipe_returns_full_details(self, mock_client):
        """Test that full recipe details are returned."""
        from mealie_mcp.models import RecipeIngredient, RecipeInstruction

        mock_client.get_recipe.return_value = Recipe(
            id="recipe-1",
            slug="test-recipe",
            name="Test Recipe",
            description="A test recipe",
            recipeYield="4 servings",
            prepTime="10 min",
            cookTime="20 min",
            totalTime="30 min",
            recipeIngredient=[
                RecipeIngredient(quantity=2, unit="cups", food="flour"),
                RecipeIngredient(quantity=1, unit="tsp", food="salt"),
            ],
            recipeInstructions=[
                RecipeInstruction(id="1", text="Mix ingredients"),
                RecipeInstruction(id="2", text="Bake at 350F"),
            ],
            tags=[],
            recipeCategory=[],
        )

        result = await get_recipe("test-recipe")

        assert result["name"] == "Test Recipe"
        assert len(result["ingredients"]) == 2
        assert len(result["instructions"]) == 2
        assert result["instructions"][0]["step"] == 1


class TestListTags:
    """Tests for list_tags tool."""

    @pytest.mark.asyncio
    async def test_list_tags_returns_formatted_list(self, mock_client):
        """Test that tags are properly formatted."""
        mock_client.list_tags.return_value = [
            Tag(id="t1", slug="quick", name="Quick"),
            Tag(id="t2", slug="vegetarian", name="Vegetarian"),
        ]

        result = await list_tags()

        assert len(result) == 2
        assert result[0]["slug"] == "quick"
        assert result[1]["name"] == "Vegetarian"


class TestListCategories:
    """Tests for list_categories tool."""

    @pytest.mark.asyncio
    async def test_list_categories_returns_formatted_list(self, mock_client):
        """Test that categories are properly formatted."""
        mock_client.list_categories.return_value = [
            Category(id="c1", slug="dinner", name="Dinner"),
            Category(id="c2", slug="desserts", name="Desserts"),
        ]

        result = await list_categories()

        assert len(result) == 2
        assert result[0]["slug"] == "dinner"
