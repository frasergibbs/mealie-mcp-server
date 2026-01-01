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
git clone https://github.com/yourusername/mealie-mcp-server.git
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

### Running as Remote Server (SSE mode)

For remote access via Tailscale Funnel:

```bash
MCP_TRANSPORT=sse python -m mealie_mcp.server
```

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
| `MCP_TRANSPORT` | Transport mode: `stdio` or `sse` | `stdio` |
| `MCP_HOST` | Host to bind (SSE mode only) | `0.0.0.0` |
| `MCP_PORT` | Port to bind (SSE mode only) | `8080` |

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
# Start the service
podman-compose up -d
```

### Expose via Tailscale Funnel

```bash
tailscale funnel 8080
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
│   └── tools/
│       ├── __init__.py
│       ├── recipes.py     # Recipe tools
│       ├── mealplans.py   # Meal planning tools
│       └── shopping.py    # Shopping list tools
├── tests/
├── Containerfile
├── compose.yaml
├── pyproject.toml
└── README.md
```

## Roadmap

- [ ] OAuth 2.1 support for Claude.ai and mobile access
- [ ] Recipe creation/editing
- [ ] Nutritional analysis and filtering
- [ ] Meal suggestions based on available ingredients

## License

MIT
