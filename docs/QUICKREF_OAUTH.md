# Quick Reference - FastMCP OAuth Setup

## What Changed

Replaced custom Ory Hydra OAuth server with FastMCP's built-in `InMemoryOAuthProvider`.

**Why?**
- Hydra v2.2 lacks Dynamic Client Registration (DCR)
- Claude.ai requires DCR for auto-registration
- FastMCP has full DCR support built-in

## Deploy to Production

```bash
# SSH to server
ssh fraser@rainworth-server "cd ~/Repos/mealie-mcp-server && git pull && systemctl --user restart mealie-mcp && sleep 2 && systemctl --user status mealie-mcp"

# Then update .env on server:
ssh fraser@rainworth-server
cd ~/Repos/mealie-mcp-server
nano .env
```

**Update .env:**
```env
# Change these
MCP_TRANSPORT=http
MCP_REQUIRE_AUTH=true
MCP_BASE_URL=https://rainworth-server.tailbf31d9.ts.net

# Remove these
OAUTH_SERVER_URL=...  # DELETE
MCP_RESOURCE_URI=...  # DELETE
```

**Restart:**
```bash
systemctl --user restart mealie-mcp
journalctl --user -u mealie-mcp -f
```

## Test OAuth

From local machine:

```bash
# 1. Protected Resource Metadata
curl https://rainworth-server.tailbf31d9.ts.net/.well-known/oauth-protected-resource | jq

# 2. OpenID Configuration with DCR
curl https://rainworth-server.tailbf31d9.ts.net/.well-known/openid-configuration | jq '.registration_endpoint'
# Should return: "https://rainworth-server.tailbf31d9.ts.net/auth/register"

# 3. Test DCR
curl -X POST https://rainworth-server.tailbf31d9.ts.net/auth/register \
  -H "Content-Type: application/json" \
  -d '{"client_name":"Test","redirect_uris":["https://example.com/callback"],"scope":"mcp"}' | jq
```

## Connect from Claude.ai

1. Go to claude.ai → Integrations
2. Add server: `https://rainworth-server.tailbf31d9.ts.net`
3. Choose OAuth authentication
4. Authorize when prompted
5. Test: "Search for recipes"

## Key Files

- `src/mealie_mcp/server.py` - Main server with OAuth setup
- `docs/FASTMCP_OAUTH_SETUP.md` - Complete OAuth guide
- `docs/DEPLOYMENT.md` - Production deployment steps
- `README.md` - Updated configuration

## Environment Variables

| Old (Hydra) | New (FastMCP) | Notes |
|-------------|---------------|-------|
| `MCP_TRANSPORT=streamable-http` | `MCP_TRANSPORT=http` | Use FastMCP's native HTTP |
| `OAUTH_SERVER_URL` | `MCP_BASE_URL` | Public URL for OAuth |
| `MCP_RESOURCE_URI` | (removed) | Not needed |
| - | `MCP_REQUIRE_AUTH=true` | Enable OAuth |

## Troubleshooting

**Service won't start:**
```bash
journalctl --user -u mealie-mcp -n 100 --no-pager
```

**OAuth discovery fails:**
```bash
sudo tailscale funnel status
```

**DCR not working:**
- Check `MCP_REQUIRE_AUTH=true`
- Check `MCP_BASE_URL` is set
- Look for "OAuth enabled with Dynamic Client Registration" in logs

## Rollback

If needed:
```bash
git checkout HEAD~1
systemctl --user restart mealie-mcp
```

## Next Steps

1. ✅ Code committed
2. ⏭️ Deploy to server
3. ⏭️ Test OAuth endpoints
4. ⏭️ Connect from Claude.ai
5. ⏭️ Stop Hydra containers (optional)

## Documentation

- **Full Setup Guide**: [docs/FASTMCP_OAUTH_SETUP.md](../FASTMCP_OAUTH_SETUP.md)
- **Deployment Guide**: [docs/DEPLOYMENT.md](../DEPLOYMENT.md)
- **FastMCP Docs**: https://gofastmcp.com/servers/auth/authentication
- **InMemoryOAuthProvider**: https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/auth/providers/in_memory.py
