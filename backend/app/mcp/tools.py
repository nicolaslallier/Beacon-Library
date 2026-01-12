"""MCP tool implementations for Beacon Library."""

import hashlib
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.directory import Directory
from app.models.file import FileMetadata, FileVersion
from app.models.library import Library

if TYPE_CHECKING:
    from app.mcp.server import MCPServer

logger = structlog.get_logger(__name__)

# Synthetic user id used for agent-initiated writes when no auth context is available.
# (MCP writes are typically disabled by default anyway.)
AGENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def register_tools(server: "MCPServer"):
    """Register all MCP tools with the server."""

    def _mcp_write_denied_error(library_id: uuid.UUID) -> Dict[str, Any]:
        """
        Return a helpful error when MCP write is denied.

        There are two independent gates:
        - Server policy gate (default controlled by MCP_DEFAULT_WRITE_ENABLED, or
          overridden via /api/mcp/libraries/{id}/policy)
        - Per-library DB flag (Library.mcp_write_enabled)
        """
        # If no explicit policy was set for this library and the default is read-only,
        # return an actionable message.
        has_explicit_policy = (
            getattr(server, "_library_policies", {}).get(library_id) is not None
        )
        if not has_explicit_policy and not settings.mcp_default_write_enabled:
            return {
                "error": (
                    "MCP write is disabled by server configuration "
                    "(MCP_DEFAULT_WRITE_ENABLED=false). "
                    f"Enable it globally (set MCP_DEFAULT_WRITE_ENABLED=true) "
                    f"or enable per-library policy via "
                    f"PUT /api/mcp/libraries/{library_id}/policy?write_enabled=true"
                )
            }

        return {
            "error": (
                "Write access denied by MCP policy for this library. "
                f"Enable per-library policy via "
                f"PUT /api/mcp/libraries/{library_id}/policy?write_enabled=true"
            )
        }

    async def _get_bucket_name(db: AsyncSession, library_id: uuid.UUID) -> str:
        result = await db.execute(select(Library).where(Library.id == library_id))
        lib = result.scalar_one_or_none()
        if not lib:
            raise ValueError("Library not found")
        return lib.bucket_name

    async def list_libraries(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List all available libraries."""
        async with server.db_session_factory() as db:
            query = select(Library).where(Library.is_deleted.is_(False))
            result = await db.execute(query)
            libraries = result.scalars().all()

            return {
                "libraries": [
                    {
                        "id": str(lib.id),
                        "name": lib.name,
                        "description": lib.description,
                        "mcp_write_enabled": lib.mcp_write_enabled,
                        "created_at": lib.created_at.isoformat(),
                    }
                    for lib in libraries
                ],
                "count": len(libraries),
            }

    async def browse_library(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Browse contents of a library or directory."""
        library_id = uuid.UUID(arguments["library_id"])
        path = arguments.get("path", "/")

        # Check policy
        policy = server.get_library_policy(library_id)
        if not policy.can_read("mcp"):  # TODO: Get actual agent ID
            return {"error": "Read access denied for this library"}

        async with server.db_session_factory() as db:
            # Get library
            lib_query = select(Library).where(
                and_(Library.id == library_id, Library.is_deleted.is_(False))
            )
            lib_result = await db.execute(lib_query)
            library = lib_result.scalar_one_or_none()

            if not library:
                return {"error": "Library not found"}

            # Find parent directory if path is not root
            parent_id = None
            if path != "/":
                dir_query = select(Directory).where(
                    and_(
                        Directory.library_id == library_id,
                        Directory.path == path,
                        Directory.is_deleted.is_(False),
                    )
                )
                dir_result = await db.execute(dir_query)
                parent_dir = dir_result.scalar_one_or_none()
                if parent_dir:
                    parent_id = parent_dir.id

            # Get directories
            if parent_id:
                dirs_query = select(Directory).where(
                    and_(
                        Directory.library_id == library_id,
                        Directory.parent_id == parent_id,
                        Directory.is_deleted.is_(False),
                    )
                )
            else:
                dirs_query = select(Directory).where(
                    and_(
                        Directory.library_id == library_id,
                        Directory.parent_id.is_(None),
                        Directory.is_deleted.is_(False),
                    )
                )

            dirs_result = await db.execute(dirs_query)
            directories = dirs_result.scalars().all()

            # Get files
            if parent_id:
                files_query = select(FileMetadata).where(
                    and_(
                        FileMetadata.library_id == library_id,
                        FileMetadata.directory_id == parent_id,
                        FileMetadata.is_deleted.is_(False),
                    )
                )
            else:
                files_query = select(FileMetadata).where(
                    and_(
                        FileMetadata.library_id == library_id,
                        FileMetadata.directory_id.is_(None),
                        FileMetadata.is_deleted.is_(False),
                    )
                )

            files_result = await db.execute(files_query)
            files = files_result.scalars().all()

            return {
                "library": {
                    "id": str(library.id),
                    "name": library.name,
                },
                "path": path,
                "directories": [
                    {
                        "id": str(d.id),
                        "name": d.name,
                        "path": d.path,
                    }
                    for d in directories
                ],
                "files": [
                    {
                        "id": str(f.id),
                        "name": f.filename,
                        "mime_type": f.content_type,
                        "size": f.size_bytes,
                        "path": f.full_path,
                        "updated_at": f.updated_at.isoformat(),
                    }
                    for f in files
                ],
            }

    async def read_file(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Read the contents of a file."""
        file_id = uuid.UUID(arguments["file_id"])

        async with server.db_session_factory() as db:
            # Get file metadata
            query = select(FileMetadata).where(
                and_(FileMetadata.id == file_id, FileMetadata.is_deleted.is_(False))
            )
            result = await db.execute(query)
            file = result.scalar_one_or_none()

            if not file:
                return {"error": "File not found"}

            # Check policy
            policy = server.get_library_policy(file.library_id)
            if not policy.can_read("mcp"):
                return {"error": "Read access denied for this library"}

            # Check if file is text-based
            text_types = [
                "text/",
                "application/json",
                "application/xml",
                "application/javascript",
                "application/typescript",
            ]
            is_text = any(file.content_type.startswith(t) for t in text_types)

            if not is_text:
                return {
                    "id": str(file.id),
                    "name": file.filename,
                    "mime_type": file.content_type,
                    "size": file.size_bytes,
                    "path": file.full_path,
                    "error": "File is binary, cannot read as text",
                }

            # Read file content from storage
            try:
                bucket_name = await _get_bucket_name(db, file.library_id)
                content = await server.storage_service.download_file(
                    bucket=bucket_name,
                    key=file.storage_key,
                )

                return {
                    "id": str(file.id),
                    "name": file.filename,
                    "mime_type": file.content_type,
                    "size": file.size_bytes,
                    "path": file.full_path,
                    "content": content.decode("utf-8", errors="replace"),
                }
            except Exception as e:
                logger.error("mcp_read_file_error", file_id=str(file_id), error=str(e))
                return {"error": f"Failed to read file: {str(e)}"}

    async def search_files(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Search for files by name."""
        query_str = arguments.get("query", "")
        library_id = arguments.get("library_id")

        async with server.db_session_factory() as db:
            conditions = [
                FileMetadata.is_deleted.is_(False),
                FileMetadata.filename.ilike(f"%{query_str}%"),
            ]

            if library_id:
                lib_id = uuid.UUID(library_id)
                policy = server.get_library_policy(lib_id)
                if not policy.can_read("mcp"):
                    return {"error": "Read access denied for this library"}
                conditions.append(FileMetadata.library_id == lib_id)

            query = select(FileMetadata).where(and_(*conditions)).limit(50)
            result = await db.execute(query)
            files = result.scalars().all()

            return {
                "query": query_str,
                "results": [
                    {
                        "id": str(f.id),
                        "name": f.filename,
                        "library_id": str(f.library_id),
                        "path": f.full_path,
                        "mime_type": f.content_type,
                        "size": f.size_bytes,
                    }
                    for f in files
                ],
                "count": len(files),
            }

    async def create_file(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new file in a library."""
        library_id = uuid.UUID(arguments["library_id"])
        full_path = arguments["path"]
        content = arguments["content"]

        async with server.db_session_factory() as db:
            # Get library
            lib_query = select(Library).where(
                and_(Library.id == library_id, Library.is_deleted.is_(False))
            )
            lib_result = await db.execute(lib_query)
            library = lib_result.scalar_one_or_none()

            if not library:
                return {"error": "Library not found"}

            if not library.mcp_write_enabled:
                return {"error": "MCP write access is disabled for this library"}

            # Check policy (after confirming the library itself allows MCP writes)
            policy = server.get_library_policy(library_id)
            if not policy.can_write("mcp"):  # TODO: Get actual agent ID from transport/session
                return _mcp_write_denied_error(library_id)

            # Parse full path to get directory and filename
            normalized = full_path if full_path.startswith("/") else f"/{full_path}"
            path_parts = normalized.strip("/").split("/")
            filename = path_parts[-1]
            dir_path = "/" + "/".join(path_parts[:-1]) if len(path_parts) > 1 else "/"

            # Find or create parent directory
            parent_id = None
            if dir_path != "/":
                dir_query = select(Directory).where(
                    and_(
                        Directory.library_id == library_id,
                        Directory.path == dir_path,
                        Directory.is_deleted.is_(False),
                    )
                )
                dir_result = await db.execute(dir_query)
                parent_dir = dir_result.scalar_one_or_none()

                if parent_dir:
                    parent_id = parent_dir.id
                else:
                    return {"error": f"Directory not found: {dir_path}"}

            # Check if file already exists
            existing_query = select(FileMetadata).where(
                and_(
                    FileMetadata.library_id == library_id,
                    FileMetadata.directory_id == parent_id,
                    FileMetadata.filename == filename,
                    FileMetadata.is_deleted.is_(False),
                )
            )
            existing_result = await db.execute(existing_query)
            if existing_result.scalar_one_or_none():
                return {"error": f"File already exists: {normalized}"}

            # Upload content to storage
            content_bytes = content.encode("utf-8")
            checksum = hashlib.sha256(content_bytes).hexdigest()
            storage_key = f"{uuid.uuid4()}/{filename}"

            try:
                await server.storage_service.upload_file(
                    bucket=library.bucket_name,
                    key=storage_key,
                    data=content_bytes,
                    content_type="text/plain",
                )
            except Exception as e:
                logger.error("mcp_upload_error", error=str(e))
                return {"error": f"Failed to upload file: {str(e)}"}

            # Create file metadata
            file = FileMetadata(
                library_id=library_id,
                directory_id=parent_id,
                filename=filename,
                path=dir_path,
                storage_key=storage_key,
                content_type="text/plain",
                size_bytes=len(content_bytes),
                checksum_sha256=checksum,
                created_by=AGENT_USER_ID,
                modified_by=AGENT_USER_ID,
            )

            db.add(file)
            # Flush to get the file.id assigned by the database
            await db.flush()

            # Create initial version
            version = FileVersion(
                file_id=file.id,
                version_number=1,
                size_bytes=len(content_bytes),
                checksum_sha256=checksum,
                storage_key=storage_key,
                created_at=datetime.utcnow(),
                created_by=AGENT_USER_ID,
            )
            db.add(version)
            await db.commit()
            await db.refresh(file)

            logger.info(
                "mcp_file_created",
                file_id=str(file.id),
                library_id=str(library_id),
                path=normalized,
            )

            return {
                "success": True,
                "file": {
                    "id": str(file.id),
                    "name": file.filename,
                    "path": file.full_path,
                    "size": file.size_bytes,
                },
            }

    async def update_file(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing file."""
        file_id = uuid.UUID(arguments["file_id"])
        content = arguments["content"]

        async with server.db_session_factory() as db:
            # Get file
            query = select(FileMetadata).where(
                and_(FileMetadata.id == file_id, FileMetadata.is_deleted.is_(False))
            )
            result = await db.execute(query)
            file = result.scalar_one_or_none()

            if not file:
                return {"error": "File not found"}

            # Get library to check MCP write enabled
            lib_query = select(Library).where(Library.id == file.library_id)
            lib_result = await db.execute(lib_query)
            library = lib_result.scalar_one_or_none()

            if not library or not library.mcp_write_enabled:
                return {"error": "MCP write access is disabled for this library"}

            # Check policy (after confirming the library itself allows MCP writes)
            policy = server.get_library_policy(file.library_id)
            if not policy.can_write("mcp"):  # TODO: Get actual agent ID from transport/session
                return _mcp_write_denied_error(file.library_id)

            # Upload new content
            content_bytes = content.encode("utf-8")
            checksum = hashlib.sha256(content_bytes).hexdigest()

            try:
                await server.storage_service.upload_file(
                    bucket=library.bucket_name,
                    key=file.storage_key,
                    data=content_bytes,
                    content_type=file.content_type,
                )
            except Exception as e:
                logger.error("mcp_update_error", error=str(e))
                return {"error": f"Failed to update file: {str(e)}"}

            # Update metadata
            new_version = file.current_version + 1
            file.size_bytes = len(content_bytes)
            file.checksum_sha256 = checksum
            file.current_version = new_version
            file.modified_by = AGENT_USER_ID

            version = FileVersion(
                file_id=file.id,
                version_number=new_version,
                size_bytes=len(content_bytes),
                checksum_sha256=checksum,
                storage_key=file.storage_key,
                created_at=datetime.utcnow(),
                created_by=AGENT_USER_ID,
            )
            db.add(version)

            await db.commit()

            logger.info(
                "mcp_file_updated",
                file_id=str(file.id),
                version=file.current_version,
            )

            return {
                "success": True,
                "file": {
                    "id": str(file.id),
                    "name": file.filename,
                    "version": file.current_version,
                    "size": file.size_bytes,
                },
            }

    # Register all tools with the server
    server.register_tool("list_libraries", list_libraries)
    server.register_tool("browse_library", browse_library)
    server.register_tool("read_file", read_file)
    server.register_tool("search_files", search_files)
    server.register_tool("create_file", create_file)
    server.register_tool("update_file", update_file)
