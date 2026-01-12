"""FastAPI application entry point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.database import async_session_factory, close_db, init_db
from app.core.versioning import APIVersionMiddleware
from app.observability import instrument_app
from app.services.cache import close_cache_service, get_cache_service
from app.services.search import start_indexing_worker, stop_indexing_worker
from app.services.storage import get_storage_service

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("application_starting", env=settings.env)

    # Initialize database
    try:
        await init_db()
        logger.info("database_connected")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))

    # Initialize cache
    try:
        await get_cache_service()
        logger.info("cache_connected")
    except Exception as e:
        logger.warning("cache_connection_failed", error=str(e))

    # Start search indexing worker
    try:
        storage_service = get_storage_service()
        await start_indexing_worker(async_session_factory, storage_service)
        logger.info("search_indexing_worker_started")
    except Exception as e:
        logger.warning("search_indexing_worker_failed", error=str(e))

    yield

    # Shutdown
    logger.info("application_shutting_down")
    await stop_indexing_worker()
    await close_db()
    await close_cache_service()


app = FastAPI(
    title=settings.app_name,
    description="Electronic Document Management System API",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Apply observability instrumentation (tracing, metrics, structured logging)
instrument_app(app)

# Correlation ID middleware (for request tracing)
app.add_middleware(CorrelationIdMiddleware)

# API versioning middleware
app.add_middleware(APIVersionMiddleware)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("root_endpoint_called")
    return {
        "message": f"{settings.app_name} API",
        "version": settings.app_version,
        "env": settings.env,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "env": settings.env,
    }


@app.get("/api/health")
async def api_health_check():
    """Health check endpoint for frontend status monitoring."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "env": settings.env,
    }
