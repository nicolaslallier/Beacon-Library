"""LM Studio Agent with Beacon Library MCP tools integration."""

import json
import httpx
from typing import Any, Dict, List, Optional

import config
from tools import BEACON_TOOLS, SYSTEM_PROMPT
from mcp_client import execute_tool


class LMStudioAgent:
    """Agent that uses LM Studio for inference and Beacon MCP for tools."""

    def __init__(
        self,
        lmstudio_url: str = config.LMSTUDIO_URL,
        model: str = config.LMSTUDIO_MODEL,
    ):
        self.lmstudio_url = lmstudio_url.rstrip("/")
        self.model = model
        self.conversation_history: List[Dict[str, Any]] = []
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def reset_conversation(self):
        """Reset the conversation history."""
        self.conversation_history = []

    async def chat(self, user_message: str, max_tool_calls: int = 5) -> str:
        """
        Send a message and get a response, automatically handling tool calls.
        
        Args:
            user_message: The user's message
            max_tool_calls: Maximum number of tool calls to process in one turn
            
        Returns:
            The assistant's final response
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Build messages with system prompt
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.conversation_history
        ]

        tool_call_count = 0

        while tool_call_count < max_tool_calls:
            # Call LM Studio
            response = await self._call_lmstudio(messages)

            if response is None:
                return "Error: Failed to get response from LM Studio"

            assistant_message = response.get("choices", [{}])[0].get("message", {})
            
            # Check for tool calls
            tool_calls = assistant_message.get("tool_calls", [])

            if not tool_calls:
                # No tool calls, return the content
                content = assistant_message.get("content", "")
                self.conversation_history.append({
                    "role": "assistant",
                    "content": content
                })
                return content

            # Process tool calls
            tool_call_count += len(tool_calls)

            # Add assistant message with tool calls to history
            messages.append(assistant_message)

            # Execute each tool call
            for tool_call in tool_calls:
                function_name = tool_call.get("function", {}).get("name", "")
                function_args_str = tool_call.get("function", {}).get("arguments", "{}")
                tool_call_id = tool_call.get("id", "")

                try:
                    function_args = json.loads(function_args_str)
                except json.JSONDecodeError:
                    function_args = {}

                print(f"[TOOL] Calling {function_name} with {function_args}")

                # Execute the tool
                result = await execute_tool(function_name, function_args)

                print(f"[TOOL] Result: {result[:200]}..." if len(result) > 200 else f"[TOOL] Result: {result}")

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": function_name,
                    "content": result
                })

        # Max tool calls reached, get final response
        response = await self._call_lmstudio(messages)
        if response:
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            self.conversation_history.append({
                "role": "assistant",
                "content": content
            })
            return content

        return "Error: Failed to get final response"

    async def _call_lmstudio(self, messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Make a chat completion request to LM Studio."""
        client = await self._get_client()

        url = f"{self.lmstudio_url}/v1/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": BEACON_TOOLS,
            "tool_choice": "auto",
            "temperature": 0.7,
            "max_tokens": 4096,
        }

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            print(f"Request Error: {e}")
            return None


# Simple CLI for testing
async def main():
    """Interactive CLI for testing the agent."""
    agent = LMStudioAgent()

    print("=" * 60)
    print("Beacon Library MCP Agent (LM Studio)")
    print("=" * 60)
    print("Type 'quit' to exit, 'reset' to clear conversation")
    print()

    try:
        while True:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                break

            if user_input.lower() == "reset":
                agent.reset_conversation()
                print("Conversation reset.")
                continue

            response = await agent.chat(user_input)
            print(f"\nAssistant: {response}\n")

    finally:
        await agent.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
