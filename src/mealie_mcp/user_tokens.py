"""User token storage for multi-user Mealie access."""

import json
import logging
import os
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class UserTokenStore:
    """Manages mapping between OAuth user IDs and Mealie API tokens."""

    def __init__(self, config_path: str | None = None):
        """Initialize user token store.

        Args:
            config_path: Path to user_tokens.json file. Defaults to config/user_tokens.json
        """
        if config_path is None:
            # Default to config/user_tokens.json in project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "user_tokens.json"
        
        self.config_path = Path(config_path)
        self._tokens: Dict[str, str] = {}
        self._load_tokens()

    def _load_tokens(self):
        """Load user token mappings from config file."""
        if not self.config_path.exists():
            logger.warning(
                f"User tokens file not found: {self.config_path}. "
                "Create it with user_id → token mappings."
            )
            return

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                self._tokens = data.get("users", {})
                logger.info(f"Loaded tokens for {len(self._tokens)} users")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.config_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading user tokens: {e}")

    def get_token(self, user_id: str) -> str | None:
        """Get Mealie API token for a user.

        Args:
            user_id: OAuth user ID (subject claim from token)

        Returns:
            Mealie API token for the user, or None if not found
        """
        token = self._tokens.get(user_id)
        
        if token is None:
            logger.warning(
                f"No Mealie token found for user: {user_id}. "
                f"Add mapping to {self.config_path}"
            )
        
        return token

    def reload(self):
        """Reload tokens from config file.
        
        Useful for adding new users without restarting the server.
        """
        logger.info("Reloading user token mappings")
        self._load_tokens()


# Global token store instance
_token_store: UserTokenStore | None = None


def get_token_store() -> UserTokenStore:
    """Get or create the global user token store instance."""
    global _token_store
    if _token_store is None:
        # Allow override via environment variable
        config_path = os.getenv("USER_TOKENS_PATH")
        _token_store = UserTokenStore(config_path)
    return _token_store
