"""API package with all routers."""

from fastapi import APIRouter

from app.api import libraries, directories, files, browse, shares, notifications, audit, trash, mcp, search, preview, realtime

# Main API router
api_router = APIRouter()

# Include all sub-routers
api_router.include_router(
    libraries.router,
    prefix="/libraries",
    tags=["Libraries"],
)
api_router.include_router(
    directories.router,
    prefix="/libraries/{library_id}/directories",
    tags=["Directories"],
)
api_router.include_router(
    files.router,
    prefix="/files",
    tags=["Files"],
)
api_router.include_router(
    browse.router,
    prefix="/libraries/{library_id}/browse",
    tags=["Browse"],
)
api_router.include_router(
    shares.router,
    tags=["Shares"],
)
api_router.include_router(
    notifications.router,
    tags=["Notifications"],
)
api_router.include_router(
    audit.router,
    tags=["Audit"],
)
api_router.include_router(
    trash.router,
    tags=["Trash"],
)
api_router.include_router(
    mcp.router,
    tags=["MCP"],
)
api_router.include_router(
    search.router,
    tags=["Search"],
)
api_router.include_router(
    preview.router,
    tags=["Preview"],
)
api_router.include_router(
    realtime.router,
    tags=["Realtime"],
)
