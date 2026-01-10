"""Correlation ID middleware for request tracing."""

import uuid
from contextvars import ContextVar
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

# Context variable to store correlation ID across async boundaries
correlation_id_var: ContextVar[Optional[uuid.UUID]] = ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> uuid.UUID:
    """Get the current correlation ID from context.

    Returns a new UUID if no correlation ID is set.
    """
    cid = correlation_id_var.get()
    if cid is None:
        cid = uuid.uuid4()
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(correlation_id: uuid.UUID) -> None:
    """Set the correlation ID in context."""
    correlation_id_var.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to extract or generate correlation ID for each request.

    The correlation ID is:
    1. Extracted from X-Correlation-ID header if present
    2. Generated as a new UUID if not present
    3. Set in the context for use throughout the request
    4. Added to the response headers
    """

    HEADER_NAME = "X-Correlation-ID"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Extract or generate correlation ID
        correlation_id_header = request.headers.get(self.HEADER_NAME)

        if correlation_id_header:
            try:
                correlation_id = uuid.UUID(correlation_id_header)
            except ValueError:
                # Invalid UUID format, generate new one
                correlation_id = uuid.uuid4()
        else:
            correlation_id = uuid.uuid4()

        # Set in context
        token = correlation_id_var.set(correlation_id)

        try:
            # Store in request state for easy access
            request.state.correlation_id = correlation_id

            # Process request
            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers[self.HEADER_NAME] = str(correlation_id)

            return response
        finally:
            # Reset context
            correlation_id_var.reset(token)


def get_request_correlation_id(request: Request) -> uuid.UUID:
    """Get correlation ID from request state.

    Falls back to context variable or generates new one.
    """
    if hasattr(request, "state") and hasattr(request.state, "correlation_id"):
        return request.state.correlation_id
    return get_correlation_id()
