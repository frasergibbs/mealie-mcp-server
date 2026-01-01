"""Tests for meal plan MCP tools."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from mealie_mcp.models import ErrorResponse, MealPlanEntry, MealType, RecipeSummary
from mealie_mcp.tools.mealplans import (
    create_meal_plan_entry,
    delete_meal_plan_entry,
    get_meal_plan,
)


@pytest.fixture
def mock_client():
    """Create a mock Mealie client."""
    with patch("mealie_mcp.tools.mealplans.get_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


class TestGetMealPlan:
    """Tests for get_meal_plan tool."""

    @pytest.mark.asyncio
    async def test_get_meal_plan_returns_entries(self, mock_client):
        """Test that meal plan entries are properly formatted."""
        mock_client.get_meal_plan.return_value = [
            MealPlanEntry(
                id="entry-1",
                date=date(2026, 1, 5),
                entryType=MealType.DINNER,
                recipeId="recipe-1",
                recipe=RecipeSummary(
                    id="recipe-1",
                    slug="spaghetti-carbonara",
                    name="Spaghetti Carbonara",
                    tags=[],
                    recipeCategory=[],
                ),
            )
        ]

        result = await get_meal_plan("2026-01-01", "2026-01-07")

        assert len(result) == 1
        assert result[0]["date"] == "2026-01-05"
        assert result[0]["meal_type"] == "dinner"
        assert result[0]["recipe"]["name"] == "Spaghetti Carbonara"

    @pytest.mark.asyncio
    async def test_get_meal_plan_handles_error(self, mock_client):
        """Test error handling."""
        mock_client.get_meal_plan.return_value = ErrorResponse.api_error("Failed")

        result = await get_meal_plan("2026-01-01", "2026-01-07")

        assert result["error"] is True


class TestCreateMealPlanEntry:
    """Tests for create_meal_plan_entry tool."""

    @pytest.mark.asyncio
    async def test_create_meal_plan_entry_success(self, mock_client):
        """Test successful meal plan creation."""
        mock_client.create_meal_plan_entry.return_value = MealPlanEntry(
            id="new-entry",
            date=date(2026, 1, 5),
            entryType=MealType.LUNCH,
            recipeId="recipe-1",
        )

        result = await create_meal_plan_entry(
            date="2026-01-05",
            recipe_slug="recipe-1",
            meal_type="lunch",
        )

        assert result["id"] == "new-entry"
        assert result["meal_type"] == "lunch"

    @pytest.mark.asyncio
    async def test_create_meal_plan_entry_invalid_meal_type(self, mock_client):
        """Test validation of meal type."""
        result = await create_meal_plan_entry(
            date="2026-01-05",
            recipe_slug="recipe-1",
            meal_type="invalid",
        )

        assert result["error"] is True
        assert result["code"] == "VALIDATION_ERROR"


class TestDeleteMealPlanEntry:
    """Tests for delete_meal_plan_entry tool."""

    @pytest.mark.asyncio
    async def test_delete_meal_plan_entry_success(self, mock_client):
        """Test successful deletion."""
        mock_client.delete_meal_plan_entry.return_value = {
            "success": True,
            "message": "Deleted meal plan entry entry-1",
        }

        result = await delete_meal_plan_entry("entry-1")

        assert result["success"] is True
