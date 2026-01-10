"""API endpoints for MCP server access."""

import json
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.mcp.server import LibraryPolicy, MCPServer, RateLimitConfig, create_mcp_server

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp"])

# Global MCP server instance (initialized on first request)
_mcp_server: Optional[MCPServer] = None


def get_mcp_server(db: AsyncSession = Depends(get_db)) -> MCPServer:
    """Get or create MCP server instance."""
    global _mcp_server

    if _mcp_server is None:
        from app.core.database import async_session_maker
        from app.services.storage import MinIOService

        storage = MinIOService(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

        _mcp_server = create_mcp_server(
            db_session_factory=async_session_maker,
            storage_service=storage,
            rate_limit_config=RateLimitConfig(
                requests_per_minute=settings.mcp_rate_limit_requests,
                window_seconds=settings.mcp_rate_limit_window,
            ),
        )

    return _mcp_server


@router.get(
    "/status",
    summary="MCP server status",
    description="Get MCP server status and configuration.",
)
async def get_mcp_status(
    current_user: dict = Depends(get_current_user),
):
    """Get MCP server status."""
    return {
        "enabled": settings.mcp_enabled,
        "rate_limit": {
            "requests_per_minute": settings.mcp_rate_limit_requests,
            "window_seconds": settings.mcp_rate_limit_window,
        },
        "default_write_enabled": settings.mcp_default_write_enabled,
    }


@router.get(
    "/sse",
    summary="MCP SSE endpoint",
    description="Server-Sent Events endpoint for MCP communication.",
)
async def mcp_sse_endpoint(
    request: Request,
    server: MCPServer = Depends(get_mcp_server),
):
    """SSE endpoint for MCP communication."""
    if not settings.mcp_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is disabled",
        )

    return await server.handle_sse(request)


@router.post(
    "/tools/{tool_name}",
    summary="Call MCP tool",
    description="Call an MCP tool directly via HTTP.",
)
async def call_mcp_tool(
    tool_name: str,
    request: Request,
    server: MCPServer = Depends(get_mcp_server),
):
    """Call an MCP tool directly."""
    if not settings.mcp_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is disabled",
        )

    # Get agent ID from headers
    agent_id = request.headers.get("X-Agent-ID", "anonymous")

    # Check rate limit
    if not server.check_rate_limit(agent_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Remaining": str(server.rate_limiter.get_remaining(agent_id)),
            },
        )

    # Parse request body
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Call tool
    if tool_name not in server._tools:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool not found: {tool_name}",
        )

    try:
        result = await server._tools[tool_name](body)
        return result
    except Exception as e:
        logger.error("mcp_tool_error", tool=tool_name, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/tools",
    summary="List MCP tools",
    description="List all available MCP tools.",
)
async def list_mcp_tools(
    server: MCPServer = Depends(get_mcp_server),
):
    """List available MCP tools."""
    if not settings.mcp_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server is disabled",
        )

    return {
        "tools": list(server._tools.keys()),
    }


@router.put(
    "/libraries/{library_id}/policy",
    summary="Set library MCP policy",
    description="Configure MCP access policy for a library.",
)
async def set_library_policy(
    library_id: uuid.UUID,
    read_enabled: bool = Query(True, description="Allow read access"),
    write_enabled: bool = Query(False, description="Allow write access"),
    current_user: dict = Depends(get_current_user),
    server: MCPServer = Depends(get_mcp_server),
):
    """Set MCP access policy for a library."""
    policy = LibraryPolicy(
        library_id=library_id,
        read_enabled=read_enabled,
        write_enabled=write_enabled,
    )

    server.set_library_policy(policy)

    logger.info(
        "mcp_policy_updated",
        library_id=str(library_id),
        read_enabled=read_enabled,
        write_enabled=write_enabled,
        user_id=current_user["sub"],
    )

    return {
        "library_id": str(library_id),
        "read_enabled": read_enabled,
        "write_enabled": write_enabled,
    }


@router.get(
    "/libraries/{library_id}/policy",
    summary="Get library MCP policy",
    description="Get MCP access policy for a library.",
)
async def get_library_policy(
    library_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    server: MCPServer = Depends(get_mcp_server),
):
    """Get MCP access policy for a library."""
    policy = server.get_library_policy(library_id)

    return {
        "library_id": str(library_id),
        "read_enabled": policy.read_enabled,
        "write_enabled": policy.write_enabled,
        "allowed_agents": policy.allowed_agents,
    }
