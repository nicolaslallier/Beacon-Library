# Beacon Library MCP Agent

This is a bridge service that connects **LM Studio** to **Beacon Library** via MCP (Model Context Protocol).

It allows your local LLM running in LM Studio to:
- Browse document libraries
- Read file contents
- Search for files
- Create and update files (if write permissions are enabled)

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  LM Studio  │────▶│   MCP Agent      │────▶│  Beacon Library     │
│  (Local LLM)│◀────│   (This Service) │◀────│  MCP API            │
└─────────────┘     └──────────────────┘     └─────────────────────┘
```

## Quick Start

### 1. Install dependencies

```bash
cd mcp-agent
pip install -r requirements.txt
```

### 2. Configure

Copy the example config and adjust if needed:

```bash
cp env.example .env
```

Edit `.env`:
```env
# Your LM Studio server
LMSTUDIO_URL=http://192.168.2.35:1234

# Beacon Library API
BEACON_MCP_URL=https://beacon-library.famillelallier.net/api/mcp
```

### 3. Run the agent

**Option A: Interactive CLI**
```bash
python agent.py
```

**Option B: HTTP API Server**
```bash
python server.py
```

Server runs at `http://localhost:8080`

## API Endpoints (Server Mode)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Send a message and get AI response |
| `/mcp/status` | GET | Check Beacon MCP status |
| `/mcp/tools` | GET | List available tools |
| `/mcp/call` | POST | Call a tool directly |

### Chat Example

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What libraries do I have?"}'
```

Response:
```json
{
  "response": "You have 2 document libraries: ...",
  "conversation_id": "abc-123"
}
```

### Continue Conversation

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me the contents of the first one",
    "conversation_id": "abc-123"
  }'
```

## Available Tools

The agent can use these tools to access Beacon Library:

1. **list_libraries** - List all document libraries
2. **browse_library** - Browse folders/files in a library
3. **read_file** - Read text file contents
4. **search_files** - Search for files by name
5. **create_file** - Create new files (requires write permission)
6. **update_file** - Update existing files (requires write permission)

## Requirements

- Python 3.10+
- LM Studio running with a model that supports function calling
- Beacon Library with MCP enabled

## LM Studio Model Requirements

For best results, use a model that supports **function calling / tool use**:
- Llama 3.1+ (8B, 70B)
- Mistral models with function calling
- Qwen 2.5+
- Any model with `tool_use` capability

## Troubleshooting

### "Tool calls not working"

Make sure your LM Studio model supports function calling. Check the model card.

### "Connection refused to Beacon"

Verify the BEACON_MCP_URL is correct and accessible:
```bash
curl https://beacon-library.famillelallier.net/api/mcp/tools
```

### "Rate limit exceeded"

The MCP server has rate limiting (100 requests/minute). Wait a moment and try again.
