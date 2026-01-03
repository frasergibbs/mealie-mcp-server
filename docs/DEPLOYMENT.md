# Deployment Instructions - FastMCP OAuth

Quick deployment guide for updating the production server to use FastMCP's built-in OAuth.

## Pre-Deployment Checklist

- [x] Code updated to use `InMemoryOAuthProvider`
- [x] Documentation created ([FASTMCP_OAUTH_SETUP.md](FASTMCP_OAUTH_SETUP.md))
- [x] README updated
- [x] Local imports tested

## Deployment Steps

### 1. Connect to Server

```bash
ssh fraser@rainworth-server
cd ~/Repos/mealie-mcp-server
```

### 2. Pull Latest Code

```bash
git pull origin main
```

### 3. Update Environment Variables

Edit `.env`:
```bash
nano .env
```

**Update these:**
```env
# Change transport
MCP_TRANSPORT=http

# Enable OAuth
MCP_REQUIRE_AUTH=true

# Set public URL
MCP_BASE_URL=https://rainworth-server.tailbf31d9.ts.net
```

**Remove these (no longer needed):**
```env
OAUTH_SERVER_URL=...  # DELETE - was for Hydra
MCP_RESOURCE_URI=...  # DELETE - was for Hydra
```

**Keep these:**
```env
MEALIE_URL=http://localhost:9000/api
MEALIE_TOKEN=<your_token>
MCP_HOST=0.0.0.0
MCP_PORT=8080
MCP_AUTH_TOKEN=<your_portal_token>
RULES_DATA_DIR=/home/fraser/Repos/mealie-mcp-server/data
PORTAL_HOST=0.0.0.0
PORTAL_PORT=8081
```

### 4. Restart Service

```bash
systemctl --user restart mealie-mcp
sleep 2
systemctl --user status mealie-mcp
```

**Expected output:**
```
● mealie-mcp.service - Mealie MCP Server
     Loaded: loaded (/home/fraser/.config/systemd/user/mealie-mcp.service; enabled)
     Active: active (running)
```

### 5. Check Logs

```bash
journalctl --user -u mealie-mcp -n 50 --no-pager
```

**Look for:**
```
Starting HTTP server on 0.0.0.0:8080
OAuth enabled with Dynamic Client Registration at https://rainworth-server.tailbf31d9.ts.net
OAuth: enabled with Dynamic Client Registration (DCR)
```

### 6. Verify OAuth Endpoints

From your local machine:

```bash
# Test Protected Resource Metadata
curl -s https://rainworth-server.tailbf31d9.ts.net/.well-known/oauth-protected-resource | jq

# Expected output:
{
  "authorization_servers": [
    "https://rainworth-server.tailbf31d9.ts.net"
  ]
}
```

```bash
# Test OpenID Configuration
curl -s https://rainworth-server.tailbf31d9.ts.net/.well-known/openid-configuration | jq

# Check for DCR endpoint
curl -s https://rainworth-server.tailbf31d9.ts.net/.well-known/openid-configuration | jq '.registration_endpoint'

# Expected: "https://rainworth-server.tailbf31d9.ts.net/auth/register"
```

### 7. Test Dynamic Client Registration

```bash
curl -X POST https://rainworth-server.tailbf31d9.ts.net/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Test Client",
    "redirect_uris": ["https://example.com/callback"],
    "scope": "mcp"
  }' | jq
```

**Expected response:**
```json
{
  "client_id": "...",
  "client_secret": "...",
  "client_name": "Test Client",
  "redirect_uris": ["https://example.com/callback"],
  "scope": "mcp"
}
```

## Post-Deployment

### Stop Hydra Infrastructure (Optional)

The Hydra containers are no longer needed:

```bash
cd ~/Repos/mealie-mcp-server
podman-compose down
```

This will stop:
- `mealie-hydra` - OAuth server
- `mealie-oauth-db` - PostgreSQL database
- `mealie-hydra-consent` - Consent UI

You can keep them stopped or remove them entirely.

### Connect from Claude.ai

1. Go to [claude.ai](https://claude.ai)
2. Open **Settings** → **Integrations** (or MCP section)
3. Add new MCP server:
   - **URL**: `https://rainworth-server.tailbf31d9.ts.net`
   - **Authentication**: OAuth (or let Claude auto-detect)

4. Claude will:
   - Discover OAuth via Protected Resource Metadata
   - Auto-register as a client via DCR
   - Show authorization consent page
   - Exchange code for access token

5. Click **Authorize** when prompted

6. Test with: "Search for chicken recipes"

## Rollback Plan

If something goes wrong:

### Quick Rollback

```bash
# On server
cd ~/Repos/mealie-mcp-server
git checkout HEAD~1  # Go back one commit
systemctl --user restart mealie-mcp
```

### Full Rollback to Hydra

```bash
# Restore Hydra containers
podman-compose up -d

# Update .env
nano .env
# Change:
#   MCP_TRANSPORT=streamable-http
#   OAUTH_SERVER_URL=https://rainworth-server.tailbf31d9.ts.net/oauth
#   MCP_RESOURCE_URI=https://rainworth-server.tailbf31d9.ts.net

# Restore old code
git checkout <commit-before-fastmcp-oauth>

# Restart
systemctl --user restart mealie-mcp
```

## Troubleshooting

### Service Won't Start

```bash
# Check for errors
journalctl --user -u mealie-mcp -n 100 --no-pager

# Common issues:
# - Missing MCP_BASE_URL
# - Typo in environment variables
# - Port already in use (check: ss -tulpn | grep 8080)
```

### OAuth Discovery Fails

```bash
# Verify Tailscale Funnel is running
sudo tailscale funnel status

# Should show:
# https://rainworth-server.tailbf31d9.ts.net (Funnel on)
# |-- / proxy http://127.0.0.1:8080

# If not running:
sudo tailscale funnel 8080
```

### "registration_endpoint: null"

This means FastMCP's OAuth provider isn't configured correctly.

Check:
1. `MCP_REQUIRE_AUTH=true` is set
2. `MCP_BASE_URL` is set correctly
3. Server logs show "OAuth enabled with Dynamic Client Registration"

### Claude Can't Connect

1. **Check server is accessible:**
   ```bash
   curl https://rainworth-server.tailbf31d9.ts.net/.well-known/oauth-protected-resource
   ```

2. **Check browser console** (F12) for errors

3. **Try re-adding server** in Claude (remove and add again)

4. **Check server logs** for authorization requests

## Success Indicators

✅ Service running (`systemctl --user status mealie-mcp`)
✅ Logs show "OAuth enabled with Dynamic Client Registration"
✅ `/.well-known/oauth-protected-resource` returns JSON
✅ `/.well-known/openid-configuration` includes `registration_endpoint`
✅ DCR test returns client credentials
✅ Claude successfully authorizes and can call MCP tools

## Next Steps After Deployment

1. Test all MCP tools from Claude:
   - Search recipes
   - Get meal plan
   - View shopping lists

2. Monitor logs for any errors

3. Archive Hydra documentation (optional):
   ```bash
   git mv docs/OAUTH_SETUP.md docs/archive/OAUTH_SETUP_HYDRA.md
   git mv docs/TAILSCALE_OAUTH_SETUP.md docs/archive/TAILSCALE_OAUTH_SETUP_HYDRA.md
   ```

4. Update any external documentation that references the old OAuth setup

## Support

If you encounter issues:

1. Check [FASTMCP_OAUTH_SETUP.md](FASTMCP_OAUTH_SETUP.md) troubleshooting section
2. Review FastMCP OAuth examples: https://github.com/jlowin/fastmcp/tree/main/tests/client/auth
3. Check MCP Authorization spec: https://spec.modelcontextprotocol.io/specification/2024-11-05/authorization/
