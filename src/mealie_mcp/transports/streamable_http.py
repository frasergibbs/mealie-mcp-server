"""Streamable HTTP transport implementation for MCP with OAuth 2.1 support.

Implements the MCP Streamable HTTP transport as specified in:
https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#streamable-http

This transport supports:
- OAuth 2.1 bearer token authentication
- Server-Sent Events (SSE) for streaming responses
- Session management with Mcp-Session-Id header
- Protected Resource Metadata (RFC 9728)
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette import EventSourceResponse

from mealie_mcp.auth import TokenValidator

logger = logging.getLogger(__name__)


class StreamableHTTPServer:
    """MCP server using Streamable HTTP transport with OAuth authentication."""

    def __init__(
        self,
        mcp_instance: Any,
        require_auth: bool = True,
        auth_server_url: str | None = None,
        resource_uri: str | None = None,
    ):
        """Initialize Streamable HTTP server.

        Args:
            mcp_instance: FastMCP instance to handle MCP protocol
            require_auth: Whether to enforce OAuth token validation
            auth_server_url: OAuth authorization server URL (from env if not provided)
            resource_uri: Canonical URI of this MCP server (from env if not provided)
        """
        self.mcp = mcp_instance
        self.require_auth = require_auth
        self.app = FastAPI(title="Mealie MCP Server", version="0.1.0")
        self.sessions: dict[str, dict] = {}  # Session storage

        # OAuth configuration
        if require_auth:
            self.auth_server_url = auth_server_url or os.getenv("OAUTH_SERVER_URL")
            self.resource_uri = resource_uri or os.getenv("MCP_RESOURCE_URI")

            if not self.auth_server_url or not self.resource_uri:
                raise ValueError(
                    "OAUTH_SERVER_URL and MCP_RESOURCE_URI required when require_auth=True"
                )

            self.token_validator = TokenValidator(self.auth_server_url, self.resource_uri)
        else:
            self.auth_server_url = None
            self.resource_uri = "http://localhost:8080"
            self.token_validator = None

        self._setup_routes()

    def _setup_routes(self):
        """Configure FastAPI routes for MCP protocol."""

        @self.app.get("/.well-known/oauth-protected-resource")
        async def protected_resource_metadata():
            """OAuth 2.0 Protected Resource Metadata (RFC 9728).

            Advertises the authorization server(s) that can issue tokens for this resource.
            """
            if not self.require_auth:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="OAuth not enabled on this server",
                )

            return {
                "resource": self.resource_uri,
                "authorization_servers": [self.auth_server_url],
                "bearer_methods_supported": ["header"],
                "resource_documentation": "https://github.com/frasergibbs/mealie-mcp-server",
            }

        @self.app.post("/mcp-mealie")
        async def mcp_endpoint(
            request: Request,
            authorization: str | None = Header(None),
            mcp_session_id: str | None = Header(None, alias="Mcp-Session-Id"),
            mcp_protocol_version: str = Header("2025-06-18", alias="MCP-Protocol-Version"),
        ):
            """Main MCP endpoint - handles JSON-RPC messages over HTTP POST.

            Supports both single JSON responses and SSE streaming based on Accept header.
            """
            # Validate OAuth token if auth required
            if self.require_auth:
                token = self.token_validator.parse_authorization_header(authorization)
                token_info = await self.token_validator.validate(token)
                user_id = token_info.get("sub")
            else:
                user_id = "local"

            # Validate protocol version
            if mcp_protocol_version not in ["2025-06-18", "2025-03-26"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported MCP protocol version: {mcp_protocol_version}",
                )

            # Parse JSON-RPC message
            try:
                message = await request.json()
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON in request body",
                )

            # Handle session management
            session_id = mcp_session_id
            if message.get("method") == "initialize":
                # Create new session on initialization
                session_id = str(uuid.uuid4())
                self.sessions[session_id] = {"user_id": user_id, "protocol_version": mcp_protocol_version}
                logger.info(f"Created session {session_id} for user {user_id}")
            elif session_id and session_id not in self.sessions:
                # Session expired or invalid
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found or expired",
                )

            # Process message based on type
            if message.get("method"):
                # This is a request - may return SSE stream or single response
                accept_header = request.headers.get("accept", "")

                # Check if client supports SSE
                if "text/event-stream" in accept_header:
                    # Return SSE stream
                    return await self._handle_request_sse(message, session_id)
                else:
                    # Return single JSON response
                    return await self._handle_request_json(message, session_id)
            else:
                # This is a notification or response - return 202 Accepted
                logger.debug(f"Received notification/response: {message.get('method', 'response')}")
                return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={})

        @self.app.get("/mcp")
        async def mcp_listen(
            request: Request,
            authorization: str | None = Header(None),
            mcp_session_id: str | None = Header(None, alias="Mcp-Session-Id"),
        ):
            """Listen endpoint - opens SSE stream for server-to-client messages.

            Allows server to send notifications/requests to client without client first sending data.
            """
            # Validate OAuth token if auth required
            if self.require_auth:
                token = self.token_validator.parse_authorization_header(authorization)
                await self.token_validator.validate(token)

            # Validate session exists
            if not mcp_session_id or mcp_session_id not in self.sessions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Valid Mcp-Session-Id required for listen endpoint",
                )

            async def event_stream():
                """Generator for SSE events."""
                # Keep connection open for server-initiated messages
                # In practice, MCP servers rarely initiate messages in this transport
                try:
                    while True:
                        # This would check for pending server messages to send
                        # For now, just keep connection alive
                        await asyncio.sleep(30)
                        yield {"event": "ping", "data": ""}
                except Exception as e:
                    logger.error(f"SSE stream error: {e}")

            return EventSourceResponse(event_stream())
        @self.app.get("/mcp-mealie")
        async def mcp_listen(
            request: Request,
            authorization: str | None = Header(None),
            mcp_session_id: str | None = Header(None, alias="Mcp-Session-Id"),
        ):
            """Listen endpoint - opens SSE stream for server-to-client messages.

            Allows server to send notifications/requests to client without client first sending data.
            """
            # Validate OAuth token if auth required
            if self.require_auth:
                token = self.token_validator.parse_authorization_header(authorization)
                await self.token_validator.validate(token)

            # Validate session exists
            if not mcp_session_id or mcp_session_id not in self.sessions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Valid Mcp-Session-Id required for listen endpoint",
                )

            async def event_stream():
                """Generator for SSE events."""
                # Keep connection open for server-initiated messages
                # In practice, MCP servers rarely initiate messages in this transport
                try:
                    while True:
                        # This would check for pending server messages to send
                        # For now, just keep connection alive
                        await asyncio.sleep(30)
                        yield {"event": "ping", "data": ""}
                except Exception as e:
                    logger.error(f"SSE stream error: {e}")

            return EventSourceResponse(event_stream())
        @self.app.delete("/mcp-mealie")
        async def mcp_terminate(
            authorization: str | None = Header(None),
            mcp_session_id: str | None = Header(None, alias="Mcp-Session-Id"),
        ):
            """Terminate session endpoint - client explicitly ends session."""
            # Validate OAuth token if auth required
            if self.require_auth:
                token = self.token_validator.parse_authorization_header(authorization)
                await self.token_validator.validate(token)

            if mcp_session_id and mcp_session_id in self.sessions:
                del self.sessions[mcp_session_id]
                logger.info(f"Terminated session {mcp_session_id}")
                return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Session terminated"})
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found",
                )

    async def _handle_request_json(self, message: dict, session_id: str | None) -> JSONResponse:
        """Handle MCP request and return single JSON response."""
        try:
            # Process through FastMCP
            # Note: This is a simplified version - actual implementation depends on FastMCP internals
            response = {"jsonrpc": "2.0", "id": message.get("id"), "result": {}}

            # For initialize, include session ID in header
            headers = {}
            if message.get("method") == "initialize" and session_id:
                headers["Mcp-Session-Id"] = session_id

            return JSONResponse(content=response, headers=headers)

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32603, "message": "Internal error"},
                },
            )

    async def _handle_request_sse(self, message: dict, session_id: str | None) -> EventSourceResponse:
        """Handle MCP request and return SSE stream."""

        async def event_generator():
            """Generate SSE events for response."""
            try:
                # Send response as SSE event
                # Note: This is simplified - actual implementation would stream MCP messages
                response = {"jsonrpc": "2.0", "id": message.get("id"), "result": {}}
                yield {
                    "event": "message",
                    "data": json.dumps(response),
                }

            except Exception as e:
                logger.error(f"Error in SSE stream: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32603, "message": str(e)},
                }
                yield {
                    "event": "message",
                    "data": json.dumps(error_response),
                }

        # Include session ID in header for initialize response
        headers = {}
        if message.get("method") == "initialize" and session_id:
            headers["Mcp-Session-Id"] = session_id

        return EventSourceResponse(event_generator(), headers=headers)

    def run(self, host: str = "0.0.0.0", port: int = 8080):
        """Start the HTTP server.

        Args:
            host: Host to bind to (default: 0.0.0.0)
            port: Port to listen on (default: 8080)
        """
        import uvicorn

        logger.info(f"Starting Streamable HTTP server on {host}:{port}")
        logger.info(f"OAuth authentication: {'enabled' if self.require_auth else 'disabled'}")

        uvicorn.run(self.app, host=host, port=port)
