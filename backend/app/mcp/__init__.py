"""MCP (Model Context Protocol) server for AI agent access to Beacon Library."""

from app.mcp.server import create_mcp_server, MCPServer
from app.mcp.tools import register_tools

__all__ = ["create_mcp_server", "MCPServer", "register_tools"]
