# Multi-User Setup Guide

This guide explains how Fraser and Sam each get their own Mealie MCP server instance with secure Tailscale authentication.

## Architecture Overview

**Single-tenant servers**: Each person runs their own MCP server process:
- **Fraser**: Port 8080, uses Fraser's Mealie token, accessible at `/fraser` path
- **Sam**: Port 8081, uses Sam's Mealie token, accessible at `/sam` path

**Security**: Tailscale Serve (not Funnel) requires Tailscale authentication
- Only devices on your Tailscale network can access the servers
- No public internet access - proper authentication, not security through obscurity
- Each person's server only accesses their own Mealie recipes/meal plans

## Prerequisites

1. **Tailscale installed** on rainworth-server and all devices that will access the MCP servers
2. **Mealie API tokens** for both Fraser and Sam
   - Generate in Mealie: User Profile → Manage API Tokens → Generate
3. **Server access**: SSH access to rainworth-server as fraser user

## Quick Deploy

```bash
# From your local machine
cd ~/Repos/mealie-mcp-server

# Push code changes
git add -A
git commit -m "Multi-user setup with Tailscale Serve"
git push

# Deploy to server
ssh fraser@rainworth-server "cd ~/Repos/mealie-mcp-server && git pull && scripts/deploy-multi-user.sh"
```

## URLs for Claude

**Fraser**: `https://rainworth-server.tailbf31d9.ts.net/fraser/mcp`  
**Sam**: `https://rainworth-server.tailbf31d9.ts.net/sam/mcp`

## Security Model

### Tailscale Serve (Proper Authentication)

✅ Requires Tailscale authentication  
✅ Only Tailscale network devices can access  
✅ Each server isolated to one user's Mealie account  
✅ No security through obscurity

### vs. Previous Funnel Setup

❌ Public internet access via random URL  
❌ No real user authentication  
❌ Security through URL obscurity

## Service Management

View status:
```bash
systemctl --user status mealie-mcp-fraser
systemctl --user status mealie-mcp-sam
```

View logs:
```bash
journalctl --user -u mealie-mcp-fraser -f
journalctl --user -u mealie-mcp-sam -f
```

Restart:
```bash
systemctl --user restart mealie-mcp-fraser mealie-mcp-sam
```

Update code:
```bash
ssh fraser@rainworth-server "cd ~/Repos/mealie-mcp-server && git pull && systemctl --user restart mealie-mcp-fraser mealie-mcp-sam"
```

## Troubleshooting

Check Tailscale Serve status:
```bash
sudo tailscale serve status
```

Test connectivity:
```bash
# Locally on server
curl -I http://127.0.0.1:8080/
curl -I http://127.0.0.1:8081/

# Via Tailscale (from authenticated device)
curl -I https://rainworth-server.tailbf31d9.ts.net/fraser/
curl -I https://rainworth-server.tailbf31d9.ts.net/sam/
```

See full documentation in [docs/MULTI_USER_SETUP_DETAILED.md](./MULTI_USER_SETUP_DETAILED.md) for:
- Detailed setup steps
- Token configuration
- Architecture diagrams
- Common issues and solutions
