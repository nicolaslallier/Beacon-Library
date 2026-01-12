"""Client for calling Beacon Library MCP endpoints."""

import httpx
import ssl
from typing import Any, Dict, Optional
import config


class MCPClient:
    """Client for interacting with Beacon Library MCP API."""

    def __init__(
        self,
        base_url: str = config.BEACON_MCP_URL,
        agent_id: str = config.AGENT_ID,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # Allow self-signed certificates if verify_ssl is False
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,  # Set to False to accept self-signed certs
                headers={
                    "X-Agent-ID": self.agent_id,
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool and return the result."""
        client = await self._get_client()
        
        url = f"{self.base_url}/tools/{tool_name}"
        
        try:
            response = await client.post(url, json=arguments)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "error": f"HTTP {e.response.status_code}: {e.response.text}"
            }
        except httpx.RequestError as e:
            return {
                "error": f"Request failed: {str(e)}"
            }

    async def list_tools(self) -> Dict[str, Any]:
        """List available MCP tools."""
        client = await self._get_client()
        
        url = f"{self.base_url}/tools"
        
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def get_status(self) -> Dict[str, Any]:
        """Get MCP server status."""
        client = await self._get_client()
        
        url = f"{self.base_url}/status"
        
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}


# Global client instance
mcp_client = MCPClient(verify_ssl=config.VERIFY_SSL)


async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Execute a tool and return the result as a string."""
    result = await mcp_client.call_tool(tool_name, arguments)
    
    # Format the result nicely
    if "error" in result:
        return f"Error: {result['error']}"
    
    import json
    return json.dumps(result, indent=2, default=str)
