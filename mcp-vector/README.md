# MCP Vector Server

A standalone MCP server that exposes ChromaDB vector operations as MCP tools for RAG (Retrieve-Augment-Generate) workflows.

## Features

- **vector.query**: Semantic search using vector similarity
- **vector.upsert_documents**: Add or update document chunks
- **vector.get**: Retrieve chunks by ID
- **vector.delete**: Remove chunks by filter

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   AI Agents     │────▶│  MCP Vector     │
│ (LM Studio,     │     │    Server       │
│  Cursor IDE)    │     │  (port 8001)    │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │ ChromaDB │ │  Ollama  │ │ Postgres │
              │ (vectors)│ │(embeddings)│ │(metadata)│
              └──────────┘ └──────────┘ └──────────┘
```

## Quick Start

### With Docker Compose

```bash
# From the Beacon-Library root
docker-compose up mcp-vector
```

### Local Development

```bash
cd mcp-vector
poetry install
poetry run uvicorn app.main:app --reload --port 8001
```

## API Endpoints

### MCP Endpoints

- `GET /mcp/tools` - List available tools
- `POST /mcp/tools/{tool_name}` - Call a tool
- `GET /mcp/sse` - Server-Sent Events for real-time communication

### Health & Status

- `GET /health` - Health check
- `GET /status` - Server status with metrics

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMADB_HOST` | `chromadb` | ChromaDB hostname |
| `CHROMADB_PORT` | `8000` | ChromaDB port |
| `OLLAMA_HOST` | `ollama` | Ollama hostname |
| `OLLAMA_PORT` | `11434` | Ollama port |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `POSTGRES_HOST` | `postgres` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `beacon_user` | PostgreSQL user |
| `POSTGRES_PASSWORD` | - | PostgreSQL password |
| `POSTGRES_DB` | `beacon_library` | PostgreSQL database |
| `MCP_RATE_LIMIT_REQUESTS` | `100` | Requests per minute |
| `LOW_CONFIDENCE_THRESHOLD` | `0.3` | Score threshold |

## Usage Examples

### vector.query

```json
{
  "text": "How does authentication work?",
  "top_k": 8,
  "filters": {
    "library_id": "uuid-here",
    "language": "python"
  }
}
```

### vector.upsert_documents

```json
{
  "chunks": ["def authenticate(user):\n    ..."],
  "metadata": [{
    "path": "/src/auth.py",
    "chunk_id": 0,
    "doc_id": "file-uuid",
    "library_id": "library-uuid",
    "line_start": 1,
    "line_end": 15
  }]
}
```

## License

MIT
