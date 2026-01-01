"""Tests for shopping list MCP tools."""

from unittest.mock import AsyncMock, patch

import pytest

from mealie_mcp.models import ShoppingList, ShoppingListItem, ShoppingListSummary
from mealie_mcp.tools.shopping import (
    add_to_shopping_list,
    clear_checked_items,
    get_shopping_list,
    get_shopping_lists,
)


@pytest.fixture
def mock_client():
    """Create a mock Mealie client."""
    with patch("mealie_mcp.tools.shopping.get_client") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client


class TestGetShoppingLists:
    """Tests for get_shopping_lists tool."""

    @pytest.mark.asyncio
    async def test_get_shopping_lists_returns_list(self, mock_client):
        """Test that shopping lists are returned."""
        mock_client.get_shopping_lists.return_value = [
            ShoppingListSummary(id="list-1", name="Weekly Groceries"),
            ShoppingListSummary(id="list-2", name="Party Supplies"),
        ]

        result = await get_shopping_lists()

        assert len(result) == 2
        assert result[0]["name"] == "Weekly Groceries"


class TestGetShoppingList:
    """Tests for get_shopping_list tool."""

    @pytest.mark.asyncio
    async def test_get_shopping_list_with_id(self, mock_client):
        """Test getting a specific list."""
        mock_client.get_shopping_list.return_value = ShoppingList(
            id="list-1",
            name="Weekly Groceries",
            listItems=[
                ShoppingListItem(
                    id="item-1", shoppingListId="list-1", note="Milk", checked=False
                ),
                ShoppingListItem(
                    id="item-2", shoppingListId="list-1", note="Eggs", checked=True
                ),
            ],
        )

        result = await get_shopping_list("list-1")

        assert result["name"] == "Weekly Groceries"
        assert result["unchecked_count"] == 1
        assert len(result["items_checked"]) == 1

    @pytest.mark.asyncio
    async def test_get_shopping_list_default(self, mock_client):
        """Test getting the default list when no ID provided."""
        mock_client.get_shopping_lists.return_value = [
            ShoppingListSummary(id="list-1", name="Default List"),
        ]
        mock_client.get_shopping_list.return_value = ShoppingList(
            id="list-1",
            name="Default List",
            listItems=[],
        )

        await get_shopping_list()

        mock_client.get_shopping_lists.assert_called_once()
        mock_client.get_shopping_list.assert_called_with("list-1")


class TestAddToShoppingList:
    """Tests for add_to_shopping_list tool."""

    @pytest.mark.asyncio
    async def test_add_to_shopping_list_success(self, mock_client):
        """Test adding items to a list."""
        mock_client.get_shopping_lists.return_value = [
            ShoppingListSummary(id="list-1", name="Default"),
        ]
        mock_client.add_shopping_list_item.return_value = ShoppingListItem(
            id="new-item", shoppingListId="list-1", note="2 cups flour", checked=False
        )

        result = await add_to_shopping_list(["2 cups flour"])

        assert result["added_count"] == 1
        assert result["added_items"][0]["text"] == "2 cups flour"

    @pytest.mark.asyncio
    async def test_add_to_shopping_list_empty(self, mock_client):
        """Test validation when no items provided."""
        result = await add_to_shopping_list([])

        assert result["error"] is True
        assert result["code"] == "VALIDATION_ERROR"


class TestClearCheckedItems:
    """Tests for clear_checked_items tool."""

    @pytest.mark.asyncio
    async def test_clear_checked_items_success(self, mock_client):
        """Test clearing checked items."""
        mock_client.get_shopping_lists.return_value = [
            ShoppingListSummary(id="list-1", name="Default"),
        ]
        mock_client.clear_checked_items.return_value = {
            "success": True,
            "removed_count": 3,
            "message": "Removed 3 checked items",
        }

        result = await clear_checked_items()

        assert result["success"] is True
        assert result["removed_count"] == 3
