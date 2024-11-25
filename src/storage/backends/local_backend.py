"""
Local storage backend implementation.
"""

import os
import shutil
from typing import Optional, Dict, List, Any, BinaryIO
import logging
from datetime import datetime
from src.api.services.fs_manager import FileSystemManager
from .base import StorageBackend

logger = logging.getLogger(__name__)

class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend implementation"""

    def __init__(self, fs_manager: FileSystemManager):
        super().__init__(fs_manager)
        self.buckets = {}  # In-memory bucket storage
        self.node_status = {}  # Track node status
        self.node_last_seen = {}  # Track last seen time for each node
        self.multipart_uploads = {}  # Track multipart uploads
        self.versions = {}  # Track object versions
        self.versioning = {}  # Track versioning status

        # Create root directory for buckets if it doesn't exist
        try:
            if not self.fs_manager.createDirectory('/buckets'):
                logger.error("Failed to create root buckets directory")
                raise RuntimeError("Failed to create root buckets directory")
        except Exception as e:
            logger.error(f"Error initializing storage backend: {e}")
            raise

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
        if consistency_level == 'strong':
            healthy_nodes = sum(1 for status in self.node_status.values() if status == 'healthy')
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
                self.node_status[node_id] = 'unhealthy'

    def get_object(self, bucket_name: str, object_key: str, consistency_level: str = 'eventual'):
        """Get an object with specified consistency level"""
        try:
            self._check_node_health()
            if not self._check_consistency(consistency_level):
                raise Exception(f"Cannot satisfy {consistency_level} consistency")

            full_path = os.path.join(bucket_name, object_key)
            return self.fs_manager.read_file(full_path)
        except Exception as e:
            logger.error(f"Failed to get object {object_key} from bucket {bucket_name}: {str(e)}")
            return None

    def put_object(self, bucket_name: str, object_key: str, data: BinaryIO, consistency_level: str = 'eventual'):
        """Put an object with specified consistency level"""
        try:
            self._check_node_health()
            if not self._check_consistency(consistency_level):
                raise Exception(f"Cannot satisfy {consistency_level} consistency")

            return super().put_object(bucket_name, object_key, data)
        except Exception as e:
            logger.error(f"Failed to put object {object_key} in bucket {bucket_name}: {str(e)}")
            return False

    def _init_buckets_from_fs(self):
        """Initialize buckets from the filesystem"""
        try:
            buckets = self.fs_manager.list_directories()
            for bucket in buckets:
                self.buckets[bucket] = {
                    'name': bucket,
                    'creation_date': datetime.now(),
                    'versioning': False
                }
        except Exception as e:
            logger.error(f"Failed to initialize buckets from filesystem: {str(e)}")

    def create_bucket(self, bucket_name: str, consistency_level: str = 'eventual'):
        """Create a new bucket"""
        try:
            self._check_node_health()
            if not self._check_consistency(consistency_level):
                raise Exception(f"Cannot satisfy {consistency_level} consistency")

            if super().create_bucket(bucket_name):
                self.buckets[bucket_name] = {
                    'name': bucket_name,
                    'creation_date': datetime.now(),
                    'versioning': False
                }
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {str(e)}")
            return False

    def list_objects(self, bucket_name: str, consistency_level: str = 'eventual'):
        """List objects in a bucket"""
        try:
            self._check_node_health()
            if not self._check_consistency(consistency_level):
                raise Exception(f"Cannot satisfy {consistency_level} consistency")

            objects = self.fs_manager.list_files(bucket_name)
            return [{"Key": obj} for obj in objects]
        except Exception as e:
            logger.error(f"Failed to list objects in bucket {bucket_name}: {str(e)}")
            return []

    def delete_object(self, bucket_name: str, object_key: str):
        """Delete an object"""
        try:
            full_path = os.path.join(bucket_name, object_key)
            return self.fs_manager.delete_file(full_path)
        except Exception as e:
            logger.error(f"Failed to delete object {object_key} from bucket {bucket_name}: {str(e)}")
            return False

    def create_multipart_upload(self, bucket_name: str, object_key: str):
        """Initialize multipart upload"""
        upload_id = str(uuid.uuid4())
        self.multipart_uploads[upload_id] = {
            'bucket': bucket_name,
            'key': object_key,
            'parts': {}
        }
        return upload_id

    def upload_part(self, bucket_name: str, object_key: str, upload_id: str, part_number: int, data: BinaryIO):
        """Upload a part"""
        if upload_id not in self.multipart_uploads:
            return None

        part_data = data.read()
        etag = hashlib.md5(part_data).hexdigest()
        self.multipart_uploads[upload_id]['parts'][part_number] = {
            'data': part_data,
            'etag': etag
        }
        return etag

    def complete_multipart_upload(self, bucket_name: str, object_key: str, upload_id: str, parts: List[Dict[str, Any]]):
        """Complete multipart upload"""
        if upload_id not in self.multipart_uploads:
            return False

        try:
            # Combine all parts
            all_data = b''
            for part in sorted(parts, key=lambda x: x['PartNumber']):
                part_data = self.multipart_uploads[upload_id]['parts'][part['PartNumber']]['data']
                all_data += part_data

            # Write combined data
            full_path = os.path.join(bucket_name, object_key)
            success = self.fs_manager.write_file(full_path, all_data)

            # Cleanup
            del self.multipart_uploads[upload_id]
            return success
        except Exception as e:
            logger.error(f"Failed to complete multipart upload: {str(e)}")
            return False

    def abort_multipart_upload(self, bucket_name: str, object_key: str, upload_id: str):
        """Abort multipart upload"""
        if upload_id in self.multipart_uploads:
            del self.multipart_uploads[upload_id]
            return True
        return False

    def list_multipart_uploads(self, bucket_name: str):
        """List multipart uploads"""
        return [
            {
                'UploadId': upload_id,
                'Key': info['key']
            }
            for upload_id, info in self.multipart_uploads.items()
            if info['bucket'] == bucket_name
        ]

    def enable_versioning(self, bucket_name: str):
        """Enable versioning for a bucket"""
        if bucket_name in self.buckets:
            self.versioning[bucket_name] = True
            return True
        return False

    def disable_versioning(self, bucket_name: str):
        """Disable versioning for a bucket"""
        if bucket_name in self.buckets:
            self.versioning[bucket_name] = False
            return True
        return False

    def get_versioning_status(self, bucket_name: str):
        """Get versioning status"""
        return self.versioning.get(bucket_name, False)

    def list_object_versions(self, bucket_name: str, prefix: Optional[str] = None):
        """List object versions"""
        if bucket_name not in self.versions:
            return []

        versions = []
        for key, version_list in self.versions[bucket_name].items():
            if prefix and not key.startswith(prefix):
                continue
            for version_id, version_info in version_list.items():
                versions.append({
                    'Key': key,
                    'VersionId': version_id,
                    'LastModified': version_info['timestamp'],
                    'IsLatest': version_info.get('is_latest', False)
                })
        return versions

    def get_object_version(self, bucket_name: str, object_key: str, version_id: str):
        """Get specific version"""
        try:
            if (bucket_name in self.versions and
                object_key in self.versions[bucket_name] and
                version_id in self.versions[bucket_name][object_key]):
                return self.versions[bucket_name][object_key][version_id]['data']
        except Exception as e:
            logger.error(f"Failed to get version {version_id} of object {object_key}: {str(e)}")
        return None

    def delete_object_version(self, bucket_name: str, object_key: str, version_id: str):
        """Delete specific version"""
        try:
            if (bucket_name in self.versions and
                object_key in self.versions[bucket_name] and
                version_id in self.versions[bucket_name][object_key]):
                del self.versions[bucket_name][object_key][version_id]
                return True
        except Exception as e:
            logger.error(f"Failed to delete version {version_id} of object {object_key}: {str(e)}")
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
