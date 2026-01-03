# Mealie MCP Server

A Model Context Protocol (MCP) server that integrates with a self-hosted [Mealie](https://mealie.io/) instance, enabling Claude to interact with your personal recipe library for AI-powered meal planning.

## Features

- 🔍 **Search Recipes** - Search your recipe library with text queries, tags, and category filters
- 📖 **View Recipes** - Get full recipe details including ingredients, instructions, and nutrition
- 📅 **Meal Planning** - Create, view, and manage meal plans
- 🛒 **Shopping Lists** - View and add items to shopping lists

## Quick Start

### Prerequisites

- Python 3.11+
- A running Mealie instance (v2.x)
- Mealie API token (generate in User Profile → Manage API Tokens)

### Installation

```bash
# Clone the repository
git clone https://github.com/frasergibbs/mealie-mcp-server.git
cd mealie-mcp-server

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your Mealie URL and token
```

### Running Locally (stdio mode)

For testing with MCP Inspector or Claude Desktop:

```bash
python -m mealie_mcp.server
```

### Running as HTTP Server with OAuth

For remote access via Claude.ai with OAuth authentication:

```bash
# Set environment variables
export MCP_TRANSPORT=http
export MCP_REQUIRE_AUTH=true
export MCP_BASE_URL=https://your-server.tailxxxxxx.ts.net

# Run server
python -m mealie_mcp.server
```

See [FastMCP OAuth Setup Guide](docs/FASTMCP_OAUTH_SETUP.md) for complete OAuth configuration with Tailscale Funnel.

### Legacy SSE Mode (Deprecated)

```bash
MCP_TRANSPORT=sse python -m mealie_mcp.server
```

> **Note**: SSE transport is deprecated. Use `http` transport with FastMCP's built-in OAuth for remote access.

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_recipes` | Search recipe library with optional query, tags, and categories |
| `get_recipe` | Get full recipe details by slug |
| `list_tags` | Get all available tags |
| `list_categories` | Get all available categories |
| `get_meal_plan` | Get meal plan for a date range |
| `create_meal_plan_entry` | Add a recipe to the meal plan |
| `delete_meal_plan_entry` | Remove an entry from the meal plan |
| `get_meal_planning_rules` | Get configured rules and daily macro requirements |
| `get_shopping_lists` | Get all shopping lists |
| `get_shopping_list` | Get items from a shopping list |
| `add_to_shopping_list` | Add items to a shopping list |
| `clear_checked_items` | Remove checked items from a shopping list |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MEALIE_URL` | Mealie API base URL | `http://localhost:9000/api` |
| `MEALIE_TOKEN` | Mealie API bearer token | Required |
| `MCP_TRANSPORT` | Transport mode: `stdio` or `http` | `stdio` |
| `MCP_HOST` | Host to bind (http mode only) | `0.0.0.0` |
| `MCP_PORT` | Port to bind (http mode only) | `8080` |
| `MCP_REQUIRE_AUTH` | Enable OAuth authentication | `false` |
| `MCP_BASE_URL` | Public URL for OAuth (required if auth enabled) | - |
| `MCP_AUTH_TOKEN` | Portal authentication token | - |
| `RULES_DATA_DIR` | Directory for storing rules config | `/data` |
| `PORTAL_HOST` | Host for rules portal | `0.0.0.0` |
| `PORTAL_PORT` | Port for rules portal | `8081` |

## Deployment

### Container Deployment

```bash
# Build the container
podman build -t mealie-mcp -f Containerfile .

# Run with environment file
podman run -d \
  --name mealie-mcp \
  --network mealie_network \
  -p 8080:8080 \
  --env-file .env \
  mealie-mcp
```

### Docker Compose

```bash
# Start all services (MCP server + rules portal)
podman-compose up -d
```

The rules portal will be available at `http://localhost:8081`.

## Meal Planning Rules Portal

A mobile-friendly web UI for configuring meal planning constraints that Claude follows when generating meal plans.

### Accessing the Portal

- **Local**: `http://localhost:8081`
- **Via Tailscale**: `tailscale funnel 8081` then access at your funnel URL

### Features

- **Rules Tab**: Edit meal planning rules in markdown format (breakfast, lunch, dinner constraints)
- **Daily Macros Tab**: Configure per-day calorie and macronutrient targets with "copy to all" shortcuts

### Default Rules

The portal comes with sensible defaults that you can customize:

- Breakfast: Simple/basic Monday-Friday, repetition allowed
- Lunch: Meal-prep friendly for weekdays (prepared on Sundays)
- Dinner: No consecutive protein repetition, easy meals Mon-Tue, configurable takeout days

### Expose via Tailscale Funnel

```bash
tailscale funnel 8080
```

### Server Deployment (Always-On Host)

For running on a dedicated home server (e.g., old laptop running Linux):

```bash
# Clone and run setup script
git clone https://github.com/frasergibbs/mealie-mcp-server.git
cd mealie-mcp-server
chmod +x scripts/setup-server.sh
./scripts/setup-server.sh

# Edit .env with your Mealie credentials
nano .env

# Enable and start the service
systemctl --user enable --now mealie-mcp

# Expose via Tailscale Funnel
tailscale funnel 8080
```

#### Service Management

```bash
# Check status
systemctl --user status mealie-mcp

# View logs
journalctl --user -u mealie-mcp -f

# Restart after code changes
git pull && systemctl --user restart mealie-mcp
```

## Claude Desktop Configuration

Add to `~/.config/claude/claude_desktop_config.json`:

### Local (stdio) Mode

```json
{
  "mcpServers": {
    "mealie": {
      "command": "python",
      "args": ["-m", "mealie_mcp.server"],
      "cwd": "/path/to/mealie-mcp-server",
      "env": {
        "MEALIE_URL": "http://localhost:9000/api",
        "MEALIE_TOKEN": "your-token-here"
      }
    }
  }
}
```

### Remote (SSE) Mode with mcp-remote

```json
{
  "mcpServers": {
    "mealie": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://your-host.tail-xxxxx.ts.net/sse",
        "--header",
        "Authorization: Bearer YOUR_MCP_AUTH_TOKEN"
      ]
    }
  }
}
```

## Development

### Running Tests

```bash
pytest
```

### Linting

```bash
ruff check src/ tests/
```

### Testing with MCP Inspector

```bash
npx @anthropic-ai/mcp-inspector
```

## Project Structure

```
mealie-mcp-server/
├── src/mealie_mcp/
│   ├── __init__.py
│   ├── server.py          # Main MCP server entry point
│   ├── client.py          # Mealie API client wrapper
│   ├── models.py          # Pydantic models
│   ├── context.py         # Request context for user IDs
│   ├── user_tokens.py     # Multi-user token management
│   ├── auth/              # OAuth validation
│   ├── portal/
│   │   ├── __init__.py
│   │   ├── app.py         # FastAPI rules portal
│   │   └── rules.py       # Rules storage/retrieval
│   ├── transports/
│   │   ├── __init__.py
│   │   └── streamable_http.py  # HTTP transport with OAuth
│   └── tools/
│       ├── __init__.py
│       ├── recipes.py     # Recipe tools
│       ├── recipes_write.py    # Recipe creation/editing
│       ├── mealplans.py   # Meal planning tools
│       ├── planning_rules.py   # Rules MCP tool
│       └── shopping.py    # Shopping list tools
├── config/
│   ├── user_tokens.json   # User→token mapping (gitignored)
│   └── README.md          # Token setup instructions
├── docs/
│   ├── MULTI_USER_SETUP.md     # Multi-user configuration guide
│   ├── OAUTH_SETUP.md          # OAuth deployment guide
│   └── DEPLOYMENT.md           # Production deployment
├── tests/
├── Containerfile
├── compose.yaml
├── pyproject.toml
└── README.md
```

## Documentation

- **[Multi-User Setup Guide](docs/MULTI_USER_SETUP.md)** - Configure for family/team use
- **[OAuth Setup Guide](docs/OAUTH_SETUP.md)** - Deploy with Claude.ai access
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production server setup

## Roadmap

- [x] OAuth 2.1 support with Dynamic Client Registration for Claude.ai
- [x] Multi-user support with per-user Mealie tokens
- [x] Recipe creation/editing
- [ ] Nutritional analysis and filtering
- [ ] Meal suggestions based on available ingredients

## License

MIT
