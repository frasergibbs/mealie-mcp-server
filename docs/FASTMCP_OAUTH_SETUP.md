# FastMCP Built-in OAuth Setup

This guide covers using FastMCP's built-in OAuth 2.1 provider with Dynamic Client Registration (DCR) for Claude.ai integration.

## Why FastMCP's Built-in OAuth?

FastMCP includes `InMemoryOAuthProvider` - a complete OAuth 2.1 server with:
- ✅ **Dynamic Client Registration (DCR)** - Required by Claude.ai for auto-registration
- ✅ **PKCE Support** - Enhanced security for public clients
- ✅ **Token Management** - Access tokens, refresh tokens, revocation
- ✅ **RFC9728 Compliance** - Protected Resource Metadata discovery
- ✅ **Zero Configuration** - No external OAuth server needed

This replaces the previous Ory Hydra setup which lacked DCR support in open-source versions.

## Architecture

```
Claude.ai → Tailscale Funnel → MCP Server (FastMCP with InMemoryOAuthProvider)
                                     ↓
                                Mealie API
```

The MCP server handles both OAuth authorization AND MCP tool execution in a single service.

## Environment Variables

Create/update `.env` on your server:

```bash
# Mealie Configuration
MEALIE_URL=http://localhost:9000/api
MEALIE_TOKEN=your_mealie_token_here

# MCP Server Configuration
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8080

# OAuth Configuration
MCP_REQUIRE_AUTH=true
MCP_BASE_URL=https://rainworth-server.tailbf31d9.ts.net

# Optional: Authentication token for portal access
MCP_AUTH_TOKEN=your_secure_token_here
```

### Variable Explanations

- `MCP_TRANSPORT=http` - Use FastMCP's HTTP transport with built-in OAuth
- `MCP_REQUIRE_AUTH=true` - Enable OAuth authentication
- `MCP_BASE_URL` - Your public-facing URL (via Tailscale Funnel)
  - This is used for OAuth metadata and redirect URIs
  - Must be HTTPS (Tailscale Funnel provides this)

## Server Configuration

The server is automatically configured based on environment variables:

```python
# In server.py
auth_provider = None
if os.getenv("MCP_REQUIRE_AUTH", "false").lower() == "true":
    base_url = os.getenv("MCP_BASE_URL")
    if not base_url:
        print("Error: MCP_BASE_URL required when MCP_REQUIRE_AUTH=true")
        sys.exit(1)
    
    auth_provider = InMemoryOAuthProvider(
        base_url=base_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,  # Enable Dynamic Client Registration
            valid_scopes=["mcp"],  # Define available OAuth scopes
        ),
    )

mcp = FastMCP(
    name="mealie",
    auth=auth_provider,
    instructions="...",
)
```

## OAuth Endpoints

When authentication is enabled, FastMCP automatically creates these endpoints:

- `/.well-known/oauth-protected-resource` - MCP Protected Resource Metadata
- `/.well-known/openid-configuration` - OpenID Configuration
- `/auth/register` - Dynamic Client Registration (DCR)
- `/auth/authorize` - Authorization endpoint
- `/auth/token` - Token endpoint
- `/auth/revoke` - Token revocation

## Testing Locally

1. **Set environment variables:**
   ```bash
   export MEALIE_URL=http://localhost:9000/api
   export MEALIE_TOKEN=your_token
   export MCP_TRANSPORT=http
   export MCP_REQUIRE_AUTH=true
   export MCP_BASE_URL=http://localhost:8080
   ```

2. **Run the server:**
   ```bash
   python -m mealie_mcp.server
   ```

3. **Test OAuth discovery:**
   ```bash
   # Test Protected Resource Metadata
   curl http://localhost:8080/.well-known/oauth-protected-resource | jq

   # Test OpenID Configuration
   curl http://localhost:8080/.well-known/openid-configuration | jq
   
   # Check for Dynamic Client Registration
   curl http://localhost:8080/.well-known/openid-configuration | jq '.registration_endpoint'
   # Should return: "http://localhost:8080/auth/register"
   ```

## Production Deployment

### 1. Update Server Environment

SSH to your server:
```bash
ssh fraser@rainworth-server
cd ~/Repos/mealie-mcp-server
```

Edit `.env`:
```bash
nano .env
```

Update these values:
```env
MCP_TRANSPORT=http
MCP_REQUIRE_AUTH=true
MCP_BASE_URL=https://rainworth-server.tailbf31d9.ts.net
```

Remove these (no longer needed):
```env
# Remove Hydra-specific variables
OAUTH_SERVER_URL=...  # DELETE
MCP_RESOURCE_URI=...  # DELETE
```

### 2. Update Systemd Service

The systemd service file should work as-is since it already loads `.env`:

```ini
[Service]
EnvironmentFile=/home/fraser/Repos/mealie-mcp-server/.env
ExecStart=/home/fraser/Repos/mealie-mcp-server/.venv/bin/python -m mealie_mcp.server
```

### 3. Deploy

```bash
# Pull latest code
git pull

# Restart service
systemctl --user restart mealie-mcp

# Check status
systemctl --user status mealie-mcp

# View logs
journalctl --user -u mealie-mcp -f
```

Look for these startup messages:
```
Starting HTTP server on 0.0.0.0:8080
OAuth: enabled with Dynamic Client Registration (DCR)
OAuth enabled with Dynamic Client Registration at https://rainworth-server.tailbf31d9.ts.net
```

### 4. Verify Tailscale Funnel

Ensure Tailscale Funnel is running:
```bash
sudo tailscale funnel status
```

Should show:
```
https://rainworth-server.tailbf31d9.ts.net (Funnel on)
|-- / proxy http://127.0.0.1:8080
```

### 5. Test OAuth from External

From your local machine:
```bash
# Test Protected Resource Metadata
curl https://rainworth-server.tailbf31d9.ts.net/.well-known/oauth-protected-resource | jq

# Test Dynamic Client Registration is advertised
curl https://rainworth-server.tailbf31d9.ts.net/.well-known/openid-configuration | jq '.registration_endpoint'
# Should return: "https://rainworth-server.tailbf31d9.ts.net/auth/register"
```

## Connect from Claude.ai

1. Go to [claude.ai](https://claude.ai)
2. Click **Integrations** (or MCP settings)
3. Add new server:
   - **URL**: `https://rainworth-server.tailbf31d9.ts.net`
   - **Authentication**: OAuth (or Auto-detect)

4. Claude will:
   - Fetch `/.well-known/oauth-protected-resource`
   - Discover OAuth server at `/.well-known/openid-configuration`
   - See `registration_endpoint` is available
   - Auto-register as an OAuth client via DCR
   - Open authorization page for consent
   - Exchange authorization code for access token
   - Store refresh token for future sessions

5. Grant access when prompted

6. Test by asking Claude:
   - "Search for recipes"
   - "Show my meal plan"
   - "What's on my shopping list?"

## Troubleshooting

### "Failed to connect" or "Blocked" Error

**Check OAuth discovery chain:**
```bash
# 1. Protected Resource Metadata
curl https://rainworth-server.tailbf31d9.ts.net/.well-known/oauth-protected-resource | jq

# 2. OpenID Configuration
curl https://rainworth-server.tailbf31d9.ts.net/.well-known/openid-configuration | jq

# 3. Verify DCR is enabled
curl https://rainworth-server.tailbf31d9.ts.net/.well-known/openid-configuration | jq '.registration_endpoint'
# Must NOT be null
```

**Check server logs:**
```bash
journalctl --user -u mealie-mcp -f
```

Look for:
- `OAuth enabled with Dynamic Client Registration`
- Client registration requests from Claude
- Authorization requests
- Token exchange

### "Invalid redirect_uri" Error

FastMCP's `InMemoryOAuthProvider` automatically validates redirect URIs during client registration. Claude should provide its callback URL during DCR.

If you see this error, check logs for the redirect_uri Claude is trying to use.

### Tokens Don't Persist Across Server Restarts

This is expected with `InMemoryOAuthProvider`. All OAuth state (clients, tokens) is stored in memory and lost on restart.

For production persistence, you would need to:
1. Implement a custom `OAuthProvider` with database storage, OR
2. Use an external OAuth provider (GitHub, Google, etc.)

For development/personal use, in-memory is fine - Claude will just re-authenticate after server restarts.

### Test DCR Manually

You can test Dynamic Client Registration directly:

```bash
curl -X POST https://rainworth-server.tailbf31d9.ts.net/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Test Client",
    "redirect_uris": ["https://example.com/callback"],
    "scope": "mcp"
  }' | jq
```

Should return client credentials:
```json
{
  "client_id": "...",
  "client_secret": "...",
  "client_name": "Test Client",
  "redirect_uris": ["https://example.com/callback"]
}
```

## Differences from Hydra Setup

| Feature | Hydra Setup | FastMCP Built-in |
|---------|-------------|------------------|
| **DCR Support** | ❌ Not in v2.2 | ✅ Built-in |
| **Components** | 3 containers (Hydra, DB, Consent UI) | 1 Python process |
| **Configuration** | Complex (hydra.yml, SQL, env vars) | 2 env vars |
| **Storage** | PostgreSQL | In-memory |
| **Persistence** | ✅ Survives restarts | ❌ Ephemeral |
| **Claude.ai Compatible** | ❌ No DCR | ✅ Full support |
| **Deployment** | Docker Compose | Systemd service |

## Security Considerations

### For Development/Personal Use

`InMemoryOAuthProvider` is suitable when:
- You're the only user
- Server is behind Tailscale VPN
- Loss of OAuth state on restart is acceptable

### For Production/Multi-User

Consider:
- Implementing persistent storage for OAuth state
- Using an external OAuth provider (GitHub, Google, WorkOS)
- Adding rate limiting for DCR endpoint
- Implementing client secret rotation
- Monitoring for OAuth abuse

## Migration from Hydra

If you're coming from the Hydra setup:

1. **Stop Hydra containers:**
   ```bash
   cd ~/Repos/mealie-mcp-server
   podman-compose down
   ```

2. **Update environment variables** (remove Hydra-specific ones)

3. **Update server code** (already done in this commit)

4. **Deploy updated code**

5. **Test OAuth discovery**

6. **Re-add server in Claude.ai** (old tokens from Hydra won't work)

The Hydra infrastructure (containers, database, consent UI) can be archived or removed entirely.

## References

- **FastMCP OAuth Documentation**: https://gofastmcp.com/servers/auth/authentication
- **InMemoryOAuthProvider Source**: https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/auth/providers/in_memory.py
- **MCP Authorization Spec**: https://spec.modelcontextprotocol.io/specification/2024-11-05/authorization/
- **Dynamic Client Registration (RFC7591)**: https://datatracker.ietf.org/doc/html/rfc7591
- **OAuth 2.1**: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-11
