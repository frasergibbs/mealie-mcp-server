# Multi-User Setup Complete! ✅

## Current Status
✅ Multi-user support deployed and running
✅ Fraser's token configured (username: `fraser`)
✅ Sam's token configured (username: `sam`)
✅ Both tokens loaded and active

## How Authentication Works
1. User logs into OAuth with username/password (e.g., `fraser` / password)
2. OAuth sends username as the `sub` claim
3. MCP server maps username → Mealie token
4. All operations use that user's personal Mealie account

## Testing
Both users can now connect to the MCP server:

**Fraser:**
- Login username: `fraser`
- Ask: "What recipes do I have?"
- Will see Fraser's Mealie recipes only

**Sam:**
- Login username: `sam`
- Ask: "What recipes do I have?"
- Will see Sam's Mealie recipes only

## Token File Location
Server: `~/Repos/mealie-mcp-server/config/user_tokens.json`

## Active Configuration
```json
{
  "users": {
    "fraser": "eyJh...1t8",  ✅ Active
    "sam": "eyJh...7w"       ✅ Active
  }
}
```

## Adding More Users
To add another user:
1. Add them to OAuth: Update `ALLOWED_USERS` env var in consent UI container
2. Create their Mealie account and generate API token
3. Add mapping to `config/user_tokens.json`
4. No restart needed!

## Quick Commands

**View current tokens:**
```bash
ssh fraser@rainworth-server "cat ~/Repos/mealie-mcp-server/config/user_tokens.json"
```

**Edit tokens:**
```bash
ssh fraser@rainworth-server "nano ~/Repos/mealie-mcp-server/config/user_tokens.json"
```

**Check server logs:**
```bash
ssh fraser@rainworth-server "journalctl --user -u mealie-mcp -f"
```

**Verify token loaded:**
When Sam connects, you'll see:
```
Created new Mealie client for user: samantha.n.gibbs@outlook.com
```

## Troubleshooting

If Sam sees "No Mealie token configured for user":
1. Check the exact user ID in server logs
2. Make sure it matches `samantha.n.gibbs@outlook.com` exactly
3. If different, update the key in user_tokens.json

If Sam sees wrong recipes:
1. Verify she has her own Mealie account
2. Make sure the token belongs to Sam's account, not Fraser's
