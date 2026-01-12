#!/usr/bin/env python3
"""
Script to create the initial Enterprise Architecture library.

This script uses the backend API directly to create a library.
Run this from the backend directory after the containers are up.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.core.database import get_db
from app.models import Library
from app.services.storage import get_storage_service
import uuid


async def create_enterprise_architecture_library():
    """Create the Enterprise Architecture library."""

    print("🚀 Creating Enterprise Architecture Library...")

    # Get database session
    async for db in get_db():
        try:
            # For now, use a dummy user ID - you'll update this after first login
            # The user ID will be from Keycloak after authentication
            user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

            print(f"ℹ️  Using placeholder user ID: {user_id}")
            print(f"   (Will be updated with your Keycloak user ID on first use)")

            # Check if library already exists
            result = await db.execute(
                select(Library).where(
                    Library.name == "Enterprise Architecture",
                    Library.is_deleted == False,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"ℹ️  Library already exists (ID: {existing.id})")
                print(f"   Bucket: {existing.bucket_name}")
                return

            # Generate library ID and bucket name
            library_id = uuid.uuid4()
            bucket_name = Library.generate_bucket_name(library_id)

            # Create the library record
            library = Library(
                id=library_id,
                name="Enterprise Architecture",
                description="Documentation and diagrams for enterprise architecture, including system designs, integration patterns, and technical specifications",
                bucket_name=bucket_name,
                created_by=user_id,
                owner_id=user_id,
                mcp_write_enabled=True,
                max_file_size_bytes=104857600,  # 100 MB
            )

            db.add(library)

            # Create the MinIO bucket
            print(f"📦 Creating MinIO bucket: {bucket_name}")
            storage = get_storage_service()
            try:
                await storage.create_bucket(bucket_name)
                print(f"✅ Bucket created successfully")
            except Exception as e:
                print(f"⚠️  Warning: Could not create bucket: {e}")
                print(f"   The bucket will be created automatically on first upload")

            # Commit to database
            await db.commit()
            await db.refresh(library)

            print("\n🎉 Library created successfully!")
            print(f"   Name: {library.name}")
            print(f"   ID: {library.id}")
            print(f"   Bucket: {library.bucket_name}")
            print(
                f"\n✨ You can now upload files to this library via the Catalog page!"
            )
            print(f"   After logging in, the owner will be updated to your user.")

        except Exception as e:
            print(f"\n❌ Error creating library: {e}")
            import traceback

            traceback.print_exc()
            await db.rollback()

        break  # Only use first session


if __name__ == "__main__":
    print("=" * 60)
    print("Enterprise Architecture Library Setup")
    print("=" * 60)
    print()

    asyncio.run(create_enterprise_architecture_library())
