# OAuth Setup Guide

This guide covers setting up OAuth 2.1 authentication for Claude mobile access using **Podman**.

## Prerequisites

- Podman and podman-compose installed
- Domain with valid TLS certificate (or Tailscale HTTPS)
- Access to rainworth-server

## Architecture

```
┌─────────────┐                 ┌──────────────────┐                 ┌─────────────┐
│   Claude    │────OAuth────────▶│ Hydra (4444)     │────validates───▶│   Mealie    │
│   Mobile    │                 │ + Consent UI     │                 │ MCP Server  │
│             │◀───token────────│ (3000)           │                 │   (8080)    │
└─────────────┘                 └──────────────────┘                 └─────────────┘
                                         │
                                         ▼
                                ┌──────────────────┐
                                │   PostgreSQL     │
                                │   (hydra db)     │
                                └──────────────────┘
```

## Quick Start

### 1. Start OAuth Infrastructure

```bash
# On rainworth-server
cd ~/Repos/mealie-mcp-server

# Start PostgreSQL and Hydra
podman-compose up -d postgres hydra-migrate hydra hydra-consent

# Verify Hydra is running
curl http://localhost:4444/.well-known/openid-configuration
```

### 2. Configure MCP Server for OAuth

Update `.env` or systemd service:

```bash
# OAuth configuration
OAUTH_SERVER_URL=https://auth.your-domain.com
MCP_RESOURCE_URI=https://mcp.your-domain.com
MCP_TRANSPORT=streamable-http
MCP_REQUIRE_AUTH=true
MCP_HOST=0.0.0.0
MCP_PORT=8080

# Existing Mealie config
MEALIE_URL=http://localhost:9000/api
MEALIE_TOKEN=your-mealie-api-token
```

### 3. Update Systemd Service

Edit `~/.config/systemd/user/mealie-mcp.service`:

```ini
[Service]
Environment="MCP_TRANSPORT=streamable-http"
Environment="OAUTH_SERVER_URL=https://auth.your-domain.com"
Environment="MCP_RESOURCE_URI=https://mcp.your-domain.com"
Environment="MCP_REQUIRE_AUTH=true"
```

Restart:
```bash
systemctl --user daemon-reload
systemctl --user restart mealie-mcp
```

## Podman Commands

### Start All Services
```bash
podman-compose up -d
```

### Start Only OAuth Services
```bash
podman-compose up -d postgres hydra hydra-consent
```

### View Logs
```bash
# All services
podman-compose logs -f

# Specific service
podman-compose logs -f hydra
podman-compose logs -f hydra-consent
```

### Stop Services
```bash
podman-compose down
```

### Clean Everything (including data)
```bash
podman-compose down -v
```

## Endpoints

- **MCP Server**: http://localhost:8080/mcp
- **Hydra Public**: http://localhost:4444
- **Hydra Admin**: http://localhost:4445 (internal only)
- **Consent UI**: http://localhost:3000
- **Resource Metadata**: http://localhost:8080/.well-known/oauth-protected-resource

## Testing OAuth Flow

### 1. Dynamic Client Registration

```bash
# Register a new OAuth client
curl -X POST http://localhost:4444/clients \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Test Client",
    "redirect_uris": ["http://localhost:5000/callback"],
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none"
  }'
```

Save the `client_id` from the response.

### 2. Start Authorization Flow

Open in browser:
```
http://localhost:4444/oauth2/auth?
  client_id=<CLIENT_ID>&
  response_type=code&
  scope=openid&
  redirect_uri=http://localhost:5000/callback&
  state=random-state&
  code_challenge=<PKCE_CHALLENGE>&
  code_challenge_method=S256&
  resource=http://localhost:8080
```

### 3. Exchange Code for Token

```bash
curl -X POST http://localhost:4444/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "client_id=<CLIENT_ID>" \
  -d "code=<AUTH_CODE>" \
  -d "redirect_uri=http://localhost:5000/callback" \
  -d "code_verifier=<PKCE_VERIFIER>" \
  -d "resource=http://localhost:8080"
```

### 4. Call MCP Server with Token

```bash
curl -X POST http://localhost:8080/mcp \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }'
```

## Production Deployment

### On rainworth-server

1. **Set up reverse proxy** (nginx/Caddy) with TLS:

```nginx
# /etc/nginx/sites-available/mcp-oauth
server {
    listen 443 ssl http2;
    server_name auth.your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Hydra public API
    location / {
        proxy_pass http://localhost:4444;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 443 ssl http2;
    server_name mcp.your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # MCP server
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Authorization $http_authorization;
    }
}
```

2. **Update Hydra config** (`oauth/hydra.yml`):

```yaml
urls:
  self:
    issuer: https://auth.your-domain.com
  consent: https://auth.your-domain.com/consent
  login: https://auth.your-domain.com/login
```

3. **Update environment variables** to use HTTPS URLs

## Troubleshooting

### Hydra won't start
```bash
# Check database
podman exec -it mealie-oauth-db psql -U hydra -c '\dt'

# Re-run migrations
podman-compose up hydra-migrate
```

### Token validation failing
```bash
# Check MCP server logs
journalctl --user -u mealie-mcp -f

# Introspect token
curl -X POST http://localhost:4444/oauth2/introspect \
  -d "token=<ACCESS_TOKEN>"
```

### Consent UI not loading
```bash
# Check consent service logs
podman-compose logs hydra-consent

# Verify Hydra admin API accessible
curl http://localhost:4445/health/ready
```

## Security Notes

1. **Never expose Hydra admin API (4445)** to the internet
2. **Always use HTTPS** in production
3. **Change default secrets** in `oauth/hydra.yml`
4. **Set strong PostgreSQL password** in production
5. **Enable rate limiting** on OAuth endpoints
6. **Rotate secrets regularly**

## Disabling OAuth (Development)

For local development without OAuth:

```bash
# .env
MCP_TRANSPORT=stdio  # for Claude Desktop
# OR
MCP_TRANSPORT=streamable-http
MCP_REQUIRE_AUTH=false  # DEVELOPMENT ONLY!
```

## Next Steps

1. Configure Claude mobile with your MCP server URL
2. Complete OAuth flow in Claude app
3. Test recipe search and meal planning
4. Monitor logs for any issues
