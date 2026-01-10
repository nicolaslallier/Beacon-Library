"""MCP tool implementations for Beacon Library."""

import uuid
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.directory import Directory
from app.models.file import FileMetadata
from app.models.library import Library

logger = structlog.get_logger(__name__)


def register_tools(server: "MCPServer"):
    """Register all MCP tools with the server."""

    @server.register_tool
    async def list_libraries(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List all available libraries."""
        async with server.db_session_factory() as db:
            query = select(Library).where(Library.is_deleted == False)
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

    @server.register_tool
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
                and_(Library.id == library_id, Library.is_deleted == False)
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
                        Directory.is_deleted == False,
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
                        Directory.is_deleted == False,
                    )
                )
            else:
                dirs_query = select(Directory).where(
                    and_(
                        Directory.library_id == library_id,
                        Directory.parent_id == None,
                        Directory.is_deleted == False,
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
                        FileMetadata.is_deleted == False,
                    )
                )
            else:
                files_query = select(FileMetadata).where(
                    and_(
                        FileMetadata.library_id == library_id,
                        FileMetadata.directory_id == None,
                        FileMetadata.is_deleted == False,
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
                        "name": f.name,
                        "mime_type": f.mime_type,
                        "size": f.size,
                        "updated_at": f.updated_at.isoformat(),
                    }
                    for f in files
                ],
            }

    @server.register_tool
    async def read_file(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Read the contents of a file."""
        file_id = uuid.UUID(arguments["file_id"])

        async with server.db_session_factory() as db:
            # Get file metadata
            query = select(FileMetadata).where(
                and_(FileMetadata.id == file_id, FileMetadata.is_deleted == False)
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
            is_text = any(file.mime_type.startswith(t) for t in text_types)

            if not is_text:
                return {
                    "id": str(file.id),
                    "name": file.name,
                    "mime_type": file.mime_type,
                    "size": file.size,
                    "error": "File is binary, cannot read as text",
                }

            # Read file content from storage
            try:
                content = await server.storage_service.get_file_content(
                    bucket_name=f"beacon-lib-{file.library_id}",
                    object_name=file.storage_key,
                )

                return {
                    "id": str(file.id),
                    "name": file.name,
                    "mime_type": file.mime_type,
                    "size": file.size,
                    "content": content.decode("utf-8"),
                }
            except Exception as e:
                logger.error("mcp_read_file_error", file_id=str(file_id), error=str(e))
                return {"error": f"Failed to read file: {str(e)}"}

    @server.register_tool
    async def search_files(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Search for files by name."""
        query_str = arguments["query"]
        library_id = arguments.get("library_id")

        async with server.db_session_factory() as db:
            conditions = [
                FileMetadata.is_deleted == False,
                FileMetadata.name.ilike(f"%{query_str}%"),
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
                        "name": f.name,
                        "library_id": str(f.library_id),
                        "path": f.path,
                        "mime_type": f.mime_type,
                        "size": f.size,
                    }
                    for f in files
                ],
                "count": len(files),
            }

    @server.register_tool
    async def create_file(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new file in a library."""
        library_id = uuid.UUID(arguments["library_id"])
        path = arguments["path"]
        content = arguments["content"]

        # Check policy
        policy = server.get_library_policy(library_id)
        if not policy.can_write("mcp"):
            return {"error": "Write access denied for this library"}

        async with server.db_session_factory() as db:
            # Get library
            lib_query = select(Library).where(
                and_(Library.id == library_id, Library.is_deleted == False)
            )
            lib_result = await db.execute(lib_query)
            library = lib_result.scalar_one_or_none()

            if not library:
                return {"error": "Library not found"}

            if not library.mcp_write_enabled:
                return {"error": "MCP write access is disabled for this library"}

            # Parse path to get directory and filename
            path_parts = path.strip("/").split("/")
            filename = path_parts[-1]
            dir_path = "/" + "/".join(path_parts[:-1]) if len(path_parts) > 1 else "/"

            # Find or create parent directory
            parent_id = None
            if dir_path != "/":
                dir_query = select(Directory).where(
                    and_(
                        Directory.library_id == library_id,
                        Directory.path == dir_path,
                        Directory.is_deleted == False,
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
                    FileMetadata.name == filename,
                    FileMetadata.is_deleted == False,
                )
            )
            existing_result = await db.execute(existing_query)
            if existing_result.scalar_one_or_none():
                return {"error": f"File already exists: {path}"}

            # Upload content to storage
            content_bytes = content.encode("utf-8")
            storage_key = f"{uuid.uuid4()}/{filename}"

            try:
                await server.storage_service.upload_file(
                    bucket_name=f"beacon-lib-{library_id}",
                    object_name=storage_key,
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
                name=filename,
                path=path,
                storage_key=storage_key,
                mime_type="text/plain",
                size=len(content_bytes),
            )

            db.add(file)
            await db.commit()
            await db.refresh(file)

            logger.info(
                "mcp_file_created",
                file_id=str(file.id),
                library_id=str(library_id),
                path=path,
            )

            return {
                "success": True,
                "file": {
                    "id": str(file.id),
                    "name": file.name,
                    "path": file.path,
                    "size": file.size,
                },
            }

    @server.register_tool
    async def update_file(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing file."""
        file_id = uuid.UUID(arguments["file_id"])
        content = arguments["content"]

        async with server.db_session_factory() as db:
            # Get file
            query = select(FileMetadata).where(
                and_(FileMetadata.id == file_id, FileMetadata.is_deleted == False)
            )
            result = await db.execute(query)
            file = result.scalar_one_or_none()

            if not file:
                return {"error": "File not found"}

            # Check policy
            policy = server.get_library_policy(file.library_id)
            if not policy.can_write("mcp"):
                return {"error": "Write access denied for this library"}

            # Get library to check MCP write enabled
            lib_query = select(Library).where(Library.id == file.library_id)
            lib_result = await db.execute(lib_query)
            library = lib_result.scalar_one_or_none()

            if not library or not library.mcp_write_enabled:
                return {"error": "MCP write access is disabled for this library"}

            # Upload new content
            content_bytes = content.encode("utf-8")

            try:
                await server.storage_service.upload_file(
                    bucket_name=f"beacon-lib-{file.library_id}",
                    object_name=file.storage_key,
                    data=content_bytes,
                    content_type=file.mime_type,
                )
            except Exception as e:
                logger.error("mcp_update_error", error=str(e))
                return {"error": f"Failed to update file: {str(e)}"}

            # Update metadata
            file.size = len(content_bytes)
            file.version += 1

            await db.commit()

            logger.info(
                "mcp_file_updated",
                file_id=str(file.id),
                version=file.version,
            )

            return {
                "success": True,
                "file": {
                    "id": str(file.id),
                    "name": file.name,
                    "version": file.version,
                    "size": file.size,
                },
            }
