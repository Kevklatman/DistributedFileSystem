"""
Local storage backend implementation.
"""

import os
import shutil
import asyncio
from typing import Optional, Dict, List, Any, BinaryIO
import logging
from datetime import datetime
from ...api.services.fs_manager import FileSystemManager
from .base import StorageBackend
import uuid
import hashlib

logger = logging.getLogger(__name__)


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend implementation"""

    def __init__(self, fs_manager: FileSystemManager):
        """Initialize local storage backend.

        Args:
            fs_manager: Filesystem manager for handling local storage
        """
        super().__init__(fs_manager)
        self.fs_manager = fs_manager

        # Use storage root from environment or default to data directory
        storage_root = os.environ.get(
            "STORAGE_ROOT", os.path.join(os.getcwd(), "data", "dfs")
        )
        self.data_root = os.path.join(storage_root, "data")

        try:
            # Create storage directories if they don't exist
            os.makedirs(storage_root, exist_ok=True)
            os.makedirs(self.data_root, exist_ok=True)
            logger.info(f"Initialized local storage backend at {storage_root}")
        except Exception as e:
            logger.error(f"Failed to create data directory: {str(e)}")
            raise RuntimeError("Failed to create data directory")

        self.buckets = {}  # In-memory bucket storage
        self.node_status = {}  # Track node status
        self.node_last_seen = {}  # Track last seen time for each node
        self.multipart_uploads = {}  # Track multipart uploads
        self.versions = {}  # Track object versions
        self.versioning = {}  # Track versioning status

        # Initialize buckets from filesystem
        self._init_buckets_from_fs()

        # Initialize node status
        self._init_node_status()

    def _init_node_status(self):
        """Initialize node status"""
        # TODO: Implement node status initialization
        pass

    def _check_consistency(self, consistency_level):
        """Check if consistency level can be satisfied"""
        if consistency_level == "strong":
            healthy_nodes = sum(
                1 for status in self.node_status.values() if status == "healthy"
            )
            return healthy_nodes >= 2
        return True

    def _update_node_status(self, node_id, status):
        """Update node status"""
        self.node_status[node_id] = status
        self.node_last_seen[node_id] = datetime.now()

    def _check_node_health(self):
        """Check health of all nodes"""
        now = datetime.now()
        for node_id in self.node_status:
            if (now - self.node_last_seen[node_id]).seconds > 30:
                self.node_status[node_id] = "unhealthy"

    async def create_bucket(self, bucket_name: str) -> bool:
        """Create a new bucket.

        Args:
            bucket_name: Name of bucket to create

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            bucket_path = os.path.join(self.data_root, bucket_name)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, os.makedirs, bucket_path, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Error creating bucket {bucket_name}: {str(e)}")
            return False

    async def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a bucket.

        Args:
            bucket_name: Name of bucket to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            bucket_path = os.path.join(self.data_root, bucket_name)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, bucket_path)
            return True
        except Exception as e:
            logger.error(f"Error deleting bucket {bucket_name}: {str(e)}")
            return False

    async def list_buckets(self) -> List[str]:
        """List all buckets.

        Returns:
            List[str]: List of bucket names
        """
        try:
            loop = asyncio.get_event_loop()
            buckets = await loop.run_in_executor(None, os.listdir, self.data_root)
            return [
                d for d in buckets if os.path.isdir(os.path.join(self.data_root, d))
            ]
        except Exception as e:
            logger.error(f"Error listing buckets: {str(e)}")
            return []

    async def put_object(self, bucket_name: str, object_key: str, data: bytes) -> bool:
        """Put an object into a bucket.

        Args:
            bucket_name: Name of bucket
            object_key: Key of object
            data: Object data

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            bucket_path = os.path.join(self.data_root, bucket_name)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, os.makedirs, bucket_path, exist_ok=True)
            object_path = os.path.join(bucket_path, object_key)
            await loop.run_in_executor(
                None, self.fs_manager.write_file, object_path, data
            )
            return True
        except Exception as e:
            logger.error(f"Error putting object {object_key}: {str(e)}")
            return False

    async def get_object(self, bucket_name: str, object_key: str) -> Optional[bytes]:
        """Get an object from a bucket.

        Args:
            bucket_name: Name of bucket
            object_key: Key of object

        Returns:
            Optional[bytes]: Object data if found, None otherwise
        """
        try:
            object_path = os.path.join(self.data_root, bucket_name, object_key)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, self.fs_manager.read_file, object_path
            )
            return data
        except Exception as e:
            logger.error(f"Error getting object {object_key}: {str(e)}")
            return None

    async def delete_object(self, bucket_name: str, object_key: str) -> bool:
        """Delete an object from a bucket.

        Args:
            bucket_name: Name of bucket
            object_key: Key of object

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            object_path = os.path.join(self.data_root, bucket_name, object_key)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, os.remove, object_path)
            return True
        except Exception as e:
            logger.error(f"Error deleting object {object_key}: {str(e)}")
            return False

    async def list_objects(self, bucket_name: str) -> List[str]:
        """List objects in a bucket.

        Args:
            bucket_name: Name of bucket

        Returns:
            List[str]: List of object keys
        """
        try:
            bucket_path = os.path.join(self.data_root, bucket_name)
            loop = asyncio.get_event_loop()
            objects = await loop.run_in_executor(None, os.listdir, bucket_path)
            return [f for f in objects if os.path.isfile(os.path.join(bucket_path, f))]
        except Exception as e:
            logger.error(f"Error listing objects in bucket {bucket_name}: {str(e)}")
            return []

    async def create_multipart_upload(self, bucket_name: str, object_key: str):
        """Initialize multipart upload"""
        upload_id = str(uuid.uuid4())
        self.multipart_uploads[upload_id] = {
            "bucket": bucket_name,
            "key": object_key,
            "parts": {},
        }
        return upload_id

    async def upload_part(
        self,
        bucket_name: str,
        object_key: str,
        upload_id: str,
        part_number: int,
        data: BinaryIO,
    ):
        """Upload a part"""
        if upload_id not in self.multipart_uploads:
            return None

        part_data = data.read()
        etag = hashlib.md5(part_data).hexdigest()
        self.multipart_uploads[upload_id]["parts"][part_number] = {
            "data": part_data,
            "etag": etag,
        }
        return etag

    async def complete_multipart_upload(
        self,
        bucket_name: str,
        object_key: str,
        upload_id: str,
        parts: List[Dict[str, Any]],
    ):
        """Complete multipart upload"""
        if upload_id not in self.multipart_uploads:
            return False

        try:
            # Combine all parts
            all_data = b""
            for part in sorted(parts, key=lambda x: x["PartNumber"]):
                part_data = self.multipart_uploads[upload_id]["parts"][
                    part["PartNumber"]
                ]["data"]
                all_data += part_data

            # Write combined data
            full_path = os.path.join(bucket_name, object_key)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self.fs_manager.write_file, full_path, all_data
            )

            # Cleanup
            del self.multipart_uploads[upload_id]
            return True
        except Exception as e:
            logger.error(f"Failed to complete multipart upload: {str(e)}")
            return False

    async def abort_multipart_upload(
        self, bucket_name: str, object_key: str, upload_id: str
    ):
        """Abort multipart upload"""
        if upload_id in self.multipart_uploads:
            del self.multipart_uploads[upload_id]
            return True
        return False

    async def list_multipart_uploads(self, bucket_name: str):
        """List multipart uploads"""
        return [
            {"UploadId": upload_id, "Key": info["key"]}
            for upload_id, info in self.multipart_uploads.items()
            if info["bucket"] == bucket_name
        ]

    async def enable_versioning(self, bucket_name: str):
        """Enable versioning for a bucket"""
        if bucket_name in self.buckets:
            self.versioning[bucket_name] = True
            return True
        return False

    async def disable_versioning(self, bucket_name: str):
        """Disable versioning for a bucket"""
        if bucket_name in self.buckets:
            self.versioning[bucket_name] = False
            return True
        return False

    async def get_versioning_status(self, bucket_name: str):
        """Get versioning status"""
        return self.versioning.get(bucket_name, False)

    async def list_object_versions(
        self, bucket_name: str, prefix: Optional[str] = None
    ):
        """List object versions"""
        if bucket_name not in self.versions:
            return []

        versions = []
        for key, version_list in self.versions[bucket_name].items():
            if prefix and not key.startswith(prefix):
                continue
            for version_id, version_info in version_list.items():
                versions.append(
                    {
                        "Key": key,
                        "VersionId": version_id,
                        "LastModified": version_info["timestamp"],
                        "IsLatest": version_info.get("is_latest", False),
                    }
                )
        return versions

    async def get_object_version(
        self, bucket_name: str, object_key: str, version_id: str
    ):
        """Get specific version"""
        try:
            if (
                bucket_name in self.versions
                and object_key in self.versions[bucket_name]
                and version_id in self.versions[bucket_name][object_key]
            ):
                return self.versions[bucket_name][object_key][version_id]["data"]
        except Exception as e:
            logger.error(
                f"Failed to get version {version_id} of object {object_key}: {str(e)}"
            )
        return None

    async def delete_object_version(
        self, bucket_name: str, object_key: str, version_id: str
    ):
        """Delete specific version"""
        try:
            if (
                bucket_name in self.versions
                and object_key in self.versions[bucket_name]
                and version_id in self.versions[bucket_name][object_key]
            ):
                del self.versions[bucket_name][object_key][version_id]
                return True
        except Exception as e:
            logger.error(
                f"Failed to delete version {version_id} of object {object_key}: {str(e)}"
            )
        return False

    def _generate_version_id(self):
        """Generate a new version ID"""
        return str(uuid.uuid4())

    def _cleanup_orphaned_data(self, bucket_name: str, object_key: str):
        """Clean up orphaned data"""
        try:
            if bucket_name in self.versions:
                if object_key in self.versions[bucket_name]:
                    del self.versions[bucket_name][object_key]
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned data: {str(e)}")

    def _init_buckets_from_fs(self):
        """Initialize buckets from the filesystem"""
        try:
            buckets = self.fs_manager.list_directories()
            for bucket in buckets:
                self.buckets[bucket] = {
                    "name": bucket,
                    "creation_date": datetime.now(),
                    "versioning": False,
                }
        except Exception as e:
            logger.error(f"Failed to initialize buckets from filesystem: {str(e)}")
