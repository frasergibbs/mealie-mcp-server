"""Meal planning rules tools for MCP."""

from mealie_mcp.portal.rules import get_all


async def get_meal_planning_rules() -> dict:
    """Get the current meal planning rules and macro requirements.

    Returns:
        Dictionary with 'rules' (markdown text) and 'macros' (per-day requirements)
    """
    return get_all()
