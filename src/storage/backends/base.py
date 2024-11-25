"""
Base class for storage backend implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any, BinaryIO
import logging
import os
import asyncio
from datetime import datetime

from src.api.services.fs_manager import FileSystemManager

logger = logging.getLogger(__name__)

class StorageBackend(ABC):
    """Storage backend implementation that handles both simple S3 and AWS S3 operations"""

    def __init__(self, fs_manager: FileSystemManager):
        self.fs_manager = fs_manager

    async def create_bucket(self, bucket_name: str) -> bool:
        """Create a new bucket"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.fs_manager.create_directory, bucket_name)
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {str(e)}")
            return False

    async def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a bucket"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.fs_manager.delete_directory, bucket_name)
        except Exception as e:
            logger.error(f"Failed to delete bucket {bucket_name}: {str(e)}")
            return False

    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all buckets"""
        try:
            loop = asyncio.get_event_loop()
            buckets = await loop.run_in_executor(None, self.fs_manager.list_directories)
            return [
                {
                    "name": bucket,
                    "creation_date": datetime.now().isoformat()
                }
                for bucket in buckets
            ]
        except Exception as e:
            logger.error(f"Failed to list buckets: {str(e)}")
            return []

    async def put_object(self, bucket_name: str, object_key: str, data: bytes,
                        metadata: Optional[Dict[str, str]] = None,
                        storage_class: str = 'STANDARD') -> Dict[str, Any]:
        """Put an object into a bucket"""
        try:
            full_path = os.path.join(bucket_name, object_key)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self.fs_manager.write_file, full_path, data)
            
            if success:
                return {
                    'etag': self.calculate_etag(data),
                    'last_modified': datetime.now().isoformat()
                }
            else:
                raise Exception("Failed to write file")
        except Exception as e:
            logger.error(f"Failed to put object {object_key} in bucket {bucket_name}: {str(e)}")
            raise

    @abstractmethod
    async def get_object(self, bucket_name: str, object_key: str, consistency_level: str = 'eventual'):
        """Get an object from a bucket"""
        pass

    @abstractmethod
    async def delete_object(self, bucket_name: str, object_key: str):
        """Delete an object from a bucket"""
        pass

    @abstractmethod
    async def list_objects(self, bucket_name: str, consistency_level: str = 'eventual'):
        """List objects in a bucket"""
        pass

    @abstractmethod
    async def create_multipart_upload(self, bucket_name: str, object_key: str):
        """Initialize a multipart upload"""
        pass

    @abstractmethod
    async def upload_part(self, bucket_name: str, object_key: str, upload_id: str, part_number: int, data: BinaryIO):
        """Upload a part in a multipart upload"""
        pass

    @abstractmethod
    async def complete_multipart_upload(self, bucket_name: str, object_key: str, upload_id: str, parts: List[Dict[str, Any]]):
        """Complete a multipart upload"""
        pass

    @abstractmethod
    async def abort_multipart_upload(self, bucket_name: str, object_key: str, upload_id: str):
        """Abort a multipart upload"""
        pass

    @abstractmethod
    async def list_multipart_uploads(self, bucket_name: str):
        """List all multipart uploads for a bucket"""
        pass

    @abstractmethod
    async def enable_versioning(self, bucket_name: str):
        """Enable versioning for a bucket"""
        pass

    @abstractmethod
    async def disable_versioning(self, bucket_name: str):
        """Disable versioning for a bucket"""
        pass

    @abstractmethod
    async def get_versioning_status(self, bucket_name: str):
        """Get versioning status for a bucket"""
        pass

    @abstractmethod
    async def list_object_versions(self, bucket_name: str, prefix: Optional[str] = None):
        """List all versions of objects in a bucket"""
        pass

    @abstractmethod
    async def get_object_version(self, bucket_name: str, object_key: str, version_id: str):
        """Get a specific version of an object"""
        pass

    @abstractmethod
    async def delete_object_version(self, bucket_name: str, object_key: str, version_id: str):
        """Delete a specific version of an object"""
        pass

    def calculate_etag(self, data: bytes) -> str:
        """Calculate ETag for an object"""
        import hashlib
        return f'"{hashlib.md5(data).hexdigest()}"'
