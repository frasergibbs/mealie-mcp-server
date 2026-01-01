"""Shopping list MCP tools."""

from mealie_mcp.client import get_client
from mealie_mcp.models import ErrorResponse


async def get_shopping_lists() -> list[dict] | dict:
    """Get all shopping lists.

    Returns:
        List of shopping list summaries with id and name
    """
    client = get_client()
    result = await client.get_shopping_lists()

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return [{"id": s.id, "name": s.name} for s in result]


async def get_shopping_list(list_id: str | None = None) -> dict:
    """Get items from a specific shopping list.

    Args:
        list_id: Shopping list ID. If not provided, uses the first available list.

    Returns:
        Shopping list with all items including their checked status
    """
    client = get_client()

    # If no list_id provided, get the first available list
    if list_id is None:
        lists = await client.get_shopping_lists()
        if isinstance(lists, ErrorResponse):
            return lists.model_dump()
        if not lists:
            return {
                "error": True,
                "code": "NOT_FOUND",
                "message": "No shopping lists found",
            }
        list_id = lists[0].id

    result = await client.get_shopping_list(list_id)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    # Format items for readability
    items = []
    for item in result.list_items:
        item_data = {
            "id": item.id,
            "checked": item.checked,
            "quantity": item.quantity,
        }

        # Build display text
        if item.display:
            item_data["text"] = item.display
        elif item.note:
            item_data["text"] = item.note
        else:
            parts = []
            if item.quantity and item.quantity != 1:
                parts.append(str(item.quantity))
            if item.unit:
                parts.append(item.unit)
            if item.food:
                parts.append(item.food)
            item_data["text"] = " ".join(parts)

        items.append(item_data)

    # Separate checked and unchecked for clarity
    unchecked = [i for i in items if not i["checked"]]
    checked = [i for i in items if i["checked"]]

    return {
        "id": result.id,
        "name": result.name,
        "items_to_buy": unchecked,
        "items_checked": checked,
        "total_items": len(items),
        "unchecked_count": len(unchecked),
    }


async def add_to_shopping_list(
    items: list[str],
    list_id: str | None = None,
) -> dict:
    """Add items to a shopping list.

    Args:
        items: List of item descriptions to add (e.g., ["2 cups flour", "1 dozen eggs"])
        list_id: Target shopping list ID. If not provided, uses the first available list.

    Returns:
        Summary of added items with the updated list info
    """
    if not items:
        return {
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": "No items provided to add",
        }

    client = get_client()

    # If no list_id provided, get the first available list
    if list_id is None:
        lists = await client.get_shopping_lists()
        if isinstance(lists, ErrorResponse):
            return lists.model_dump()
        if not lists:
            return {
                "error": True,
                "code": "NOT_FOUND",
                "message": "No shopping lists found",
            }
        list_id = lists[0].id

    # Add each item
    added = []
    failed = []

    for item_text in items:
        result = await client.add_shopping_list_item(list_id, item_text)
        if isinstance(result, ErrorResponse):
            failed.append({"item": item_text, "error": result.message})
        else:
            added.append({"id": result.id, "text": item_text})

    response = {
        "list_id": list_id,
        "added_count": len(added),
        "added_items": added,
    }

    if failed:
        response["failed_items"] = failed

    return response


async def clear_checked_items(list_id: str | None = None) -> dict:
    """Remove all checked items from a shopping list.

    Args:
        list_id: Shopping list ID. If not provided, uses the first available list.

    Returns:
        Summary of removed items count
    """
    client = get_client()

    # If no list_id provided, get the first available list
    if list_id is None:
        lists = await client.get_shopping_lists()
        if isinstance(lists, ErrorResponse):
            return lists.model_dump()
        if not lists:
            return {
                "error": True,
                "code": "NOT_FOUND",
                "message": "No shopping lists found",
            }
        list_id = lists[0].id

    result = await client.clear_checked_items(list_id)

    if isinstance(result, ErrorResponse):
        return result.model_dump()

    return result
