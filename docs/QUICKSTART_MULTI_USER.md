# Quick Setup: Multi-User Configuration

This guide shows you how to configure the MCP server for multi-user access after deploying.

## Step 1: Get OAuth User IDs

First, identify what user IDs your OAuth server assigns to each user. Connect to Claude with your account and check the server logs:

```bash
ssh fraser@rainworth-server "journalctl --user -u mealie-mcp -f"
```

When you authenticate, you'll see a log like:
```
Created session abc123 for user fraser@gibbs.family
```

The part after "for user" is your OAuth user ID. Have each family member connect and note their user ID.

## Step 2: Create Mealie API Tokens

For each family member:

1. Log into Mealie at your Mealie URL
2. Click on your user avatar → Profile
3. Go to "API Tokens" tab
4. Click "Create Token"
5. Give it a name like "MCP Server"
6. **Copy the token immediately** - it won't be shown again

## Step 3: Configure Token Mapping

On your server:

```bash
# SSH to server
ssh fraser@rainworth-server

# Navigate to project
cd ~/Repos/mealie-mcp-server

# Create config directory if needed
mkdir -p config

# Edit token mapping file
nano config/user_tokens.json
```

Add your mappings:

```json
{
  "users": {
    "fraser@gibbs.family": "paste_your_token_here",
    "partner@gibbs.family": "paste_partner_token_here"
  }
}
```

Save and exit (Ctrl+X, Y, Enter).

## Step 4: Secure the File

```bash
# Set restrictive permissions
chmod 600 config/user_tokens.json

# Verify ownership
ls -l config/user_tokens.json
# Should show: -rw------- 1 fraser fraser
```

## Step 5: Restart MCP Server

```bash
# Restart service
systemctl --user restart mealie-mcp

# Check it loaded tokens
journalctl --user -u mealie-mcp -n 20 | grep "Loaded tokens"
```

You should see: `Loaded tokens for 2 users`

## Step 6: Test

Have each family member:
1. Open Claude on their device
2. Connect to the MCP server
3. Ask: "What recipes do I have?"
4. Verify they see only their own Mealie recipes

## Troubleshooting

### "No Mealie token configured for user: X"

Your OAuth user ID doesn't match what's in the config file.

**Fix:**
1. Check server logs to see the exact user ID being used
2. Update `user_tokens.json` to match that ID exactly
3. No restart needed - try again immediately

### "Unable to validate token"

The Mealie API token is invalid.

**Fix:**
1. Log into Mealie as that user
2. Go to Profile → API Tokens
3. Delete the old token and create a new one
4. Update `user_tokens.json` with the new token

### Users see each other's recipes

They're using the same Mealie account.

**Fix:**
1. Create separate Mealie user accounts
2. Log in as each user and generate separate tokens
3. Map each OAuth user to their own token

## Adding More Users Later

Just edit `config/user_tokens.json` and add new entries. No restart needed!

```bash
nano config/user_tokens.json
# Add new user
# Save and exit
# Next request will pick up the change
```

## Example Working Setup

**OAuth Provider (Hydra):**
- Fraser authenticates → OAuth `sub` = "fraser@gibbs.family"
- Wife authenticates → OAuth `sub` = "wife@gibbs.family"

**Mealie:**
- User "Fraser" → Token: `eyJhbG...abc123`
- User "Wife" → Token: `eyJhbG...xyz789`

**config/user_tokens.json:**
```json
{
  "users": {
    "fraser@gibbs.family": "eyJhbG...abc123",
    "wife@gibbs.family": "eyJhbG...xyz789"
  }
}
```

**Result:**
- Fraser asks Claude about recipes → sees Fraser's Mealie recipes
- Wife asks Claude about recipes → sees Wife's Mealie recipes
- Both can use the server simultaneously! 🎉
