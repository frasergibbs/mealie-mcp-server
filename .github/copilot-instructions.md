  
  # Mealie MCP Server - Copilot Instructions

## Project Overview
Python MCP (Model Context Protocol) server that integrates with a self-hosted Mealie instance for AI-powered meal planning via Claude. Supports multi-user access with per-user Mealie authentication.

## Technology Stack
- **Runtime**: Python 3.11+
- **MCP Framework**: FastMCP
- **HTTP Client**: httpx (async)
- **Data Models**: Pydantic v2
- **Config**: python-dotenv
- **Multi-User**: contextvars for request-scoped user context

## Project Structure
```
mealie-mcp-server/
├── src/mealie_mcp/
│   ├── __init__.py
│   ├── server.py          # Main MCP server entry point
│   ├── client.py          # Mealie API client wrapper (per-user)
│   ├── models.py          # Pydantic models
│   ├── context.py         # Request-scoped user context
│   ├── user_tokens.py     # User token management
│   └── tools/
│       ├── __init__.py
│       ├── recipes.py     # Recipe tools
│       ├── recipes_write.py    # Recipe creation/editing
│       ├── mealplans.py   # Meal planning tools
│       ├── planning_rules.py   # Meal planning rules
│       └── shopping.py    # Shopping list tools
├── config/
│   ├── user_tokens.json   # OAuth user → Mealie token mapping
│   └── README.md          # Token configuration guide
├── tests/
├── Containerfile
├── compose.yaml
├── pyproject.toml
└── .env.example
```

## Multi-User Architecture
- OAuth identifies users via `sub` claim (e.g., email address)
- `user_tokens.py` maps OAuth users to Mealie API tokens
- `context.py` stores current user ID in request context
- `client.py` creates per-user Mealie clients with correct tokens
- Each user sees only their own recipes, meal plans, and shopping lists

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
- `MEALIE_URL` - Mealie API base URL (shared by all users)
- `MEALIE_TOKEN` - (Deprecated) Single token - use user_tokens.json instead
- `MCP_AUTH_TOKEN` - MCP server authentication token (if not using OAuth)
- `OAUTH_SERVER_URL` - OAuth authorization server URL (internal)
- `OAUTH_PUBLIC_URL` - OAuth server public URL (for discovery)
- `MCP_RESOURCE_URI` - This MCP server's canonical URI
- `MCP_HOST` - Server host (default: 0.0.0.0)
- `MCP_PORT` - Server port (default: 8080)
- `USER_TOKENS_PATH` - Custom path to user_tokens.json (optional)

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
- **Multi-User Setup**: docs/MULTI_USER_SETUP.md
- **OAuth Setup**: docs/OAUTH_SETUP.md
