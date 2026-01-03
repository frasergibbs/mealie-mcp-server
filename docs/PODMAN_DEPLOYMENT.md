# Deploying OAuth to rainworth-server (Podman)

Quick deployment guide for adding OAuth support to your existing Mealie MCP server running on rainworth-server.

## Current Setup (Before OAuth)

- MCP server runs via systemd user service
- Uses stdio transport for Claude Desktop
- No OAuth, no remote access to Claude mobile

## After OAuth Setup

- MCP server supports **both** stdio (Claude Desktop) and streamable-http (Claude Mobile)
- Hydra OAuth server handles authentication
- Podman containers for Hydra + PostgreSQL + Consent UI

## Deployment Steps

### 1. Pull Latest Code

```bash
ssh fraser@rainworth-server
cd ~/Repos/mealie-mcp-server
git pull
```

### 2. Install OAuth Dependencies

```bash
source venv/bin/activate
pip install -e ".[oauth]"
```

### 3. Start OAuth Services with Podman

```bash
# Start OAuth infrastructure
podman-compose up -d postgres hydra-migrate hydra hydra-consent

# Verify services
podman ps
podman-compose logs -f hydra
```

### 4. Update Systemd Service

Edit `~/.config/systemd/user/mealie-mcp.service`:

```ini
[Unit]
Description=Mealie MCP Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/fraser/Repos/mealie-mcp-server
Environment="PATH=/home/fraser/Repos/mealie-mcp-server/venv/bin:/usr/bin"
Environment="MEALIE_URL=http://localhost:9000/api"
Environment="MEALIE_TOKEN=your-token"

# NEW: OAuth configuration (keep stdio for Claude Desktop compatibility)
Environment="MCP_TRANSPORT=streamable-http"
Environment="OAUTH_SERVER_URL=https://auth.rainworth-server.your-tailnet.ts.net"
Environment="MCP_RESOURCE_URI=https://mcp.rainworth-server.your-tailnet.ts.net"
Environment="MCP_REQUIRE_AUTH=true"
Environment="MCP_HOST=0.0.0.0"
Environment="MCP_PORT=8080"

ExecStart=/home/fraser/Repos/mealie-mcp-server/venv/bin/python -m mealie_mcp.server
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

### 5. Reload and Restart

```bash
systemctl --user daemon-reload
systemctl --user restart mealie-mcp
systemctl --user status mealie-mcp
```

### 6. Configure Tailscale HTTPS (if not already done)

```bash
# Enable HTTPS on Tailscale
sudo tailscale cert rainworth-server
```

This gives you valid certs at:
- `https://rainworth-server.your-tailnet.ts.net`

### 7. Set Up Reverse Proxy (Optional but Recommended)

Using Caddy for automatic HTTPS:

```bash
# Install Caddy
sudo dnf install caddy

# Configure
sudo nano /etc/caddy/Caddyfile
```

Add:
```
# Hydra public API
auth.rainworth-server.your-tailnet.ts.net {
    reverse_proxy localhost:4444
}

# MCP server
mcp.rainworth-server.your-tailnet.ts.net {
    reverse_proxy localhost:8080
}

# Consent UI
auth.rainworth-server.your-tailnet.ts.net/consent {
    reverse_proxy localhost:3000
}

auth.rainworth-server.your-tailnet.ts.net/login {
    reverse_proxy localhost:3000
}
```

```bash
sudo systemctl enable --now caddy
```

## Podman-Specific Notes

### Podman vs Docker

- Use `podman-compose` instead of `docker compose`
- `podman ps` instead of `docker ps`
- Podman runs rootless by default (good for security!)
- Networks work slightly differently

### Managing Containers

```bash
# List all containers
podman ps -a

# View logs
podman logs mealie-hydra
podman logs mealie-oauth-db

# Stop services
podman-compose down

# Restart single service
podman-compose restart hydra
```

### Persistence

Volumes are stored in:
```
~/.local/share/containers/storage/volumes/
```

Check with:
```bash
podman volume ls
```

## Testing

### 1. Verify OAuth Server

```bash
curl https://auth.rainworth-server.your-tailnet.ts.net/.well-known/openid-configuration
```

### 2. Verify MCP Server

```bash
curl https://mcp.rainworth-server.your-tailnet.ts.net/.well-known/oauth-protected-resource
```

Should return:
```json
{
  "resource": "https://mcp.rainworth-server.your-tailnet.ts.net",
  "authorization_servers": ["https://auth.rainworth-server.your-tailnet.ts.net"],
  "bearer_methods_supported": ["header"]
}
```

### 3. Test with Claude Desktop (stdio still works!)

Your existing Claude Desktop config continues to work unchanged:

```json
{
  "mcpServers": {
    "mealie": {
      "command": "ssh",
      "args": [
        "fraser@rainworth-server",
        "cd ~/Repos/mealie-mcp-server && MCP_TRANSPORT=stdio venv/bin/python -m mealie_mcp.server"
      ]
    }
  }
}
```

## Troubleshooting

### Check all services are running

```bash
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Should show:
- mealie-oauth-db (Up)
- mealie-hydra (Up, 4444->4444, 4445->4445)
- mealie-hydra-consent (Up, 3000->3000)

### View MCP server logs

```bash
journalctl --user -u mealie-mcp -f
```

### Restart everything

```bash
# Stop MCP server
systemctl --user stop mealie-mcp

# Stop OAuth services
podman-compose down

# Start OAuth services
podman-compose up -d postgres hydra-migrate hydra hydra-consent

# Wait for healthy
sleep 10

# Start MCP server
systemctl --user start mealie-mcp
```

## Rollback (If Needed)

```bash
# Stop OAuth services
podman-compose down

# Revert systemd service to stdio
systemctl --user edit mealie-mcp.service
# Remove OAuth environment variables

# Restart
systemctl --user restart mealie-mcp
```

## Auto-Start on Boot

```bash
# Enable services to start on boot
systemctl --user enable mealie-mcp

# For podman containers, create systemd units:
cd ~/Repos/mealie-mcp-server
podman generate systemd --new --name mealie-hydra > ~/.config/systemd/user/mealie-hydra.service
podman generate systemd --new --name mealie-oauth-db > ~/.config/systemd/user/mealie-oauth-db.service
podman generate systemd --new --name mealie-hydra-consent > ~/.config/systemd/user/mealie-hydra-consent.service

systemctl --user enable mealie-hydra mealie-oauth-db mealie-hydra-consent
```

## Next: Configure Claude Mobile

See docs/OAUTH_SETUP.md for testing OAuth flow with Claude mobile.
