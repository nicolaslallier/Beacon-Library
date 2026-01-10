"""File preview service using Gotenberg for document conversion."""

import io
import uuid
from typing import Optional, Tuple

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


# Supported file types for preview
PREVIEWABLE_TYPES = {
    # Documents
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.oasis.opendocument.presentation": "odp",
    # Text
    "text/plain": "txt",
    "text/html": "html",
    "text/markdown": "md",
    "text/csv": "csv",
    # Images (passthrough)
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}

# Types that need conversion to PDF
CONVERT_TO_PDF_TYPES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
}

# Types that can be rendered directly
DIRECT_RENDER_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "text/plain",
    "text/html",
    "text/markdown",
    "text/csv",
}


class PreviewService:
    """Service for generating file previews."""

    def __init__(
        self,
        gotenberg_url: str = None,
        max_file_size: int = None,
    ):
        self.gotenberg_url = gotenberg_url or settings.gotenberg_url
        self.max_file_size = max_file_size or settings.preview_max_file_size

    def can_preview(self, mime_type: str) -> bool:
        """Check if a file type can be previewed."""
        return mime_type in PREVIEWABLE_TYPES

    def needs_conversion(self, mime_type: str) -> bool:
        """Check if a file needs conversion to PDF for preview."""
        return mime_type in CONVERT_TO_PDF_TYPES

    async def generate_preview(
        self,
        file_content: bytes,
        file_name: str,
        mime_type: str,
    ) -> Tuple[bytes, str]:
        """Generate a preview for a file.

        Returns:
            Tuple of (preview_content, preview_mime_type)
        """
        if not self.can_preview(mime_type):
            raise ValueError(f"Cannot preview file type: {mime_type}")

        if len(file_content) > self.max_file_size:
            raise ValueError(
                f"File too large for preview: {len(file_content)} bytes "
                f"(max: {self.max_file_size})"
            )

        if self.needs_conversion(mime_type):
            # Convert to PDF using Gotenberg
            return await self._convert_to_pdf(file_content, file_name, mime_type)

        # Return as-is for direct render types
        return file_content, mime_type

    async def generate_thumbnail(
        self,
        file_content: bytes,
        file_name: str,
        mime_type: str,
        width: int = 200,
        height: int = 200,
    ) -> Tuple[bytes, str]:
        """Generate a thumbnail image for a file.

        Returns:
            Tuple of (thumbnail_content, thumbnail_mime_type)
        """
        # For images, resize directly
        if mime_type.startswith("image/"):
            return await self._resize_image(file_content, width, height)

        # For documents, first convert to PDF, then to image
        if self.needs_conversion(mime_type):
            pdf_content, _ = await self._convert_to_pdf(file_content, file_name, mime_type)
            return await self._pdf_to_image(pdf_content, width, height)

        if mime_type == "application/pdf":
            return await self._pdf_to_image(file_content, width, height)

        # For text files, generate a text preview image
        if mime_type.startswith("text/"):
            return await self._text_to_image(file_content.decode("utf-8"), width, height)

        raise ValueError(f"Cannot generate thumbnail for: {mime_type}")

    async def _convert_to_pdf(
        self,
        file_content: bytes,
        file_name: str,
        mime_type: str,
    ) -> Tuple[bytes, str]:
        """Convert a document to PDF using Gotenberg."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Use LibreOffice route for office documents
                files = {
                    "files": (file_name, io.BytesIO(file_content), mime_type),
                }

                response = await client.post(
                    f"{self.gotenberg_url}/forms/libreoffice/convert",
                    files=files,
                )
                response.raise_for_status()

                return response.content, "application/pdf"

            except httpx.HTTPStatusError as e:
                logger.error(
                    "gotenberg_conversion_error",
                    status_code=e.response.status_code,
                    file_name=file_name,
                )
                raise ValueError(f"Document conversion failed: {e.response.status_code}")
            except Exception as e:
                logger.error(
                    "gotenberg_error",
                    error=str(e),
                    file_name=file_name,
                )
                raise ValueError(f"Document conversion failed: {str(e)}")

    async def _pdf_to_image(
        self,
        pdf_content: bytes,
        width: int,
        height: int,
    ) -> Tuple[bytes, str]:
        """Convert the first page of a PDF to an image using Gotenberg."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                files = {
                    "files": ("document.pdf", io.BytesIO(pdf_content), "application/pdf"),
                }

                data = {
                    "format": "png",
                    "quality": 80,
                    "width": width,
                    "height": height,
                }

                response = await client.post(
                    f"{self.gotenberg_url}/forms/chromium/screenshot",
                    files=files,
                    data=data,
                )
                response.raise_for_status()

                return response.content, "image/png"

            except Exception as e:
                logger.error("pdf_to_image_error", error=str(e))
                raise ValueError(f"PDF to image conversion failed: {str(e)}")

    async def _resize_image(
        self,
        image_content: bytes,
        width: int,
        height: int,
    ) -> Tuple[bytes, str]:
        """Resize an image.

        Note: For production, use PIL/Pillow for local processing.
        This is a placeholder that returns the original image.
        """
        # TODO: Implement actual image resizing with Pillow
        # For now, return original image
        return image_content, "image/png"

    async def _text_to_image(
        self,
        text: str,
        width: int,
        height: int,
    ) -> Tuple[bytes, str]:
        """Generate an image preview of text content.

        Note: For production, use PIL/Pillow for local processing.
        This is a placeholder.
        """
        # TODO: Implement text-to-image with Pillow
        # For now, convert to HTML and use Gotenberg
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: monospace;
                    font-size: 10px;
                    padding: 10px;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}
            </style>
        </head>
        <body>{text[:1000]}</body>
        </html>
        """

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                files = {
                    "files": ("preview.html", io.BytesIO(html_content.encode()), "text/html"),
                }

                data = {
                    "format": "png",
                    "width": width,
                    "height": height,
                }

                response = await client.post(
                    f"{self.gotenberg_url}/forms/chromium/screenshot",
                    files=files,
                    data=data,
                )
                response.raise_for_status()

                return response.content, "image/png"

            except Exception as e:
                logger.error("text_to_image_error", error=str(e))
                raise ValueError(f"Text preview generation failed: {str(e)}")


class PreviewCacheService:
    """Cache for file previews."""

    def __init__(self, cache_service):
        self.cache = cache_service
        self.ttl = 3600 * 24  # 24 hours

    async def get_preview(
        self,
        file_id: uuid.UUID,
        preview_type: str = "full",
    ) -> Optional[Tuple[bytes, str]]:
        """Get a cached preview."""
        key = f"preview:{file_id}:{preview_type}"
        data = await self.cache.get(key)
        if data:
            # Parse cached data (mime_type:base64_content)
            mime_type, content_b64 = data.split(":", 1)
            import base64
            return base64.b64decode(content_b64), mime_type
        return None

    async def set_preview(
        self,
        file_id: uuid.UUID,
        content: bytes,
        mime_type: str,
        preview_type: str = "full",
    ) -> None:
        """Cache a preview."""
        import base64
        key = f"preview:{file_id}:{preview_type}"
        data = f"{mime_type}:{base64.b64encode(content).decode()}"
        await self.cache.set(key, data, ttl=self.ttl)

    async def invalidate_preview(self, file_id: uuid.UUID) -> None:
        """Invalidate all cached previews for a file."""
        for preview_type in ["full", "thumbnail"]:
            key = f"preview:{file_id}:{preview_type}"
            await self.cache.delete(key)
