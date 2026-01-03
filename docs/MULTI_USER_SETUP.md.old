# Multi-User Setup Guide

This guide explains how to configure the MCP server for multiple users, each with their own Mealie account.

## Overview

The MCP server supports multi-user access where:
- Each user authenticates via OAuth (e.g., using Claude mobile)
- Each user has their own Mealie account and API token
- Actions are tracked to the correct Mealie user profile
- Users can only see/modify their own recipes and meal plans

## Architecture

```
┌─────────────┐                 ┌──────────────────┐                 ┌─────────────┐
│   Claude    │────OAuth────────▶│ OAuth Server     │                 │   Mealie    │
│   (Fraser)  │                 │ (Hydra)          │                 │   (Fraser)  │
└─────────────┘                 └──────────────────┘                 └─────────────┘
                                         │                                     ▲
                                         ▼                                     │
                                ┌──────────────────┐                          │
                                │   MCP Server     │──────user token──────────┘
                                │                  │
                                │ User Token Map:  │                  ┌─────────────┐
                                │ fraser@...→token1│──────token2─────▶│   Mealie    │
                                │ wife@...  →token2│                  │   (Wife)    │
                                └──────────────────┘                  └─────────────┘
```

## Setup Steps

### 1. Create Mealie Accounts

Each family member needs their own Mealie account:

1. Log into Mealie as admin
2. Go to Settings → Users → Manage Users
3. Create a new user for each family member
4. Set appropriate permissions (can be admin or regular user)

### 2. Generate Mealie API Tokens

For each user:

1. Log into Mealie as that user
2. Navigate to User Profile → API Tokens
3. Click "Create New Token"
4. Give it a descriptive name (e.g., "MCP Server Access")
5. Copy the token immediately (it won't be shown again)
6. Save it securely - you'll need it for the next step

### 3. Configure User Token Mapping

On your server (e.g., `rainworth-server`):

```bash
# Navigate to MCP server directory
cd ~/Repos/mealie-mcp-server

# Create/edit the user tokens file
nano config/user_tokens.json
```

Add each user with their Mealie token:

```json
{
  "users": {
    "fraser@gibbs.family": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fraser_token_here",
    "wife@gibbs.family": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.wife_token_here"
  }
}
```

**Important:** The user ID (e.g., `fraser@gibbs.family`) must match the OAuth `sub` claim from your OAuth provider.

### 4. Secure the Token File

```bash
# Set restrictive permissions
chmod 600 config/user_tokens.json

# Verify it's not tracked by git
git status  # Should not show user_tokens.json
```

### 5. Restart the MCP Server

```bash
# Restart the systemd service
systemctl --user restart mealie-mcp

# Check it started successfully
systemctl --user status mealie-mcp

# Verify tokens loaded
journalctl --user -u mealie-mcp -n 20 | grep "Loaded tokens"
```

You should see: `Loaded tokens for 2 users` (or however many you configured)

## Verifying OAuth User IDs

To find out what user ID your OAuth provider assigns:

1. Check the OAuth token introspection response
2. Look at MCP server logs when a user connects:
   ```bash
   journalctl --user -u mealie-mcp -f
   ```
3. When a user authenticates, you'll see:
   ```
   Created new Mealie client for user: fraser@gibbs.family
   ```

## Adding New Users

To add a new user without restarting:

1. Create Mealie account (if needed)
2. Generate Mealie API token for that user
3. Edit `config/user_tokens.json` and add the new entry
4. No restart needed - tokens are loaded per-request

## Testing

Test that each user sees only their content:

1. Have each family member open Claude
2. Ask to "show my recipes"
3. Verify they only see their own Mealie recipes
4. Create a test recipe and verify it appears in their Mealie account

## Troubleshooting

### Error: "No Mealie token configured for user: X"

**Cause:** User ID in OAuth doesn't match any entry in `user_tokens.json`

**Solution:**
1. Check server logs to see the exact user ID being used
2. Update `user_tokens.json` to match that exact ID
3. Ensure there are no extra spaces or characters

### Error: "Unable to validate token"

**Cause:** Mealie API token is invalid or expired

**Solution:**
1. Log into Mealie as that user
2. Check if the API token still exists
3. Generate a new token if needed
4. Update `user_tokens.json` with the new token

### User sees wrong recipes

**Cause:** Multiple users sharing the same Mealie account

**Solution:**
1. Create separate Mealie accounts for each user
2. Generate individual API tokens
3. Update `user_tokens.json` accordingly

### File permission errors

**Cause:** MCP server can't read `user_tokens.json`

**Solution:**
```bash
# Check file ownership
ls -l config/user_tokens.json

# Fix ownership if needed
chown fraser:fraser config/user_tokens.json
chmod 600 config/user_tokens.json
```

## Security Best Practices

1. **Never commit `user_tokens.json` to git** - it's already in `.gitignore`
2. **Use restrictive file permissions** - `chmod 600`
3. **Rotate tokens periodically** - regenerate Mealie tokens every few months
4. **Monitor access** - check Mealie audit logs for unexpected activity
5. **Limit token scope** - create Mealie tokens with minimal required permissions

## Advanced: Custom Token Storage Path

If you want to store tokens elsewhere:

```bash
# Set environment variable
export USER_TOKENS_PATH=/secure/path/to/tokens.json

# Or add to systemd service file
Environment="USER_TOKENS_PATH=/secure/path/to/tokens.json"
```

## Family Workflow Example

**Fraser:**
- OAuth ID: `fraser@gibbs.family`
- Mealie account: `fraser`
- Claude asks: "What recipes do I have with chicken?"
- MCP server uses Fraser's token → sees Fraser's recipes

**Wife:**
- OAuth ID: `wife@gibbs.family`
- Mealie account: `wife`
- Claude asks: "Add pasta to shopping list"
- MCP server uses Wife's token → adds to Wife's shopping list

Both can use the same MCP server simultaneously, each seeing only their own data!
