"""API versioning middleware using Accept header."""

import re
from typing import Optional, Tuple

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Supported API versions
SUPPORTED_VERSIONS = {"v1"}
DEFAULT_VERSION = "v1"

# Accept header pattern: application/vnd.beacon.v1+json
VERSION_PATTERN = re.compile(
    r"application/vnd\.beacon\.(?P<version>v\d+)\+json",
    re.IGNORECASE,
)


def parse_accept_header(accept: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse the Accept header to extract API version.

    Args:
        accept: Accept header value

    Returns:
        Tuple of (version, media_type) or (None, None) if not found
    """
    if not accept:
        return None, None

    # Check for versioned media type
    match = VERSION_PATTERN.search(accept)
    if match:
        version = match.group("version").lower()
        return version, f"application/vnd.beacon.{version}+json"

    return None, None


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle API versioning via Accept header.

    Extracts version from Accept header and sets it in request state.
    Adds Content-Type header with version to response.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Skip versioning for non-API routes
        if not request.url.path.startswith(settings.api_prefix):
            return await call_next(request)

        # Parse Accept header
        accept = request.headers.get("Accept", "")
        version, media_type = parse_accept_header(accept)

        # Use default version if not specified
        if version is None:
            version = DEFAULT_VERSION
            media_type = f"application/vnd.beacon.{version}+json"

        # Check if version is supported
        if version not in SUPPORTED_VERSIONS:
            return JSONResponse(
                status_code=406,
                content={
                    "error": "Not Acceptable",
                    "detail": f"API version '{version}' is not supported",
                    "supported_versions": list(SUPPORTED_VERSIONS),
                },
            )

        # Store version in request state
        request.state.api_version = version

        # Process request
        response = await call_next(request)

        # Add version to response Content-Type
        # But preserve original content type for SSE and streaming responses
        if response.status_code < 400:
            original_content_type = response.headers.get("Content-Type", "")
            # Don't override SSE or streaming content types
            if not original_content_type.startswith(("text/event-stream", "text/plain")):
                response.headers["Content-Type"] = media_type
            response.headers["X-API-Version"] = version

        return response


def get_api_version(request: Request) -> str:
    """
    Get the API version from request state.

    Usage in route handlers:
        @app.get("/items")
        async def get_items(request: Request):
            version = get_api_version(request)
            ...
    """
    return getattr(request.state, "api_version", DEFAULT_VERSION)
