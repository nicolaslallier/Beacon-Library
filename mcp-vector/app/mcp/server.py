"""MCP Vector Server implementation.

Provides vector search and indexing capabilities as MCP tools.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import structlog
from fastapi import Request
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities, Tool, ToolsCapability
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.services.access import AccessControlService

logger = structlog.get_logger(__name__)


class MCPVectorServer:
    """MCP Server for vector operations.

    Provides tools for AI agents to:
    - Search documents using vector similarity (vector.query)
    - Index/update documents (vector.upsert_documents)
    - Retrieve documents by ID (vector.get)
    - Delete documents (vector.delete)
    """

    def __init__(
        self,
        access_service: Optional[AccessControlService] = None,
    ):
        self.access_service = access_service or AccessControlService()
        self._tools: Dict[str, Callable] = {}
        self._server = Server("mcp-vector")
        self.current_agent_id: Optional[str] = None

        # Metrics
        self.metrics: Dict[str, Any] = {
            "query_count": 0,
            "query_latency_sum": 0,
            "upsert_count": 0,
            "delete_count": 0,
            "error_count": 0,
            "no_results_count": 0,
            "low_confidence_count": 0,
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

        # Register handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Set up MCP protocol handlers."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available vector tools."""
            tools = [
                Tool(
                    name="vector.query",
                    description="Semantic search by similarity. Returns relevant chunks with metadata for traceability.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Query text for semantic search",
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Number of results to return (default: 8, max: 50)",
                                "default": 8,
                                "minimum": 1,
                                "maximum": 50,
                            },
                            "filters": {
                                "type": "object",
                                "description": "Optional metadata filters",
                                "properties": {
                                    "path": {
                                        "type": "string",
                                        "description": "File path filter (exact or prefix)",
                                    },
                                    "doc_id": {
                                        "type": "string",
                                        "description": "Document/file UUID filter",
                                    },
                                    "library_id": {
                                        "type": "string",
                                        "description": "Library UUID to scope search",
                                    },
                                    "doc_type": {
                                        "type": "string",
                                        "description": "MIME type filter",
                                    },
                                    "language": {
                                        "type": "string",
                                        "description": "Programming language filter",
                                    },
                                    "chunk_type": {
                                        "type": "string",
                                        "description": "Chunk type (function, class, section, etc.)",
                                    },
                                    "tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Tag filter",
                                    },
                                },
                            },
                        },
                        "required": ["text"],
                    },
                ),
                Tool(
                    name="vector.upsert_documents",
                    description="Add or update document chunks in the vector store. Idempotent based on library_id + doc_id + chunk_id.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chunks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of chunk texts to upsert",
                            },
                            "metadata": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "path": {
                                            "type": "string",
                                            "description": "File path (required)",
                                        },
                                        "chunk_id": {
                                            "type": "integer",
                                            "description": "Chunk index within document (required)",
                                        },
                                        "doc_id": {
                                            "type": "string",
                                            "description": "Document UUID (recommended)",
                                        },
                                        "library_id": {
                                            "type": "string",
                                            "description": "Library UUID (required)",
                                        },
                                        "line_start": {"type": "integer"},
                                        "line_end": {"type": "integer"},
                                        "page": {"type": "integer"},
                                        "hash": {
                                            "type": "string",
                                            "description": "Chunk fingerprint",
                                        },
                                        "updated_at": {
                                            "type": "string",
                                            "description": "ISO-8601 timestamp",
                                        },
                                        "language": {"type": "string"},
                                        "chunk_type": {"type": "string"},
                                        "name": {"type": "string"},
                                    },
                                    "required": ["path", "chunk_id", "library_id"],
                                },
                                "description": "Metadata for each chunk (aligned 1:1 with chunks)",
                            },
                        },
                        "required": ["chunks", "metadata"],
                    },
                ),
                Tool(
                    name="vector.get",
                    description="Fetch chunks by exact IDs.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of chunk IDs to retrieve",
                            },
                        },
                        "required": ["ids"],
                    },
                ),
                Tool(
                    name="vector.delete",
                    description="Delete chunks by filter (doc_id, path_prefix, or library_id).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "where": {
                                "type": "object",
                                "description": "Filter conditions (at least one required)",
                                "properties": {
                                    "doc_id": {
                                        "type": "string",
                                        "description": "Delete all chunks for a document",
                                    },
                                    "path_prefix": {
                                        "type": "string",
                                        "description": "Delete chunks with paths starting with prefix",
                                    },
                                    "library_id": {
                                        "type": "string",
                                        "description": "Delete all chunks in a library",
                                    },
                                },
                            },
                        },
                        "required": ["where"],
                    },
                ),
            ]
            return tools

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """Handle tool calls."""
            from mcp.types import TextContent

            try:
                if name in self._tools:
                    result = await self._tools[name](arguments)
                    return [TextContent(type="text", text=json.dumps(result))]
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error("mcp_tool_error", tool=name, error=str(e))
                raise

    def register_tool(self, name: str, handler: Callable):
        """Register a tool handler."""
        self._tools[name] = handler

    def get_tool_schema(self, name: str) -> dict:
        """Get the schema for a tool in MCP format."""
        schemas = {
            "vector.query": {
                "name": "vector.query",
                "description": "Semantic search by similarity",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Query text"},
                        "top_k": {"type": "integer", "default": 8},
                        "filters": {"type": "object"},
                    },
                    "required": ["text"],
                },
            },
            "vector.upsert_documents": {
                "name": "vector.upsert_documents",
                "description": "Add or update document chunks",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "chunks": {"type": "array", "items": {"type": "string"}},
                        "metadata": {"type": "array"},
                    },
                    "required": ["chunks", "metadata"],
                },
            },
            "vector.get": {
                "name": "vector.get",
                "description": "Fetch chunks by IDs",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["ids"],
                },
            },
            "vector.delete": {
                "name": "vector.delete",
                "description": "Delete chunks by filter",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "where": {"type": "object"},
                    },
                    "required": ["where"],
                },
            },
        }
        return schemas.get(
            name,
            {"name": name, "description": "Unknown tool", "inputSchema": {"type": "object"}},
        )

    async def handle_stdio(self):
        """Handle MCP communication over stdio."""
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="mcp-vector",
                    server_version=settings.service_version,
                    capabilities=ServerCapabilities(
                        tools=ToolsCapability(listChanged=False),
                    ),
                ),
            )

    async def run_with_streams(self, read_stream, write_stream):
        """Run MCP server with provided streams (for SSE transport)."""
        await self._server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mcp-vector",
                server_version=settings.service_version,
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=False),
                ),
            ),
        )

    async def handle_sse(self, request: Request) -> EventSourceResponse:
        """Handle MCP communication over SSE."""
        agent_id = request.headers.get("X-Agent-ID", "anonymous")
        self.current_agent_id = agent_id

        # Check rate limit
        if not self.access_service.check_rate_limit(agent_id):
            async def rate_limit_error():
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "error": "Rate limit exceeded",
                        "remaining": self.access_service.get_rate_limit_remaining(agent_id),
                    }),
                }
            return EventSourceResponse(rate_limit_error())

        async def event_generator():
            """Generate SSE events for MCP communication."""
            yield {
                "event": "connected",
                "data": json.dumps({
                    "server": "mcp-vector",
                    "version": settings.service_version,
                    "agent_id": agent_id,
                }),
            }

            # Keep connection alive with heartbeats
            while True:
                await asyncio.sleep(30)
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }),
                }

        return EventSourceResponse(event_generator())

    async def call_tool_http(
        self,
        tool_name: str,
        arguments: dict,
        agent_id: str = "anonymous",
    ) -> dict:
        """Call a tool via HTTP (for REST API endpoint)."""
        self.current_agent_id = agent_id

        # Check rate limit
        if not self.access_service.check_rate_limit(agent_id):
            return {
                "error": "Rate limit exceeded",
                "remaining": self.access_service.get_rate_limit_remaining(agent_id),
            }

        if tool_name not in self._tools:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return await self._tools[tool_name](arguments)
        except Exception as e:
            logger.error(
                "http_tool_call_error",
                tool=tool_name,
                agent_id=agent_id,
                error=str(e),
            )
            return {"error": str(e)}

    def get_metrics(self) -> dict:
        """Get server metrics."""
        query_count = self.metrics["query_count"]
        avg_latency = (
            self.metrics["query_latency_sum"] / query_count
            if query_count > 0
            else 0
        )

        return {
            "query_count": query_count,
            "query_avg_latency_ms": round(avg_latency, 2),
            "upsert_count": self.metrics["upsert_count"],
            "delete_count": self.metrics["delete_count"],
            "error_count": self.metrics["error_count"],
            "no_results_count": self.metrics["no_results_count"],
            "low_confidence_count": self.metrics["low_confidence_count"],
            "no_results_rate": (
                self.metrics["no_results_count"] / query_count
                if query_count > 0
                else 0
            ),
            "start_time": self.metrics["start_time"],
        }


def create_mcp_server(
    access_service: Optional[AccessControlService] = None,
) -> MCPVectorServer:
    """Create and configure an MCP Vector Server instance."""
    server = MCPVectorServer(access_service=access_service)

    # Register tools
    from app.mcp.tools import register_tools
    register_tools(server)

    return server
