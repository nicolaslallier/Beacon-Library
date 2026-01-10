"""FastAPI application entry point."""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.observability import instrument_app

app = FastAPI(
    title="Beacon Library API",
    description="Electronic Document Management System API",
    version="0.1.0",
)

# Apply observability instrumentation (tracing, metrics, structured logging)
instrument_app(app)

# Get structured logger
logger = structlog.get_logger(__name__)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],  # Frontend dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("root_endpoint_called")
    return {"message": "Beacon Library API", "version": app.version}


@app.get("/health")
async def health_check():
    """Health check endpoint for frontend status monitoring."""
    return {"status": "ok", "version": app.version}
