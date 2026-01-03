# ✅ Multi-User Deployment Complete

## Summary

Two separate MCP server instances are now running with **FastMCP OAuth + Tailscale Funnel**:

- **Fraser**: https://rainworth-server.tailbf31d9.ts.net/fraser/mcp
- **Sam**: https://rainworth-server.tailbf31d9.ts.net/sam/mcp

## Security Model ⚠️

**Current: OAuth DCR + URL Obscurity + Per-Server Tokens**

1. **FastMCP OAuth with DCR** - Required for Claude.ai to work (Dynamic Client Registration)
2. **Tailscale Funnel** - Public access (required for claude.ai, works without Tailscale)
3. **Per-server tokens** - Each instance uses only that user's Mealie token
4. **Path isolation** - /fraser and /sam are separate server processes

⚠️ **Note**: FastMCP's OAuth provides DCR but NO user authentication. Anyone with the URL can register a client.

🔒 **Planned**: Auth0 integration for proper user authentication - see `.github/ISSUE_TEMPLATE/auth0-enhancement.md`

### How Tailscale Serve Works

- Only devices **on your Tailscale network** can access the servers
- Tailscale handles authentication automatically
- Works alongside Caddy (port 443 shared via hostname routing):
  - `mealie.fraserandsam.com` → Caddy → Mealie (public)
  - `rainworth-server.tailbf31d9.ts.net` → Tailscale → MCP servers (Tailscale-only)

## Configure Claude Desktop

**Fraser's Config** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "mealie": {
      "url": "https://rainworth-server.tailbf31d9.ts.net/fraser/mcp",
      "transport": "sse"
    }
  }
}
```

**Sam's Config** (on Sam's computer):
```json
{
  "mcpServers": {
    "mealie": {
      "url": "https://rainworth-server.tailbf31d9.ts.net/sam/mcp",
      "transport": "sse"
    }
  }
}
```

## Service Management

```bash
# View status
systemctl --user status mealie-mcp-fraser
systemctl --user status mealie-mcp-sam

# View logs
journalctl --user -u mealie-mcp-fraser -f
journalctl --user -u mealie-mcp-sam -f

# Restart
systemctl --user restart mealie-mcp-fraser mealie-mcp-sam

# Update code
ssh fraser@rainworth-server "cd ~/Repos/mealie-mcp-server && git pull && systemctl --user restart mealie-mcp-fraser mealie-mcp-sam"
```

## Current Status

✅ Fraser's server: Running on port 8080  
✅ Sam's server: Running on port 8081  
✅ Tailscale Serve: Configured for both paths  
✅ No port conflicts with Caddy  
✅ Authentication: Tailscale network required  

## Testing

From a Tailscale-authenticated device:
```bash
# Test Fraser's endpoint
curl https://rainworth-server.tailbf31d9.ts.net/fraser/

# Test Sam's endpoint  
curl https://rainworth-server.tailbf31d9.ts.net/sam/
```

From a non-Tailscale device:
```bash
# Should fail with connection/auth error
curl https://rainworth-server.tailbf31d9.ts.net/fraser/
```

## Architecture

```
Tailscale Network (Auth Required)
         ↓
rainworth-server.tailbf31d9.ts.net:443
         ├─ /fraser → 127.0.0.1:8080 (Fraser's server + Fraser's token)
         └─ /sam    → 127.0.0.1:8081 (Sam's server + Sam's token)
                              ↓
                     Mealie API (127.0.0.1:9000)
```

## Next Steps

1. Add server URLs to Claude Desktop on both Fraser and Sam's computers
2. Restart Claude Desktop to load the new configuration
3. Test by asking Claude to search recipes (each user will see their own recipes)

## Maintenance

- **Update tokens**: Edit `~/.config/mealie-fraser.env` or `~/.config/mealie-sam.env` and restart services
- **View Tailscale config**: `tailscale serve status`
- **Reset Tailscale**: `tailscale serve reset`
