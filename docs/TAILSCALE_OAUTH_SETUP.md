# Tailscale Funnel + OAuth Configuration

This guide configures the Mealie MCP server to be accessible via Claude mobile using Tailscale Funnel and OAuth 2.1.

## Architecture

- **MCP Server**: `https://rainworth-server.tailbf31d9.ts.net/mcp` (port 8081, exposed via Tailscale Funnel)
- **OAuth Server**: `https://rainworth-server.tailbf31d9.ts.net/oauth` (Hydra port 4444, exposed via Tailscale Funnel)
- **Consent UI**: `http://localhost:3000` (internal only)
- **PostgreSQL**: `mealie-oauth-db` on `oauth_network` (internal only)

## Setup Steps

### 1. Configure Tailscale Funnel

On `rainworth-server`, run:

```bash
# Reset existing configuration
sudo tailscale serve reset

# Expose MCP server on /mcp
sudo tailscale serve --bg --https=443 --set-path=/mcp http://127.0.0.1:8081

# Expose OAuth server on /oauth/
sudo tailscale serve --bg --https=443 --set-path=/oauth/ http://127.0.0.1:4444

# Enable funnel (public access)
sudo tailscale funnel --bg 443 on

# Verify configuration
tailscale funnel status
```

Expected output:
```
# Funnel on:
#     - https://rainworth-server.tailbf31d9.ts.net

https://rainworth-server.tailbf31d9.ts.net (Funnel on)
|-- /mcp proxy http://127.0.0.1:8081
|-- /oauth/ proxy http://127.0.0.1:4444
```

### 2. Update Hydra Configuration

Edit `~/Repos/mealie-mcp-server/oauth/hydra.yml`:

```yaml
serve:
  public:
    cors:
      enabled: true
      allowed_origins:
        - https://rainworth-server.tailbf31d9.ts.net

urls:
  self:
    issuer: https://rainworth-server.tailbf31d9.ts.net/oauth
  consent: http://localhost:3000/consent
  login: http://localhost:3000/login

dsn: postgres://hydra:secret@mealie-oauth-db:5432/hydra?sslmode=disable

oauth2:
  expose_internal_errors: true
  pkce:
    enforced: true
  access_token_strategy: jwt
  access_token_lifespan: 1h
  refresh_token_lifespan: 720h
  id_token_lifespan: 1h
  auth_code_lifespan: 10m

secrets:
  system:
    - yoursupersecrethydrasystemsecretkey1234567890
```

### 3. Update MCP Server Systemd Service

Edit `~/.config/systemd/user/mealie-mcp-oauth.service`:

```ini
[Unit]
Description=Mealie MCP Server (OAuth/HTTP)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/fraser/Repos/mealie-mcp-server
Environment=MEALIE_URL=http://localhost:9000/api
Environment=MEALIE_TOKEN=<your-token-here>
Environment=MCP_TRANSPORT=streamable-http
Environment=MCP_HOST=127.0.0.1
Environment=MCP_PORT=8081
Environment=OAUTH_SERVER_URL=https://rainworth-server.tailbf31d9.ts.net/oauth
Environment=MCP_RESOURCE_URI=https://rainworth-server.tailbf31d9.ts.net/mcp
ExecStart=/home/fraser/Repos/mealie-mcp-server/.venv/bin/python -m mealie_mcp.server
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

### 4. Restart Services

```bash
# Restart Hydra with new configuration
podman stop mealie-hydra
podman rm mealie-hydra

podman run -d \
  --name mealie-hydra \
  --network oauth_network \
  -p 4444:4444 \
  -p 4445:4445 \
  -v ~/Repos/mealie-mcp-server/oauth/hydra.yml:/home/ory/hydra.yml:ro \
  docker.io/oryd/hydra:v2.2 \
  serve all --config /home/ory/hydra.yml

# Reload and restart MCP OAuth service
systemctl --user daemon-reload
systemctl --user restart mealie-mcp-oauth

# Verify services are running
systemctl --user status mealie-mcp-oauth
podman ps | grep hydra
```

### 5. Register OAuth Client

Register a client for Claude mobile:

```bash
curl -X POST https://rainworth-server.tailbf31d9.ts.net/oauth/admin/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Claude Mobile",
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "redirect_uris": ["anthropic://auth/callback"],
    "scope": "mcp:read mcp:write offline_access",
    "token_endpoint_auth_method": "none"
  }'
```

Save the returned `client_id` - you'll need it for Claude mobile configuration.

## Testing

### Test Protected Resource Metadata

```bash
curl https://rainworth-server.tailbf31d9.ts.net/mcp/.well-known/oauth-protected-resource
```

Expected response:
```json
{
  "resource": "https://rainworth-server.tailbf31d9.ts.net/mcp",
  "authorization_servers": [
    "https://rainworth-server.tailbf31d9.ts.net/oauth"
  ],
  "bearer_methods_supported": ["header"],
  "resource_documentation": "https://github.com/frasergibbs/mealie-mcp-server"
}
```

### Test Authorization Server Metadata

```bash
curl https://rainworth-server.tailbf31d9.ts.net/oauth/.well-known/oauth-authorization-server
```

Should return OAuth server configuration with HTTPS endpoints.

### Test MCP Endpoint (Should Return 401)

```bash
curl -i https://rainworth-server.tailbf31d9.ts.net/mcp
```

Expected:
```
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer realm="mcp", resource_metadata="https://rainworth-server.tailbf31d9.ts.net/mcp/.well-known/oauth-protected-resource"
```

## Claude Mobile Configuration

In Claude mobile app, add MCP server:

**Server URL**: `https://rainworth-server.tailbf31d9.ts.net/mcp`

Claude will:
1. Attempt to connect and receive 401
2. Fetch protected resource metadata
3. Discover OAuth server at `https://rainworth-server.tailbf31d9.ts.net/oauth`
4. Initiate OAuth flow with PKCE
5. Open browser for user consent
6. Receive access token
7. Connect to MCP server with token

## Troubleshooting

### Check Tailscale Funnel Status
```bash
tailscale funnel status
```

### Check MCP Server Logs
```bash
journalctl --user -u mealie-mcp-oauth -f
```

### Check Hydra Logs
```bash
podman logs mealie-hydra -f
```

### Check Consent UI Logs
```bash
podman logs mealie-hydra-consent -f
```

### Test from External Device
From a device NOT on your Tailscale network:
```bash
curl https://rainworth-server.tailbf31d9.ts.net/mcp/.well-known/oauth-protected-resource
```

This should work if Funnel is properly configured.
