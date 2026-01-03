# User Token Configuration

This directory contains the user token mapping file for multi-user Mealie access.

## Setup

1. **Create a Mealie API token for each user:**
   - Log into Mealie as each user
   - Go to User Settings → API Tokens
   - Create a new token with a descriptive name (e.g., "MCP Server Access")
   - Copy the token (it will only be shown once)

2. **Add tokens to `user_tokens.json`:**
   ```json
   {
     "users": {
       "user-id-1": "mealie-token-for-user-1",
       "user-id-2": "mealie-token-for-user-2"
     }
   }
   ```

   The user ID should match the OAuth `sub` claim (typically email address).

3. **Reload tokens without restarting:**
   The server will automatically reload tokens on each request, so you can add new users by editing the file.

## Security

- **DO NOT commit this file to git** - it's already in `.gitignore`
- Store tokens securely on the server
- Use appropriate file permissions: `chmod 600 user_tokens.json`
- Each user should only have access to their own Mealie account

## Example

If you use email addresses as OAuth identifiers:

```json
{
  "users": {
    "fraser@gibbs.family": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "partner@gibbs.family": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

## Troubleshooting

If you see "No Mealie token configured for user" errors:
1. Check that the user ID in the error matches an entry in `user_tokens.json`
2. Verify the token is still valid in Mealie
3. Check file permissions allow the MCP server to read the file
4. Review server logs for token loading errors
