"""OAuth token validation against authorization server."""

import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class TokenValidator:
    """Validates OAuth 2.1 access tokens with authorization server."""

    def __init__(self, auth_server_url: str, resource_uri: str):
        """Initialize token validator.

        Args:
            auth_server_url: Base URL of OAuth authorization server (e.g., https://auth.example.com)
            resource_uri: Canonical URI of this MCP server (e.g., https://mcp.example.com)
        """
        self.auth_server_url = auth_server_url.rstrip("/")
        self.resource_uri = resource_uri.rstrip("/")
        # Use admin API endpoint for introspection (Ory Hydra)
        self.introspection_endpoint = f"{self.auth_server_url}/admin/oauth2/introspect"

    async def validate(self, token: str) -> dict[str, Any]:
        """Validate access token with authorization server.

        Performs token introspection and validates:
        1. Token is active
        2. Token audience includes this resource URI (RFC 8707)

        Args:
            token: OAuth bearer token to validate

        Returns:
            Token metadata from introspection endpoint

        Raises:
            HTTPException: 401 if token invalid, 403 if wrong audience
        """
        try:
            async with httpx.AsyncClient() as client:
                # Token introspection (RFC 7662)
                response = await client.post(
                    self.introspection_endpoint,
                    data={"token": token},
                    timeout=10.0,
                )

                if response.status_code != 200:
                    logger.warning(
                        f"Token introspection failed: {response.status_code} {response.text}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token validation failed",
                        headers=self._www_authenticate_header(),
                    )

                token_info = response.json()

                # Check if token is active
                if not token_info.get("active", False):
                    logger.info("Token is not active")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token is not active",
                        headers=self._www_authenticate_header(),
                    )

                # Validate audience claim (RFC 8707)
                audiences = token_info.get("aud", [])
                if isinstance(audiences, str):
                    audiences = [audiences]

                if self.resource_uri not in audiences:
                    logger.warning(
                        f"Token audience mismatch. Expected: {self.resource_uri}, Got: {audiences}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Token not issued for this resource",
                    )

                logger.debug(f"Token validated successfully for subject: {token_info.get('sub')}")
                return token_info

        except httpx.RequestError as e:
            logger.error(f"Error connecting to authorization server: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to validate token: authorization server unavailable",
            )

    def _www_authenticate_header(self) -> dict[str, str]:
        """Generate WWW-Authenticate header for 401 responses (RFC 9728)."""
        metadata_url = f"{self.resource_uri}/.well-known/oauth-protected-resource"
        return {
            "WWW-Authenticate": f'Bearer realm="mcp", resource_metadata="{metadata_url}"'
        }

    def parse_authorization_header(self, authorization: str | None) -> str:
        """Extract bearer token from Authorization header.

        Args:
            authorization: Authorization header value

        Returns:
            Bearer token string

        Raises:
            HTTPException: 401 if header missing or malformed
        """
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers=self._www_authenticate_header(),
            )

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format. Expected: Bearer <token>",
                headers=self._www_authenticate_header(),
            )

        return parts[1]
