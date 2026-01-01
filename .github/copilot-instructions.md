# Mealie MCP Server - Copilot Instructions

## Project Overview
Python MCP (Model Context Protocol) server that integrates with a self-hosted Mealie instance for AI-powered meal planning via Claude.

## Technology Stack
- **Runtime**: Python 3.11+
- **MCP Framework**: FastMCP
- **HTTP Client**: httpx (async)
- **Data Models**: Pydantic v2
- **Config**: python-dotenv

## Project Structure
```
mealie-mcp-server/
├── src/mealie_mcp/
│   ├── __init__.py
│   ├── server.py          # Main MCP server entry point
│   ├── client.py          # Mealie API client wrapper
│   ├── models.py          # Pydantic models
│   └── tools/
│       ├── __init__.py
│       ├── recipes.py     # Recipe tools
│       ├── mealplans.py   # Meal planning tools
│       └── shopping.py    # Shopping list tools
├── tests/
├── Containerfile
├── compose.yaml
├── pyproject.toml
└── .env.example
```

## MCP Tools
- `search_recipes` - Search recipe library with filters
- `get_recipe` - Get full recipe details
- `list_tags` / `list_categories` - Get organizers
- `get_meal_plan` - Retrieve meal plans by date range
- `create_meal_plan_entry` / `delete_meal_plan_entry` - Manage meal plans
- `get_shopping_lists` / `get_shopping_list` - View shopping lists
- `add_to_shopping_list` / `clear_checked_items` - Manage shopping items

## Development Commands
```bash
# Install dependencies
pip install -e ".[dev]"

# Run server locally
python -m mealie_mcp.server

# Run tests
pytest

# Lint
ruff check src/ tests/
```

## Environment Variables
- `MEALIE_URL` - Mealie API base URL
- `MEALIE_TOKEN` - Mealie API bearer token
- `MCP_AUTH_TOKEN` - MCP server authentication token
- `MCP_HOST` - Server host (default: 0.0.0.0)
- `MCP_PORT` - Server port (default: 8080)
