"""Multi-user OAuth provider for FastMCP with Mealie token mapping."""

import logging
from typing import Any

from fastmcp.server.auth.providers.in_memory import InMemoryOAuthProvider
from mealie_mcp.user_tokens import get_token_store

logger = logging.getLogger(__name__)


class MultiUserOAuthProvider(InMemoryOAuthProvider):
    """OAuth provider that maps OAuth clients to Mealie user tokens.
    
    When a new client registers via Dynamic Client Registration, we prompt
    for which Mealie user they want to authenticate as. This creates a mapping
    from OAuth client_id → Mealie user → Mealie token.
    
    For now, we use a simple environment variable to specify which user this
    server instance represents. In the future, this could be extended to support
    interactive user selection or multiple users per server.
    """
    
    def __init__(self, *args, default_user: str | None = None, **kwargs):
        """Initialize with optional default user for client-to-user mapping.
        
        Args:
            default_user: The Mealie username to use for all OAuth clients
            *args: Passed to InMemoryOAuthProvider
            **kwargs: Passed to InMemoryOAuthProvider
        """
        super().__init__(*args, **kwargs)
        self.default_user = default_user
        self._client_user_map: dict[str, str] = {}  # client_id → username
        logger.info(f"Multi-user OAuth provider initialized (default_user={default_user})")
    
    def get_user_for_client(self, client_id: str) -> str:
        """Get the Mealie username for an OAuth client.
        
        Args:
            client_id: The OAuth client ID
            
        Returns:
            The Mealie username for this client
        """
        # Check if we have a mapping for this client
        if client_id in self._client_user_map:
            return self._client_user_map[client_id]
        
        # Use default user if configured
        if self.default_user:
            self._client_user_map[client_id] = self.default_user
            logger.info(f"Mapped client {client_id} to default user {self.default_user}")
            return self.default_user
        
        # TODO: In the future, could prompt user here or use other logic
        raise ValueError(f"No user mapping for client {client_id} and no default user configured")
    
    def get_mealie_token_for_client(self, client_id: str) -> str:
        """Get the Mealie API token for an OAuth client.
        
        Args:
            client_id: The OAuth client ID
            
        Returns:
            The Mealie API token for this client's user
        """
        username = self.get_user_for_client(client_id)
        token_store = get_token_store()
        token = token_store.get_token(username)
        
        if not token:
            raise ValueError(f"No Mealie token configured for user {username}")
        
        logger.debug(f"Retrieved Mealie token for user {username} (client {client_id})")
        return token
