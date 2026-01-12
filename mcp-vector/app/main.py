"""FastAPI application for MCP Vector Server."""

import time
from contextlib import asynccontextmanager
from typing import Any, Dict

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.sse import SseServerTransport
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.routing import Mount, Route

from app.config import settings
from app.mcp.server import MCPVectorServer, create_mcp_server
from app.observability import setup_logging, setup_tracing
from app.services.access import AccessControlService
from app.services.embeddings import OllamaEmbeddingService

# Initialize logging first
setup_logging()

# Initialize tracing early (before app creation)
setup_tracing()

logger = structlog.get_logger(__name__)

# Global server instance
mcp_server: MCPVectorServer = None
access_service: AccessControlService = None
sse_transport: SseServerTransport = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global mcp_server, access_service, sse_transport

    logger.info(
        "mcp_vector_server_starting",
        version=settings.service_version,
        env=settings.env,
    )

    # Initialize services
    access_service = AccessControlService()
    await access_service.initialize()

    # Create MCP server
    mcp_server = create_mcp_server(access_service=access_service)
    
    # Create SSE transport - POST messages will be received at /messages 
    # (relative to the mount point /mcp)
    sse_transport = SseServerTransport("/messages")

    # Check Ollama availability
    embedding_service = OllamaEmbeddingService()
    ollama_healthy = await embedding_service.health_check()
    if not ollama_healthy:
        logger.warning(
            "ollama_not_available",
            message="Embeddings may fail until Ollama is ready",
        )

    logger.info("mcp_vector_server_started")

    yield

    # Cleanup
    logger.info("mcp_vector_server_stopping")
    await access_service.close()
    logger.info("mcp_vector_server_stopped")


# Create FastAPI app
app = FastAPI(
    title="MCP Vector Server",
    description="ChromaDB vector operations exposed as MCP tools for RAG workflows",
    version=settings.service_version,
    lifespan=lifespan,
)

# Setup OpenTelemetry instrumentation (must be done before app starts)
if settings.otlp_enabled:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("fastapi_instrumentation_enabled")
    except ImportError:
        pass
    except Exception as e:
        logger.warning("fastapi_instrumentation_failed", error=str(e))

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # Skip logging health checks
    if request.url.path not in ["/health", "/healthz"]:
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            agent_id=request.headers.get("X-Agent-ID", "anonymous"),
        )

    return response


# =============================================================================
# Health & Status Endpoints
# =============================================================================


@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mcp-vector"}


@app.get("/status")
async def status():
    """Detailed status with metrics."""
    if mcp_server is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    # Check ChromaDB connectivity
    from app.services.chroma import ChromaDBService
    chroma = ChromaDBService()
    collections = chroma.list_collections()

    # Check Ollama
    embedding_service = OllamaEmbeddingService()
    ollama_healthy = await embedding_service.health_check()

    return {
        "status": "healthy" if ollama_healthy else "degraded",
        "service": "mcp-vector",
        "version": settings.service_version,
        "env": settings.env,
        "dependencies": {
            "chromadb": {
                "status": "connected",
                "collections": len(collections),
            },
            "ollama": {
                "status": "connected" if ollama_healthy else "disconnected",
                "model": settings.ollama_embedding_model,
            },
        },
        "metrics": mcp_server.get_metrics(),
    }


# =============================================================================
# MCP Endpoints
# =============================================================================


@app.get("/mcp/tools")
async def list_tools():
    """List available MCP tools."""
    if mcp_server is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    tools = []
    for tool_name in ["vector.query", "vector.upsert_documents", "vector.get", "vector.delete"]:
        tools.append(mcp_server.get_tool_schema(tool_name))

    return {"tools": tools}


class ToolCallRequest(BaseModel):
    """Request body for tool calls."""
    arguments: Dict[str, Any] = {}


@app.post("/mcp/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request, body: ToolCallRequest):
    """Call an MCP tool."""
    if mcp_server is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    agent_id = request.headers.get("X-Agent-ID", "anonymous")

    result = await mcp_server.call_tool_http(
        tool_name=tool_name,
        arguments=body.arguments,
        agent_id=agent_id,
    )

    if "error" in result and result.get("error") == "Rate limit exceeded":
        return JSONResponse(
            status_code=429,
            content=result,
        )

    if "error" in result and "Unknown tool" in result.get("error", ""):
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# =============================================================================
# MCP SSE Transport Endpoints
# =============================================================================


async def handle_sse(request: Request):
    """Handle SSE connection for MCP protocol."""
    if mcp_server is None or sse_transport is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Server not initialized"}
        )
    
    # Run the MCP server with SSE transport using raw ASGI
    async with sse_transport.connect_sse(
        request.scope, 
        request.receive, 
        request._send
    ) as (read_stream, write_stream):
        await mcp_server.run_with_streams(read_stream, write_stream)


async def handle_messages(request: Request):
    """Handle POST messages for MCP protocol."""
    if sse_transport is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Server not initialized"}
        )
    
    await sse_transport.handle_post_message(
        request.scope,
        request.receive,
        request._send
    )


# Mount the SSE endpoints as a Starlette sub-application
mcp_routes = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
    ]
)

# Mount the Starlette app for MCP SSE transport
app.mount("/mcp", mcp_routes)


# =============================================================================
# Metrics Endpoint
# =============================================================================


@app.get("/metrics")
async def metrics():
    """Prometheus-style metrics endpoint."""
    if mcp_server is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    m = mcp_server.get_metrics()

    # Format as Prometheus metrics
    lines = [
        "# HELP mcp_vector_queries_total Total number of vector queries",
        "# TYPE mcp_vector_queries_total counter",
        f"mcp_vector_queries_total {m['query_count']}",
        "",
        "# HELP mcp_vector_query_latency_avg_ms Average query latency in milliseconds",
        "# TYPE mcp_vector_query_latency_avg_ms gauge",
        f"mcp_vector_query_latency_avg_ms {m['query_avg_latency_ms']}",
        "",
        "# HELP mcp_vector_upserts_total Total number of upsert operations",
        "# TYPE mcp_vector_upserts_total counter",
        f"mcp_vector_upserts_total {m['upsert_count']}",
        "",
        "# HELP mcp_vector_deletes_total Total number of delete operations",
        "# TYPE mcp_vector_deletes_total counter",
        f"mcp_vector_deletes_total {m['delete_count']}",
        "",
        "# HELP mcp_vector_errors_total Total number of errors",
        "# TYPE mcp_vector_errors_total counter",
        f"mcp_vector_errors_total {m['error_count']}",
        "",
        "# HELP mcp_vector_no_results_total Queries that returned no results",
        "# TYPE mcp_vector_no_results_total counter",
        f"mcp_vector_no_results_total {m['no_results_count']}",
        "",
        "# HELP mcp_vector_low_confidence_total Queries with low confidence results",
        "# TYPE mcp_vector_low_confidence_total counter",
        f"mcp_vector_low_confidence_total {m['low_confidence_count']}",
        "",
        "# HELP mcp_vector_no_results_rate Rate of queries with no results",
        "# TYPE mcp_vector_no_results_rate gauge",
        f"mcp_vector_no_results_rate {m['no_results_rate']:.4f}",
    ]

    return "\n".join(lines)


# =============================================================================
# Run with uvicorn (for development)
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
