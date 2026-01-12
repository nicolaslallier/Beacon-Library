#!/usr/bin/env python3
"""Reindex library files with the new smart chunking strategy.

This script re-indexes all files in a library (or all libraries) using
the enhanced chunking and metadata extraction features.

Usage:
    # Reindex a specific library
    python -m scripts.reindex_library --library-id <uuid>

    # Reindex all libraries
    python -m scripts.reindex_library --all

    # Reindex only Python files
    python -m scripts.reindex_library --all --language python

    # Dry run (show what would be indexed)
    python -m scripts.reindex_library --all --dry-run
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.file import FileMetadata
from app.models.library import Library
from app.services.chunking import chunking_service
from app.services.content_extraction import content_extraction_service
from app.services.search import ChromaDBService, OllamaEmbeddingService, SemanticSearchService
from app.services.storage import StorageService


async def get_db_session() -> AsyncSession:
    """Create a database session."""
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


async def get_storage_service() -> StorageService:
    """Create storage service."""
    return StorageService()


async def reindex_file(
    db: AsyncSession,
    storage: StorageService,
    search_service: SemanticSearchService,
    file: FileMetadata,
    library: Library,
    dry_run: bool = False,
) -> bool:
    """Reindex a single file."""
    print(f"  Processing: {file.filename} ({file.content_type})")

    if dry_run:
        lang = chunking_service.detect_language(file.filename)
        print(f"    Language: {lang.value}")
        return True

    try:
        # Check if content can be extracted
        if not content_extraction_service.can_extract(file.content_type, file.filename):
            print(f"    Skipping: Content type not extractable")
            return False

        # Download file content
        file_content = await storage.download_file(
            bucket=library.bucket_name,
            key=file.storage_key,
        )

        # Extract text
        extracted_text = await content_extraction_service.extract_text(
            file_content=file_content,
            file_name=file.filename,
            mime_type=file.content_type,
        )

        if not extracted_text:
            print(f"    Warning: No text extracted")
            # Still index with metadata only
            searchable_content = content_extraction_service.create_searchable_content(
                file_name=file.filename,
                file_path=file.path,
                extracted_text=None,
                mime_type=file.content_type,
            )
            success = await search_service.index_file(
                file_id=file.id,
                content=searchable_content,
            )
        else:
            # Use chunked indexing
            success = await search_service.index_file_chunked(
                file_id=file.id,
                content=extracted_text,
                file_name=file.filename,
                mime_type=file.content_type,
            )

        if success:
            print(f"    ✓ Indexed successfully")
        else:
            print(f"    ✗ Indexing failed")

        return success

    except Exception as e:
        print(f"    ✗ Error: {str(e)}")
        return False


async def reindex_library(
    library_id: uuid.UUID,
    language_filter: str = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Reindex all files in a library.

    Returns:
        Tuple of (success_count, error_count)
    """
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    storage = StorageService()

    success_count = 0
    error_count = 0

    async with async_session() as db:
        # Get library
        result = await db.execute(
            select(Library).where(Library.id == library_id)
        )
        library = result.scalar_one_or_none()

        if not library:
            print(f"Library not found: {library_id}")
            await engine.dispose()
            return 0, 0

        print(f"\nReindexing library: {library.name} ({library_id})")
        print(f"Bucket: {library.bucket_name}")

        # Get all files
        query = select(FileMetadata).where(
            FileMetadata.library_id == library_id,
            FileMetadata.is_deleted == False,
        )
        result = await db.execute(query)
        files = result.scalars().all()

        print(f"Total files: {len(files)}")

        # Filter by language if specified
        if language_filter:
            filtered_files = []
            for file in files:
                lang = chunking_service.detect_language(file.filename)
                if lang.value == language_filter:
                    filtered_files.append(file)
            files = filtered_files
            print(f"Files matching language '{language_filter}': {len(files)}")

        if not files:
            print("No files to index")
            await engine.dispose()
            return 0, 0

        # Create search service
        search_service = SemanticSearchService(db=db)

        # Process each file
        for i, file in enumerate(files):
            print(f"\n[{i + 1}/{len(files)}]")
            success = await reindex_file(
                db=db,
                storage=storage,
                search_service=search_service,
                file=file,
                library=library,
                dry_run=dry_run,
            )

            if success:
                success_count += 1
            else:
                error_count += 1

    await engine.dispose()
    return success_count, error_count


async def reindex_all_libraries(
    language_filter: str = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Reindex all libraries."""
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total_success = 0
    total_errors = 0

    async with async_session() as db:
        # Get all libraries
        result = await db.execute(
            select(Library).where(Library.is_deleted == False)
        )
        libraries = result.scalars().all()

        print(f"Found {len(libraries)} libraries")

        for library in libraries:
            success, errors = await reindex_library(
                library_id=library.id,
                language_filter=language_filter,
                dry_run=dry_run,
            )
            total_success += success
            total_errors += errors

    await engine.dispose()
    return total_success, total_errors


async def clear_library_index(library_id: uuid.UUID) -> bool:
    """Clear the vector index for a library."""
    print(f"Clearing index for library: {library_id}")

    try:
        vector_store = ChromaDBService()
        await vector_store.delete_library_collection(library_id)
        print("  ✓ Index cleared")
        return True
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Reindex library files with smart chunking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--library-id",
        type=str,
        help="UUID of the library to reindex",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Reindex all libraries",
    )

    parser.add_argument(
        "--language",
        type=str,
        help="Only reindex files of this language (e.g., python, typescript)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be indexed without actually indexing",
    )

    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="Clear the existing index before reindexing",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Beacon Library - Reindex Script")
    print("=" * 60)

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    async def run():
        if args.library_id:
            library_id = uuid.UUID(args.library_id)

            if args.clear_first and not args.dry_run:
                await clear_library_index(library_id)

            success, errors = await reindex_library(
                library_id=library_id,
                language_filter=args.language,
                dry_run=args.dry_run,
            )
        else:
            # Reindex all libraries
            if args.clear_first and not args.dry_run:
                engine = create_async_engine(settings.database_url, echo=False)
                async_session = sessionmaker(
                    engine, class_=AsyncSession, expire_on_commit=False
                )
                async with async_session() as db:
                    result = await db.execute(
                        select(Library).where(Library.is_deleted == False)
                    )
                    libraries = result.scalars().all()
                    for lib in libraries:
                        await clear_library_index(lib.id)
                await engine.dispose()

            success, errors = await reindex_all_libraries(
                language_filter=args.language,
                dry_run=args.dry_run,
            )

        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Successfully indexed: {success}")
        print(f"Errors: {errors}")

        if args.dry_run:
            print("\n*** DRY RUN - No changes were made ***")

        return errors == 0

    success = asyncio.run(run())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
