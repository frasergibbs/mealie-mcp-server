  
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

## Production Deployment

### Server Details
- **Host**: rainworth-server (ssh: fraser@rainworth-server)
- **Install Path**: ~/Repos/mealie-mcp-server
- **Service**: systemd user service at ~/.config/systemd/user/mealie-mcp.service
- **Python**: Virtual environment at .venv/bin/python

### Deployment Process
```bash
# Standard deployment workflow
ssh fraser@rainworth-server "cd ~/Repos/mealie-mcp-server && git pull && systemctl --user restart mealie-mcp && sleep 2 && systemctl --user status mealie-mcp"

# Check service status
ssh fraser@rainworth-server "systemctl --user status mealie-mcp"

# View logs
ssh fraser@rainworth-server "journalctl --user -u mealie-mcp -f"
```

### Service Management
```bash
# Restart service
systemctl --user restart mealie-mcp

# Start/stop service
systemctl --user start mealie-mcp
systemctl --user stop mealie-mcp

# Enable/disable autostart
systemctl --user enable mealie-mcp
systemctl --user disable mealie-mcp
```

## Documentation

- **Mealie API**: https://docs.mealie.io/documentation/getting-started/api/
- **FastMCP**: https://github.com/jlowin/fastmcp
- **Model Context Protocol**: https://modelcontextprotocol.io/
- **Pydantic v2**: https://docs.pydantic.dev/latest/
- **systemd User Services**: https://wiki.archlinux.org/title/Systemd/User
