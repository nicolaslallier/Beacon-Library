"""Content extraction service for text extraction from various file formats."""

import io
from typing import Optional

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


# MIME types that can have text extracted
EXTRACTABLE_TYPES = {
    # Text-based files
    "text/plain",
    "text/html",
    "text/markdown",
    "text/csv",
    "text/xml",
    "application/json",
    "application/xml",
    "application/x-yaml",
    "application/yaml",
    "text/yaml",
    "text/x-yaml",
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument"
    ".presentationml.presentation",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    # Code files
    "text/javascript",
    "text/css",
    "application/javascript",
    "text/x-python",
    "text/x-java-source",
    "text/x-c",
    "text/x-c++",
    "text/x-sh",
    "application/x-sh",
}

# File extensions that should be treated as text (for application/octet-stream fallback)
TEXT_EXTENSIONS = {
    # Config files
    ".yml", ".yaml", ".json", ".xml", ".toml", ".ini", ".cfg", ".conf",
    ".env", ".properties", ".cnf",
    # Code files
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".r", ".m",
    ".cs", ".vb", ".fs", ".lua", ".pl", ".pm", ".sh", ".bash", ".zsh",
    ".fish", ".ps1", ".psm1", ".bat", ".cmd",
    # Web files
    ".html", ".htm", ".css", ".scss", ".sass", ".less", ".vue", ".svelte",
    # Data files
    ".csv", ".tsv", ".sql", ".graphql", ".gql",
    # Documentation
    ".md", ".markdown", ".rst", ".txt", ".adoc", ".asciidoc",
    # Build/DevOps files
    ".dockerfile", ".containerfile", ".tf", ".tfvars", ".hcl",
    ".gradle", ".sbt", ".cmake", ".makefile",
    # Other config
    ".gitignore", ".gitattributes", ".editorconfig", ".eslintrc",
    ".prettierrc", ".babelrc", ".nvmrc", ".npmrc", ".yarnrc",
}

# Filenames that should be treated as text (without extensions)
TEXT_FILENAMES = {
    "Makefile", "Dockerfile", "Containerfile", "Jenkinsfile", "Vagrantfile",
    "Gemfile", "Rakefile", "Procfile", "Brewfile",
    ".gitignore", ".gitattributes", ".dockerignore", ".editorconfig",
    ".cursorrules", ".cursorignore", ".env", ".envrc",
    "requirements.txt", "Pipfile", "setup.py", "pyproject.toml",
    "package.json", "tsconfig.json", "webpack.config.js",
    "docker-compose.yml", "docker-compose.yaml",
    "LICENSE", "README", "CHANGELOG", "AUTHORS", "CONTRIBUTING",
    "CODEOWNERS", "SECURITY", "NOTICE",
}


class ContentExtractionService:
    """Service for extracting text content from files for indexing."""

    def __init__(self, gotenberg_url: str = None):
        self.gotenberg_url = gotenberg_url or settings.gotenberg_url
        self.max_content_length = 50000  # Max characters to extract

    def can_extract(self, mime_type: str, file_name: str = None) -> bool:
        """Check if text can be extracted from this file type.
        
        Args:
            mime_type: The MIME type of the file
            file_name: Optional filename for extension-based detection
        """
        # Check exact MIME type match
        if mime_type in EXTRACTABLE_TYPES:
            return True
        # Check text/* and code files
        if mime_type.startswith("text/"):
            return True
        
        # For application/octet-stream or unknown types, check by filename
        if file_name and mime_type in {"application/octet-stream", ""}:
            return self._is_text_by_filename(file_name)
        
        return False
    
    def _is_text_by_filename(self, file_name: str) -> bool:
        """Check if a file should be treated as text based on its name."""
        # Check exact filename match
        if file_name in TEXT_FILENAMES:
            return True
        
        # Check file extension
        lower_name = file_name.lower()
        for ext in TEXT_EXTENSIONS:
            if lower_name.endswith(ext):
                return True
        
        # Check if filename matches known text file patterns
        base_name = file_name.rsplit("/", 1)[-1]  # Get just the filename
        if base_name in TEXT_FILENAMES:
            return True
        
        return False

    async def extract_text(
        self,
        file_content: bytes,
        file_name: str,
        mime_type: str,
    ) -> Optional[str]:
        """Extract text content from a file.

        Returns:
            Extracted text content, or None if extraction fails
        """
        if not self.can_extract(mime_type, file_name):
            logger.debug("content_not_extractable", mime_type=mime_type, file_name=file_name)
            return None

        try:
            # Text-based files - decode directly
            # Check MIME type OR filename for text detection
            is_text_mime = (
                mime_type.startswith("text/") or 
                mime_type in {
                    "application/json",
                    "application/xml",
                    "application/javascript",
                    "application/x-yaml",
                    "application/yaml",
                }
            )
            is_text_by_name = (
                mime_type == "application/octet-stream" and 
                self._is_text_by_filename(file_name)
            )
            
            if is_text_mime or is_text_by_name:
                return self._extract_text_file(file_content)

            # PDF files
            if mime_type == "application/pdf":
                return await self._extract_pdf(file_content, file_name)

            # Office documents - use Gotenberg to convert to text
            if "word" in mime_type or "document" in mime_type:
                return await self._extract_office_document(
                    file_content, file_name, mime_type
                )

            if "excel" in mime_type or "spreadsheet" in mime_type:
                return await self._extract_office_document(
                    file_content, file_name, mime_type
                )

            if "powerpoint" in mime_type or "presentation" in mime_type:
                return await self._extract_office_document(
                    file_content, file_name, mime_type
                )

            if "opendocument" in mime_type:
                return await self._extract_office_document(
                    file_content, file_name, mime_type
                )

            return None

        except Exception as e:
            logger.error(
                "content_extraction_error",
                file_name=file_name,
                mime_type=mime_type,
                error=str(e),
            )
            return None

    def _extract_text_file(self, file_content: bytes) -> str:
        """Extract text from a text-based file."""
        # Try UTF-8 first, then fall back to other encodings
        for encoding in ["utf-8", "latin-1", "cp1252"]:
            try:
                text = file_content.decode(encoding)
                return self._truncate_text(text)
            except UnicodeDecodeError:
                continue

        # If all decodings fail, decode with errors replaced
        text = file_content.decode("utf-8", errors="replace")
        return self._truncate_text(text)

    async def _extract_pdf(
        self, file_content: bytes, file_name: str
    ) -> Optional[str]:
        """Extract text from a PDF file using PyPDF2 or Gotenberg."""
        # Try using PyPDF2 for basic text extraction
        try:
            import PyPDF2

            reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text_parts = []

            for page in reader.pages[:50]:  # Limit to first 50 pages
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            if text_parts:
                full_text = "\n\n".join(text_parts)
                return self._truncate_text(full_text)

        except ImportError:
            logger.debug("pypdf2_not_installed")
        except Exception as e:
            logger.warning("pdf_extraction_error", error=str(e))

        # Fallback: Use Gotenberg to convert to text
        return await self._extract_via_gotenberg(
            file_content, file_name, "application/pdf"
        )

    async def _extract_office_document(
        self,
        file_content: bytes,
        file_name: str,
        mime_type: str,
    ) -> Optional[str]:
        """Extract text from Office documents using Gotenberg conversion."""
        return await self._extract_via_gotenberg(
            file_content, file_name, mime_type
        )

    async def _extract_via_gotenberg(
        self,
        file_content: bytes,
        file_name: str,
        mime_type: str,
    ) -> Optional[str]:
        """Extract text by converting document via Gotenberg."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Convert to HTML first (preserves text better)
                files = {
                    "files": (file_name, io.BytesIO(file_content), mime_type),
                }

                # Try LibreOffice route for office docs
                endpoint = f"{self.gotenberg_url}/forms/libreoffice/convert"

                response = await client.post(
                    endpoint,
                    files=files,
                    data={"pdfFormat": "PDF/A-1a"},  # PDF format for better text
                )
                response.raise_for_status()

                # Now extract text from the PDF result
                pdf_content = response.content
                return await self._extract_pdf(pdf_content, "converted.pdf")

            except Exception as e:
                logger.warning(
                    "gotenberg_extraction_error",
                    file_name=file_name,
                    error=str(e),
                )
                return None

    def _truncate_text(self, text: str) -> str:
        """Truncate text to maximum length while preserving word boundaries."""
        if len(text) <= self.max_content_length:
            return text.strip()

        # Find the last space before the limit
        truncated = text[: self.max_content_length]
        last_space = truncated.rfind(" ")

        if last_space > self.max_content_length * 0.8:
            return truncated[:last_space].strip()

        return truncated.strip()

    def create_searchable_content(
        self,
        file_name: str,
        file_path: str,
        extracted_text: Optional[str],
        mime_type: str,
    ) -> str:
        """Create a searchable content string combining metadata and content.

        This combines file metadata with extracted text for better search results.
        """
        parts = []

        # Add filename (important for search)
        parts.append(f"File: {file_name}")

        # Add path info
        if file_path and file_path != "/":
            parts.append(f"Path: {file_path}")

        # Add file type description
        type_desc = self._get_type_description(mime_type)
        if type_desc:
            parts.append(f"Type: {type_desc}")

        # Add extracted content
        if extracted_text:
            parts.append("")  # Empty line separator
            parts.append(extracted_text)

        return "\n".join(parts)

    def _get_type_description(self, mime_type: str) -> str:
        """Get a human-readable description of the file type."""
        # Long MIME types
        word_docx = (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )
        excel_xlsx = (
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        )
        pptx = (
            "application/vnd.openxmlformats-officedocument"
            ".presentationml.presentation"
        )
        
        type_map = {
            "application/pdf": "PDF Document",
            "application/msword": "Word Document",
            word_docx: "Word Document",
            "application/vnd.ms-excel": "Excel Spreadsheet",
            excel_xlsx: "Excel Spreadsheet",
            "application/vnd.ms-powerpoint": "PowerPoint Presentation",
            pptx: "PowerPoint Presentation",
            "text/plain": "Text File",
            "text/html": "HTML Document",
            "text/markdown": "Markdown Document",
            "text/csv": "CSV Data",
            "image/jpeg": "JPEG Image",
            "image/png": "PNG Image",
            "image/gif": "GIF Image",
        }

        if mime_type in type_map:
            return type_map[mime_type]

        if mime_type.startswith("image/"):
            return "Image"
        if mime_type.startswith("video/"):
            return "Video"
        if mime_type.startswith("audio/"):
            return "Audio"
        if mime_type.startswith("text/"):
            return "Text Document"

        return "File"


# Global instance
content_extraction_service = ContentExtractionService()
