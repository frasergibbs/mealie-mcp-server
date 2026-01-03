# Enhancement: Add Auth0 User Authentication

## Current State

**What works:**
- ✅ FastMCP OAuth with Dynamic Client Registration (DCR)
- ✅ Claude.ai / Claude Desktop / Claude Mobile all work
- ✅ Tailscale Funnel for public access
- ✅ Per-server token isolation (Fraser's server ≠ Sam's server)

**Security model:**
- OAuth DCR prevents random clients from connecting (must register first)
- Each server instance only has one user's Mealie token (data isolation)
- Public URLs via Tailscale Funnel (obscured but not secret)

**What's missing:**
- ❌ No user authentication in OAuth flow
- ❌ Anyone who discovers the URL can register a client and connect
- ❌ No way to verify that Fraser is accessing Fraser's server vs Sam's server

## Proposed Enhancement

Add **Auth0** (or WorkOS/Descope) for proper user authentication while keeping DCR.

### Why Auth0?

1. **Supports Dynamic Client Registration** - Required by Claude
2. **Proper user authentication** - Login screen with username/password
3. **Free tier is generous** - 7,500 monthly active users
4. **FastMCP has built-in provider** - `Auth0Provider` already exists
5. **Multi-user support** - Fraser and Sam can have separate accounts
6. **Works with claude.ai** - Public OAuth server, no Tailscale required

### Architecture After Enhancement

```
Claude (any platform)
    ↓
Tailscale Funnel (public HTTPS)
    ↓
Auth0 OAuth Server
    ├─ User Authentication (login screen)
    ├─ Dynamic Client Registration (Claude requirement)
    └─ Token issuance with user claims
    ↓
FastMCP Server (Fraser or Sam)
    ├─ Validates Auth0 token
    ├─ Extracts user ID from token claims
    └─ Uses corresponding Mealie token
    ↓
Mealie API (user-specific data)
```

### Implementation Plan

#### Step 1: Auth0 Account Setup (15 minutes)

1. Create Auth0 account at https://auth0.com
2. Create new application (type: "Regular Web Application")
3. Configure settings:
   - **Allowed Callback URLs**: `https://rainworth-server.tailbf31d9.ts.net/fraser/auth/callback`, `https://rainworth-server.tailbf31d9.ts.net/sam/auth/callback`
   - **Allowed Web Origins**: `https://rainworth-server.tailbf31d9.ts.net`
   - **Enable Dynamic Client Registration**: Settings → Advanced → OAuth → Enable DCR
4. Create users for Fraser and Sam
5. Copy Client ID, Client Secret, and Domain

#### Step 2: Code Changes (10 minutes)

**Update server.py:**

```python
from fastmcp.server.auth.providers.auth0 import Auth0Provider

# Replace InMemoryOAuthProvider with Auth0Provider
auth_provider = Auth0Provider(
    domain=os.getenv("AUTH0_DOMAIN"),  # e.g., "your-tenant.us.auth0.com"
    client_id=os.getenv("AUTH0_CLIENT_ID"),
    client_secret=os.getenv("AUTH0_CLIENT_SECRET"),
    base_url=base_url,
    audience=os.getenv("AUTH0_AUDIENCE"),  # Optional API identifier
)
```

**Update .env:**

```env
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your-client-id-here
AUTH0_CLIENT_SECRET=your-client-secret-here
AUTH0_AUDIENCE=https://rainworth-server.tailbf31d9.ts.net/api
```

**Update client.py to use token claims:**

```python
from fastmcp.server.dependencies import get_access_token

def get_client() -> MealieClient:
    """Get Mealie client based on authenticated user."""
    token = get_access_token()
    
    if token and token.claims:
        # Extract user ID from Auth0 token
        user_id = token.claims.get("sub")  # or "email"
        
        # Map Auth0 user to Mealie token
        token_store = get_token_store()
        mealie_token = token_store.get_token(user_id)
    else:
        # Fallback for unauthenticated access
        mealie_token = os.getenv("MEALIE_TOKEN")
    
    return MealieClient(token=mealie_token, user_id=user_id)
```

#### Step 3: Update User Mapping (5 minutes)

Update `config/user_tokens.json` to map Auth0 user IDs:

```json
{
  "users": {
    "auth0|abc123...": "fraser-mealie-token-here",
    "auth0|def456...": "sam-mealie-token-here"
  }
}
```

Or use email-based mapping:

```json
{
  "users": {
    "fraser@example.com": "fraser-mealie-token-here",
    "sam@example.com": "sam-mealie-token-here"
  }
}
```

#### Step 4: Testing (10 minutes)

1. Deploy updated code to server
2. Restart both services
3. Connect Claude.ai → should see Auth0 login screen
4. Login as Fraser → should access Fraser's recipes
5. Login as Sam (different browser/incognito) → should access Sam's recipes

### Benefits After Implementation

✅ **Real authentication** - Login screen with credentials  
✅ **Still works with Claude.ai** - Auth0 supports DCR  
✅ **User-based access control** - Token claims identify the user  
✅ **No more URL obscurity** - Proper auth replaces security through obscurity  
✅ **Audit trail** - Auth0 logs all authentication events  
✅ **Easy to add more users** - Just create Auth0 account + add to user_tokens.json  

### Alternative: WorkOS AuthKit

Similar setup but with some advantages:

- Built specifically for B2B/multi-tenant scenarios
- Better documentation for FastMCP integration
- Free tier: 1 million MAUs
- Simpler UI for user management

### Estimated Effort

- **Total time**: ~45 minutes
- **Complexity**: Low (FastMCP provider already exists)
- **Risk**: Low (can test locally first)
- **Downtime**: ~5 minutes during deployment

### Migration Path

1. Keep current setup running (no downtime)
2. Set up Auth0 in parallel
3. Test locally with Auth0 provider
4. Deploy to one server (Fraser) first
5. If successful, deploy to Sam's server
6. Update Claude configurations with new URLs

### Open Questions

1. **Single Auth0 app vs separate apps?**
   - Single app: Both servers use same client ID/secret
   - Separate apps: Fraser and Sam have different credentials
   - **Recommendation**: Single app, use user claims to differentiate

2. **How to handle existing sessions?**
   - Users will need to re-authenticate once
   - Claude Desktop will handle automatically
   - **Recommendation**: Announce the change, coordinate with Sam

3. **Backup plan if Auth0 is down?**
   - Could fall back to InMemoryOAuthProvider
   - **Recommendation**: Auth0 has 99.99% uptime SLA, not a concern

### Resources

- Auth0 FastMCP Example: https://github.com/jlowin/fastmcp/tree/main/examples/auth/auth0_oauth
- Auth0 DCR Docs: https://auth0.com/docs/get-started/applications/dynamic-client-registration
- FastMCP Auth0Provider: https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/server/auth/providers/auth0.py

## Acceptance Criteria

- [ ] Auth0 account created and configured
- [ ] Fraser can login with his credentials and see only his recipes
- [ ] Sam can login with her credentials and see only her recipes
- [ ] Works on Claude.ai, Claude Desktop, and Claude Mobile
- [ ] No one can access without proper authentication
- [ ] User tokens mapping documented in README
