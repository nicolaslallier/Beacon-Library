"""MCP Server implementation for Beacon Library.

Supports both stdio and SSE transports for AI agent access.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import structlog
from fastapi import Request, Response
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings

logger = structlog.get_logger(__name__)


class RateLimitConfig(BaseModel):
    """Rate limit configuration for MCP agents."""

    requests_per_minute: int = 100
    window_seconds: int = 60


class RateLimiter:
    """Simple in-memory rate limiter for MCP agents."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._requests: Dict[str, List[datetime]] = {}

    def is_allowed(self, agent_id: str) -> bool:
        """Check if an agent is allowed to make a request."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.config.window_seconds)

        # Clean old requests
        if agent_id in self._requests:
            self._requests[agent_id] = [
                ts for ts in self._requests[agent_id] if ts > window_start
            ]
        else:
            self._requests[agent_id] = []

        # Check limit
        if len(self._requests[agent_id]) >= self.config.requests_per_minute:
            return False

        # Record request
        self._requests[agent_id].append(now)
        return True

    def get_remaining(self, agent_id: str) -> int:
        """Get remaining requests for an agent."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.config.window_seconds)

        if agent_id not in self._requests:
            return self.config.requests_per_minute

        recent = [ts for ts in self._requests[agent_id] if ts > window_start]
        return max(0, self.config.requests_per_minute - len(recent))


class LibraryPolicy:
    """Policy configuration for library access."""

    def __init__(
        self,
        library_id: uuid.UUID,
        read_enabled: bool = True,
        write_enabled: bool = False,
        allowed_agents: Optional[List[str]] = None,
    ):
        self.library_id = library_id
        self.read_enabled = read_enabled
        self.write_enabled = write_enabled
        self.allowed_agents = allowed_agents  # None means all agents allowed

    def can_read(self, agent_id: str) -> bool:
        """Check if agent can read from library."""
        if not self.read_enabled:
            return False
        if self.allowed_agents is not None and agent_id not in self.allowed_agents:
            return False
        return True

    def can_write(self, agent_id: str) -> bool:
        """Check if agent can write to library."""
        if not self.write_enabled:
            return False
        if self.allowed_agents is not None and agent_id not in self.allowed_agents:
            return False
        return True


class MCPServer:
    """MCP Server for Beacon Library.

    Provides tools for AI agents to:
    - List libraries and their contents
    - Read file contents
    - Create/update files (if write policy allows)
    - Search files
    """

    def __init__(
        self,
        db_session_factory: Callable,
        storage_service: Any,
        rate_limit_config: Optional[RateLimitConfig] = None,
    ):
        self.db_session_factory = db_session_factory
        self.storage_service = storage_service
        self.rate_limiter = RateLimiter(
            rate_limit_config or RateLimitConfig(
                requests_per_minute=settings.mcp_rate_limit_requests,
                window_seconds=settings.mcp_rate_limit_window,
            )
        )
        self._library_policies: Dict[uuid.UUID, LibraryPolicy] = {}
        self._tools: Dict[str, Callable] = {}
        self._server = Server("beacon-library")

        # Register handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up MCP protocol handlers."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            tools = [
                Tool(
                    name="list_libraries",
                    description="List all available document libraries",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="browse_library",
                    description="Browse contents of a library or directory",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "library_id": {
                                "type": "string",
                                "description": "UUID of the library",
                            },
                            "path": {
                                "type": "string",
                                "description": "Path within the library (optional)",
                                "default": "/",
                            },
                        },
                        "required": ["library_id"],
                    },
                ),
                Tool(
                    name="read_file",
                    description="Read the contents of a file",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_id": {
                                "type": "string",
                                "description": "UUID of the file to read",
                            },
                        },
                        "required": ["file_id"],
                    },
                ),
                Tool(
                    name="search_files",
                    description="Search for files by name or content",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                            },
                            "library_id": {
                                "type": "string",
                                "description": "Limit search to specific library (optional)",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="create_file",
                    description="Create a new file in a library (requires write permission)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "library_id": {
                                "type": "string",
                                "description": "UUID of the library",
                            },
                            "path": {
                                "type": "string",
                                "description": "Path for the new file",
                            },
                            "content": {
                                "type": "string",
                                "description": "File content",
                            },
                        },
                        "required": ["library_id", "path", "content"],
                    },
                ),
                Tool(
                    name="update_file",
                    description="Update an existing file (requires write permission)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_id": {
                                "type": "string",
                                "description": "UUID of the file to update",
                            },
                            "content": {
                                "type": "string",
                                "description": "New file content",
                            },
                        },
                        "required": ["file_id", "content"],
                    },
                ),
            ]
            return tools

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """Handle tool calls."""
            try:
                if name in self._tools:
                    result = await self._tools[name](arguments)
                    # IMPORTANT: mcp.server.Server.call_tool expects an Iterable[Content],
                    # not a CallToolResult. The server wrapper will construct CallToolResult.
                    return [TextContent(type="text", text=json.dumps(result))]
                else:
                    # Raise so the MCP server wrapper marks isError=True
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error("mcp_tool_error", tool=name, error=str(e))
                # Raise so the MCP server wrapper marks isError=True
                raise

    def register_tool(self, name: str, handler: Callable):
        """Register a tool handler."""
        self._tools[name] = handler

    def get_tool_schema(self, name: str) -> dict:
        """Get the schema for a tool in MCP format."""
        # Tool schemas for the standard MCP protocol
        schemas = {
            "list_libraries": {
                "name": "list_libraries",
                "description": "List all available libraries in Beacon Library",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            "browse_library": {
                "name": "browse_library",
                "description": "Browse contents of a library or directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "library_id": {
                            "type": "string",
                            "description": "UUID of the library to browse",
                        },
                        "path": {
                            "type": "string",
                            "description": "Path within the library (default: /)",
                            "default": "/",
                        },
                    },
                    "required": ["library_id"],
                },
            },
            "read_file": {
                "name": "read_file",
                "description": "Read the contents of a text file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "UUID of the file to read",
                        },
                    },
                    "required": ["file_id"],
                },
            },
            "search_files": {
                "name": "search_files",
                "description": "Search for files by name",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "library_id": {
                            "type": "string",
                            "description": "Optional: limit search to specific library",
                        },
                    },
                    "required": ["query"],
                },
            },
            "create_file": {
                "name": "create_file",
                "description": "Create a new text file in a library",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "library_id": {
                            "type": "string",
                            "description": "UUID of the library",
                        },
                        "path": {
                            "type": "string",
                            "description": "Full path for the new file",
                        },
                        "content": {
                            "type": "string",
                            "description": "Content of the file",
                        },
                    },
                    "required": ["library_id", "path", "content"],
                },
            },
            "update_file": {
                "name": "update_file",
                "description": "Update an existing file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "UUID of the file to update",
                        },
                        "content": {
                            "type": "string",
                            "description": "New content for the file",
                        },
                    },
                    "required": ["file_id", "content"],
                },
            },
        }
        return schemas.get(name, {"name": name, "description": "Unknown tool", "inputSchema": {"type": "object"}})

    def set_library_policy(self, policy: LibraryPolicy):
        """Set access policy for a library."""
        self._library_policies[policy.library_id] = policy

    def get_library_policy(self, library_id: uuid.UUID) -> LibraryPolicy:
        """Get access policy for a library."""
        if library_id in self._library_policies:
            return self._library_policies[library_id]

        # Default policy: read-only, based on settings
        return LibraryPolicy(
            library_id=library_id,
            read_enabled=True,
            write_enabled=settings.mcp_default_write_enabled,
        )

    def check_rate_limit(self, agent_id: str) -> bool:
        """Check if agent is within rate limits."""
        return self.rate_limiter.is_allowed(agent_id)

    async def handle_stdio(self):
        """Handle MCP communication over stdio."""
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="beacon-library",
                    server_version="1.0.0",
                ),
            )

    async def handle_sse(self, request: Request) -> EventSourceResponse:
        """Handle MCP communication over SSE.

        This creates an SSE endpoint for real-time communication with AI agents.
        """
        agent_id = request.headers.get("X-Agent-ID", "anonymous")

        # Check rate limit
        if not self.check_rate_limit(agent_id):
            async def rate_limit_error():
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "error": "Rate limit exceeded",
                        "remaining": self.rate_limiter.get_remaining(agent_id),
                    }),
                }
            return EventSourceResponse(rate_limit_error())

        async def event_generator():
            """Generate SSE events for MCP communication."""
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "server": "beacon-library",
                    "version": "1.0.0",
                    "agent_id": agent_id,
                }),
            }

            # Keep connection alive with heartbeats
            while True:
                await asyncio.sleep(30)
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}),
                }

        return EventSourceResponse(event_generator())


def create_mcp_server(
    db_session_factory: Callable,
    storage_service: Any,
    rate_limit_config: Optional[RateLimitConfig] = None,
) -> MCPServer:
    """Create and configure an MCP server instance."""
    server = MCPServer(
        db_session_factory=db_session_factory,
        storage_service=storage_service,
        rate_limit_config=rate_limit_config,
    )

    # Register tools
    from app.mcp.tools import register_tools
    register_tools(server)

    return server
