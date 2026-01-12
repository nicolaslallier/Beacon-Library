"""FastAPI server that provides a chat API with Beacon MCP tools."""

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
from agent import LMStudioAgent
from mcp_client import mcp_client


# Request/Response models
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    reset: bool = False


class ChatResponse(BaseModel):
    response: str
    conversation_id: str


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict = {}


# Store agents by conversation ID
agents: dict[str, LMStudioAgent] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    yield
    # Cleanup
    await mcp_client.close()
    for agent in agents.values():
        await agent.close()


app = FastAPI(
    title="Beacon MCP Agent API",
    description="Chat API with Beacon Library document access via MCP tools",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/mcp/status")
async def mcp_status():
    """Get Beacon MCP server status."""
    return await mcp_client.get_status()


@app.get("/mcp/tools")
async def list_tools():
    """List available MCP tools."""
    return await mcp_client.list_tools()


@app.post("/mcp/call")
async def call_tool(request: ToolCallRequest):
    """Call an MCP tool directly."""
    result = await mcp_client.call_tool(request.tool_name, request.arguments)
    return result


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a chat message and get a response with automatic tool usage.
    
    The agent will automatically call Beacon Library tools when needed
    to answer questions about documents.
    """
    import uuid

    # Get or create conversation
    conversation_id = request.conversation_id or str(uuid.uuid4())

    if conversation_id not in agents or request.reset:
        agents[conversation_id] = LMStudioAgent()

    agent = agents[conversation_id]

    if request.reset:
        agent.reset_conversation()

    try:
        response = await agent.chat(request.message)
        return ChatResponse(
            response=response,
            conversation_id=conversation_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chat/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and free resources."""
    if conversation_id in agents:
        await agents[conversation_id].close()
        del agents[conversation_id]
        return {"status": "deleted"}
    return {"status": "not_found"}


@app.get("/")
async def root():
    """Root endpoint with usage information."""
    return {
        "name": "Beacon MCP Agent API",
        "description": "Chat with an AI that has access to Beacon Library documents",
        "endpoints": {
            "POST /chat": "Send a message and get a response",
            "GET /mcp/status": "Check Beacon MCP server status",
            "GET /mcp/tools": "List available MCP tools",
            "POST /mcp/call": "Call an MCP tool directly",
        },
        "example": {
            "request": {
                "message": "List all my document libraries",
                "conversation_id": "optional-id-to-continue-conversation"
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=config.HOST,
        port=config.PORT,
        reload=True
    )
