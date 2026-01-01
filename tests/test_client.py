"""Tests for the Mealie API client."""

import pytest
from pytest_httpx import HTTPXMock

from mealie_mcp.client import MealieClient
from mealie_mcp.models import ErrorResponse


@pytest.fixture
def client():
    """Create a test client."""
    return MealieClient(
        base_url="http://test-mealie:9000/api",
        token="test-token",
    )


class TestRecipes:
    """Tests for recipe-related API calls."""

    @pytest.mark.asyncio
    async def test_search_recipes_success(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test successful recipe search."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-mealie:9000/api/recipes?page=1&perPage=20",
            json={
                "items": [
                    {
                        "id": "recipe-1",
                        "slug": "spaghetti-carbonara",
                        "name": "Spaghetti Carbonara",
                        "description": "Classic Italian pasta",
                        "tags": [],
                        "recipeCategory": [],
                    }
                ],
                "page": 1,
                "perPage": 20,
                "total": 1,
                "totalPages": 1,
            },
        )

        result = await client.search_recipes()
        assert len(result) == 1
        assert result[0].slug == "spaghetti-carbonara"
        assert result[0].name == "Spaghetti Carbonara"

    @pytest.mark.asyncio
    async def test_search_recipes_with_filters(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test recipe search with query and filters."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-mealie:9000/api/recipes?page=1&perPage=10&search=pasta&tags=italian",
            json={"items": [], "page": 1, "perPage": 10, "total": 0, "totalPages": 0},
        )

        result = await client.search_recipes(
            query="pasta",
            tags=["italian"],
            per_page=10,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_get_recipe_success(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test getting a single recipe."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-mealie:9000/api/recipes/spaghetti-carbonara",
            json={
                "id": "recipe-1",
                "slug": "spaghetti-carbonara",
                "name": "Spaghetti Carbonara",
                "description": "Classic Italian pasta",
                "recipeIngredient": [
                    {"quantity": 400, "unit": "g", "food": "spaghetti"},
                    {"quantity": 200, "unit": "g", "food": "pancetta"},
                ],
                "recipeInstructions": [
                    {"id": "1", "text": "Boil pasta"},
                    {"id": "2", "text": "Fry pancetta"},
                ],
                "tags": [],
                "recipeCategory": [],
            },
        )

        result = await client.get_recipe("spaghetti-carbonara")
        assert result.name == "Spaghetti Carbonara"
        assert len(result.recipe_ingredient) == 2
        assert len(result.recipe_instructions) == 2

    @pytest.mark.asyncio
    async def test_get_recipe_not_found(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test getting a non-existent recipe."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-mealie:9000/api/recipes/nonexistent",
            status_code=404,
        )

        result = await client.get_recipe("nonexistent")
        assert isinstance(result, ErrorResponse)
        assert result.code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_list_tags(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test listing all tags."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-mealie:9000/api/organizers/tags",
            json={
                "items": [
                    {"id": "tag-1", "slug": "quick", "name": "Quick"},
                    {"id": "tag-2", "slug": "vegetarian", "name": "Vegetarian"},
                ]
            },
        )

        result = await client.list_tags()
        assert len(result) == 2
        assert result[0].slug == "quick"


class TestMealPlans:
    """Tests for meal plan API calls."""

    @pytest.mark.asyncio
    async def test_get_meal_plan(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test getting meal plan for a date range."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-mealie:9000/api/households/mealplans?start_date=2026-01-01&end_date=2026-01-07",
            json={
                "items": [
                    {
                        "id": "entry-1",
                        "date": "2026-01-01",
                        "entryType": "dinner",
                        "recipeId": "recipe-1",
                        "recipe": {
                            "id": "recipe-1",
                            "slug": "spaghetti-carbonara",
                            "name": "Spaghetti Carbonara",
                        },
                    }
                ]
            },
        )

        result = await client.get_meal_plan("2026-01-01", "2026-01-07")
        assert len(result) == 1
        assert result[0].entry_type.value == "dinner"
        assert result[0].recipe.name == "Spaghetti Carbonara"

    @pytest.mark.asyncio
    async def test_create_meal_plan_entry(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test creating a meal plan entry."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-mealie:9000/api/households/mealplans",
            json={
                "id": "new-entry",
                "date": "2026-01-05",
                "entryType": "lunch",
                "recipeId": "recipe-1",
            },
        )

        result = await client.create_meal_plan_entry(
            date="2026-01-05",
            recipe_id="recipe-1",
            entry_type="lunch",
        )
        assert result.id == "new-entry"
        assert result.entry_type.value == "lunch"

    @pytest.mark.asyncio
    async def test_delete_meal_plan_entry(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test deleting a meal plan entry."""
        httpx_mock.add_response(
            method="DELETE",
            url="http://test-mealie:9000/api/households/mealplans/entry-1",
            status_code=204,
        )

        result = await client.delete_meal_plan_entry("entry-1")
        assert result["success"] is True


class TestShoppingLists:
    """Tests for shopping list API calls."""

    @pytest.mark.asyncio
    async def test_get_shopping_lists(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test getting all shopping lists."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-mealie:9000/api/households/shopping/lists",
            json={
                "items": [
                    {"id": "list-1", "name": "Weekly Groceries"},
                    {"id": "list-2", "name": "Party Supplies"},
                ]
            },
        )

        result = await client.get_shopping_lists()
        assert len(result) == 2
        assert result[0].name == "Weekly Groceries"

    @pytest.mark.asyncio
    async def test_get_shopping_list(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test getting a specific shopping list."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-mealie:9000/api/households/shopping/lists/list-1",
            json={
                "id": "list-1",
                "name": "Weekly Groceries",
                "listItems": [
                    {"id": "item-1", "shoppingListId": "list-1", "note": "Milk", "checked": False},
                    {"id": "item-2", "shoppingListId": "list-1", "note": "Eggs", "checked": True},
                ],
            },
        )

        result = await client.get_shopping_list("list-1")
        assert result.name == "Weekly Groceries"
        assert len(result.list_items) == 2

    @pytest.mark.asyncio
    async def test_add_shopping_list_item(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test adding an item to a shopping list."""
        httpx_mock.add_response(
            method="POST",
            url="http://test-mealie:9000/api/households/shopping/lists/list-1/items",
            json={
                "id": "new-item",
                "shoppingListId": "list-1",
                "note": "2 cups flour",
                "quantity": 1,
                "checked": False,
            },
        )

        result = await client.add_shopping_list_item("list-1", "2 cups flour")
        assert result.id == "new-item"
        assert result.note == "2 cups flour"


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_auth_error(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test handling of authentication errors."""
        httpx_mock.add_response(
            method="GET",
            url="http://test-mealie:9000/api/recipes?page=1&perPage=20",
            status_code=401,
        )

        result = await client.search_recipes()
        assert isinstance(result, ErrorResponse)
        assert result.code == "AUTH_ERROR"

    @pytest.mark.asyncio
    async def test_connection_error(self, client: MealieClient, httpx_mock: HTTPXMock):
        """Test handling of connection errors."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        result = await client.search_recipes()
        assert isinstance(result, ErrorResponse)
        assert result.code == "API_ERROR"
        assert "Cannot connect" in result.message
