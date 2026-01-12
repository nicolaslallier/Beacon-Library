"""MinIO/S3 storage service with chunked upload support."""

import hashlib
import io
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, AsyncGenerator, BinaryIO, Dict, List, Optional

import aioboto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class UploadResult:
    """Result of a file upload operation."""
    storage_key: str
    size_bytes: int
    checksum_sha256: str
    content_type: str
    etag: str


@dataclass
class MultipartUploadInfo:
    """Information about an in-progress multipart upload."""
    upload_id: str
    bucket: str
    key: str
    parts: List[Dict[str, Any]]
    created_at: datetime


class StorageService:
    """
    Service for interacting with MinIO/S3 storage.

    Supports:
    - Single-part uploads for small files
    - Multipart uploads for large files (chunked, resumable)
    - Streaming downloads
    - Presigned URLs
    - Bucket management
    """

    def __init__(self):
        self._session = aioboto3.Session()
        self._config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        # Track active multipart uploads
        self._active_uploads: Dict[str, MultipartUploadInfo] = {}

    @asynccontextmanager
    async def _get_client(self):
        """Get an S3 client context manager."""
        async with self._session.client(
            "s3",
            endpoint_url=settings.minio_endpoint_url,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name=settings.minio_region,
            config=self._config,
        ) as client:
            yield client

    # ==========================================================================
    # Bucket Management
    # ==========================================================================

    async def create_bucket(self, bucket_name: str) -> bool:
        """
        Create a new bucket.

        Args:
            bucket_name: Name of the bucket to create

        Returns:
            True if bucket was created, False if it already exists
        """
        async with self._get_client() as client:
            try:
                await client.create_bucket(Bucket=bucket_name)
                logger.info("bucket_created", bucket=bucket_name)
                return True
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                    logger.debug("bucket_exists", bucket=bucket_name)
                    return False
                raise

    async def bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists."""
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=bucket_name)
                return True
            except ClientError:
                return False

    async def delete_bucket(self, bucket_name: str, force: bool = False) -> None:
        """
        Delete a bucket.

        Args:
            bucket_name: Name of the bucket to delete
            force: If True, delete all objects first
        """
        async with self._get_client() as client:
            if force:
                # Delete all objects first
                paginator = client.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=bucket_name):
                    objects = page.get("Contents", [])
                    if objects:
                        delete_objects = [{"Key": obj["Key"]} for obj in objects]
                        await client.delete_objects(
                            Bucket=bucket_name,
                            Delete={"Objects": delete_objects},
                        )

            await client.delete_bucket(Bucket=bucket_name)
            logger.info("bucket_deleted", bucket=bucket_name)

    # ==========================================================================
    # Single-Part Upload (for small files)
    # ==========================================================================

    async def upload_file(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> UploadResult:
        """
        Upload a file in a single request.

        Best for files smaller than the chunk size (5 MB default).

        Args:
            bucket: Bucket name
            key: Object key (path in bucket)
            data: File content as bytes or file-like object
            content_type: MIME type
            metadata: Optional metadata dict

        Returns:
            UploadResult with storage details
        """
        # Convert to bytes if needed
        if hasattr(data, "read"):
            content = data.read()
        else:
            content = data

        # Calculate checksum
        checksum = hashlib.sha256(content).hexdigest()
        size = len(content)

        async with self._get_client() as client:
            extra_args: Dict[str, Any] = {
                "ContentType": content_type,
            }
            if metadata:
                extra_args["Metadata"] = metadata

            try:
                response = await client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    **extra_args,
                )
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "NoSuchBucket":
                    # Bucket doesn't exist, create it and retry
                    logger.info("bucket_missing_creating", bucket=bucket)
                    await self.create_bucket(bucket)
                    response = await client.put_object(
                        Bucket=bucket,
                        Key=key,
                        Body=content,
                        **extra_args,
                    )
                else:
                    raise

            logger.info(
                "file_uploaded",
                bucket=bucket,
                key=key,
                size=size,
                content_type=content_type,
            )

            return UploadResult(
                storage_key=key,
                size_bytes=size,
                checksum_sha256=checksum,
                content_type=content_type,
                etag=response.get("ETag", "").strip('"'),
            )

    # ==========================================================================
    # Multipart Upload (for large files, resumable)
    # ==========================================================================

    async def start_multipart_upload(
        self,
        bucket: str,
        key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Start a multipart upload.

        Args:
            bucket: Bucket name
            key: Object key
            content_type: MIME type
            metadata: Optional metadata

        Returns:
            Upload ID for subsequent part uploads
        """
        async with self._get_client() as client:
            extra_args: Dict[str, Any] = {
                "ContentType": content_type,
            }
            if metadata:
                extra_args["Metadata"] = metadata

            try:
                response = await client.create_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    **extra_args,
                )
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "NoSuchBucket":
                    # Bucket doesn't exist, create it and retry
                    logger.info("bucket_missing_creating", bucket=bucket)
                    await self.create_bucket(bucket)
                    response = await client.create_multipart_upload(
                        Bucket=bucket,
                        Key=key,
                        **extra_args,
                    )
                else:
                    raise

            upload_id = response["UploadId"]

            # Track the upload
            self._active_uploads[upload_id] = MultipartUploadInfo(
                upload_id=upload_id,
                bucket=bucket,
                key=key,
                parts=[],
                created_at=datetime.utcnow(),
            )

            logger.info(
                "multipart_upload_started",
                bucket=bucket,
                key=key,
                upload_id=upload_id,
            )

            return upload_id

    async def upload_part(
        self,
        bucket: str,
        key: str,
        upload_id: str,
        part_number: int,
        data: bytes,
    ) -> Dict[str, Any]:
        """
        Upload a single part of a multipart upload.

        Args:
            bucket: Bucket name
            key: Object key
            upload_id: Upload ID from start_multipart_upload
            part_number: Part number (1-10000)
            data: Part content

        Returns:
            Part info with ETag
        """
        async with self._get_client() as client:
            response = await client.upload_part(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=data,
            )

            part_info = {
                "PartNumber": part_number,
                "ETag": response["ETag"],
                "Size": len(data),
            }

            # Track the part
            if upload_id in self._active_uploads:
                self._active_uploads[upload_id].parts.append(part_info)

            logger.debug(
                "multipart_part_uploaded",
                upload_id=upload_id,
                part_number=part_number,
                size=len(data),
            )

            return part_info

    async def complete_multipart_upload(
        self,
        bucket: str,
        key: str,
        upload_id: str,
        parts: Optional[List[Dict[str, Any]]] = None,
    ) -> UploadResult:
        """
        Complete a multipart upload.

        Args:
            bucket: Bucket name
            key: Object key
            upload_id: Upload ID
            parts: List of part info (optional, uses tracked parts if not provided)

        Returns:
            UploadResult with storage details
        """
        if parts is None and upload_id in self._active_uploads:
            parts = self._active_uploads[upload_id].parts

        if not parts:
            raise ValueError("No parts provided for multipart upload completion")

        # Sort parts by number
        sorted_parts = sorted(parts, key=lambda p: p["PartNumber"])
        multipart_upload = {
            "Parts": [
                {"PartNumber": p["PartNumber"], "ETag": p["ETag"]}
                for p in sorted_parts
            ]
        }

        async with self._get_client() as client:
            response = await client.complete_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload=multipart_upload,
            )

            # Get object info for size
            head_response = await client.head_object(Bucket=bucket, Key=key)
            size = head_response["ContentLength"]
            content_type = head_response.get("ContentType", "application/octet-stream")

            # Calculate checksum (would need to download for accurate SHA256)
            # For now, use ETag as a proxy
            etag = response.get("ETag", "").strip('"')

            # Clean up tracking
            if upload_id in self._active_uploads:
                del self._active_uploads[upload_id]

            logger.info(
                "multipart_upload_completed",
                bucket=bucket,
                key=key,
                upload_id=upload_id,
                size=size,
            )

            return UploadResult(
                storage_key=key,
                size_bytes=size,
                checksum_sha256=etag,  # Note: This is ETag, not SHA256
                content_type=content_type,
                etag=etag,
            )

    async def abort_multipart_upload(
        self,
        bucket: str,
        key: str,
        upload_id: str,
    ) -> None:
        """Abort a multipart upload."""
        async with self._get_client() as client:
            await client.abort_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
            )

            # Clean up tracking
            if upload_id in self._active_uploads:
                del self._active_uploads[upload_id]

            logger.info(
                "multipart_upload_aborted",
                bucket=bucket,
                key=key,
                upload_id=upload_id,
            )

    async def list_multipart_uploads(self, bucket: str) -> List[Dict[str, Any]]:
        """List all in-progress multipart uploads for a bucket."""
        async with self._get_client() as client:
            response = await client.list_multipart_uploads(Bucket=bucket)
            return response.get("Uploads", [])

    # ==========================================================================
    # Download
    # ==========================================================================

    async def download_file(self, bucket: str, key: str) -> bytes:
        """
        Download a file as bytes.

        For large files, use download_file_stream instead.
        """
        async with self._get_client() as client:
            response = await client.get_object(Bucket=bucket, Key=key)
            data = await response["Body"].read()
            return data

    async def download_file_stream(
        self,
        bucket: str,
        key: str,
        chunk_size: int = 1024 * 1024,  # 1 MB chunks
    ) -> AsyncGenerator[bytes, None]:
        """
        Download a file as a stream of chunks.

        Args:
            bucket: Bucket name
            key: Object key
            chunk_size: Size of each chunk in bytes

        Yields:
            Chunks of file data
        """
        async with self._get_client() as client:
            response = await client.get_object(Bucket=bucket, Key=key)
            async for chunk in response["Body"].iter_chunks(chunk_size=chunk_size):
                yield chunk

    # ==========================================================================
    # Presigned URLs
    # ==========================================================================

    async def generate_presigned_download_url(
        self,
        bucket: str,
        key: str,
        expires_in: int = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a presigned URL for downloading a file.

        Args:
            bucket: Bucket name
            key: Object key
            expires_in: URL expiry in seconds (default from settings)
            filename: Optional filename for Content-Disposition header

        Returns:
            Presigned URL
        """
        if expires_in is None:
            expires_in = settings.storage_presigned_url_expiry

        params: Dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
        }

        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        async with self._get_client() as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
            )
            return url

    async def generate_presigned_upload_url(
        self,
        bucket: str,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = None,
    ) -> str:
        """
        Generate a presigned URL for uploading a file.

        Args:
            bucket: Bucket name
            key: Object key
            content_type: Expected content type
            expires_in: URL expiry in seconds

        Returns:
            Presigned URL for PUT request
        """
        if expires_in is None:
            expires_in = settings.storage_presigned_url_expiry

        async with self._get_client() as client:
            url = await client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
            return url

    # ==========================================================================
    # Object Management
    # ==========================================================================

    async def delete_file(self, bucket: str, key: str) -> None:
        """Delete a file from storage."""
        async with self._get_client() as client:
            await client.delete_object(Bucket=bucket, Key=key)
            logger.info("file_deleted", bucket=bucket, key=key)

    async def delete_files(self, bucket: str, keys: List[str]) -> None:
        """Delete multiple files from storage."""
        if not keys:
            return

        async with self._get_client() as client:
            delete_objects = [{"Key": key} for key in keys]
            await client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": delete_objects},
            )
            logger.info("files_deleted", bucket=bucket, count=len(keys))

    async def copy_file(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> None:
        """Copy a file within or between buckets."""
        async with self._get_client() as client:
            await client.copy_object(
                Bucket=dest_bucket,
                Key=dest_key,
                CopySource={"Bucket": source_bucket, "Key": source_key},
            )
            logger.info(
                "file_copied",
                source=f"{source_bucket}/{source_key}",
                dest=f"{dest_bucket}/{dest_key}",
            )

    async def file_exists(self, bucket: str, key: str) -> bool:
        """Check if a file exists."""
        async with self._get_client() as client:
            try:
                await client.head_object(Bucket=bucket, Key=key)
                return True
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return False
                raise

    async def get_file_info(self, bucket: str, key: str) -> Dict[str, Any]:
        """Get file metadata."""
        async with self._get_client() as client:
            response = await client.head_object(Bucket=bucket, Key=key)
            return {
                "size_bytes": response["ContentLength"],
                "content_type": response.get("ContentType", "application/octet-stream"),
                "last_modified": response["LastModified"],
                "etag": response["ETag"].strip('"'),
                "metadata": response.get("Metadata", {}),
            }

    async def list_files(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        List files in a bucket with optional prefix.

        Args:
            bucket: Bucket name
            prefix: Key prefix to filter by
            max_keys: Maximum number of keys to return

        Returns:
            List of file info dicts
        """
        async with self._get_client() as client:
            response = await client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size_bytes": obj["Size"],
                    "last_modified": obj["LastModified"],
                    "etag": obj["ETag"].strip('"'),
                })

            return files

    # ==========================================================================
    # Utility Methods
    # ==========================================================================

    @staticmethod
    def generate_storage_key(
        library_id: uuid.UUID,
        directory_path: str,
        filename: str,
        version: int = 1,
    ) -> str:
        """
        Generate a unique storage key for a file.

        Format: {library_id}/{path}/{filename}_v{version}
        """
        # Normalize path
        path = directory_path.strip("/")
        if path:
            return f"{library_id}/{path}/{filename}_v{version}"
        return f"{library_id}/{filename}_v{version}"

    @staticmethod
    def calculate_checksum(data: bytes) -> str:
        """Calculate SHA-256 checksum of data."""
        return hashlib.sha256(data).hexdigest()


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
