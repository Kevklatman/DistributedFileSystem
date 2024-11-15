from abc import ABC, abstractmethod
import boto3
from botocore.client import Config
from config import current_config, STORAGE_ENV
import uuid
import datetime
import hashlib

class StorageBackend(ABC):
    @abstractmethod
    def create_bucket(self, bucket_name):
        pass

    @abstractmethod
    def delete_bucket(self, bucket_name):
        pass

    @abstractmethod
    def list_buckets(self):
        pass

    @abstractmethod
    def put_object(self, bucket_name, object_key, data):
        pass

    @abstractmethod
    def get_object(self, bucket_name, object_key):
        pass

    @abstractmethod
    def delete_object(self, bucket_name, object_key):
        pass

    @abstractmethod
    def list_objects(self, bucket_name):
        pass

    @abstractmethod
    def create_multipart_upload(self, bucket_name, object_key):
        """Initialize a multipart upload and return an upload ID."""
        pass

    @abstractmethod
    def upload_part(self, bucket_name, object_key, upload_id, part_number, data):
        """Upload a part of a multipart upload."""
        pass

    @abstractmethod
    def complete_multipart_upload(self, bucket_name, object_key, upload_id, parts):
        """Complete a multipart upload using the given parts."""
        pass

    @abstractmethod
    def abort_multipart_upload(self, bucket_name, object_key, upload_id):
        """Abort a multipart upload."""
        pass

    @abstractmethod
    def list_multipart_uploads(self, bucket_name):
        """List all in-progress multipart uploads for a bucket."""
        pass

    @abstractmethod
    def enable_versioning(self, bucket_name):
        """Enable versioning for a bucket."""
        pass

    @abstractmethod
    def disable_versioning(self, bucket_name):
        """Disable versioning for a bucket."""
        pass

    @abstractmethod
    def get_versioning_status(self, bucket_name):
        """Get the versioning status of a bucket."""
        pass

    @abstractmethod
    def list_object_versions(self, bucket_name, prefix=None):
        """List all versions of objects in a bucket."""
        pass

    @abstractmethod
    def get_object_version(self, bucket_name, object_key, version_id):
        """Get a specific version of an object."""
        pass

    @abstractmethod
    def delete_object_version(self, bucket_name, object_key, version_id):
        """Delete a specific version of an object."""
        pass

class LocalStorageBackend(StorageBackend):
    def __init__(self, fs_manager):
        self.fs_manager = fs_manager
        self.buckets = {}  # In-memory bucket storage
        self.multipart_uploads = {}  # Store multipart upload data
        self.versioning = {}  # Store versioning configuration
        self.versions = {}  # Store object versions

    def _generate_version_id(self):
        return str(uuid.uuid4())

    def create_bucket(self, bucket_name):
        if bucket_name in self.buckets:
            return False, "Bucket already exists"

        self.buckets[bucket_name] = {
            'objects': {}
        }
        self.fs_manager.createDirectory(f'/{bucket_name}')
        return True, None

    def delete_bucket(self, bucket_name):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        if self.buckets[bucket_name]['objects']:
            return False, "Bucket not empty"

        del self.buckets[bucket_name]
        self.fs_manager.deleteDirectory(f'/{bucket_name}')
        return True, None

    def list_buckets(self):
        return list(self.buckets.keys())

    def put_object(self, bucket_name, object_key, data):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"

        # Initialize versions dict for bucket if needed
        if bucket_name not in self.versions:
            self.versions[bucket_name] = {}
        if object_key not in self.versions[bucket_name]:
            self.versions[bucket_name][object_key] = []

        # Generate version ID if versioning is enabled
        version_id = None
        if self.versioning.get(bucket_name):
            version_id = self._generate_version_id()
            # Store the current version
            self.versions[bucket_name][object_key].append({
                'version_id': version_id,
                'data': data,
                'size': len(data),
                'last_modified': datetime.datetime.now(datetime.timezone.utc)
            })
        else:
            # If versioning is disabled, just keep the latest version
            self.versions[bucket_name][object_key] = [{
                'version_id': 'latest',
                'data': data,
                'size': len(data),
                'last_modified': datetime.datetime.now(datetime.timezone.utc)
            }]

        # Update the object size in buckets
        self.buckets[bucket_name]['objects'][object_key] = len(data)
        return True, version_id

    def get_object(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"
        if object_key not in self.buckets[bucket_name]['objects']:
            return None, "Object does not exist"

        # Get the latest version
        versions = self.versions.get(bucket_name, {}).get(object_key, [])
        if not versions:
            return None, "Object has no versions"
        return versions[-1]['data'], None

    def delete_object(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        if object_key not in self.buckets[bucket_name]['objects']:
            return False, "Object does not exist"

        if self.versioning.get(bucket_name):
            # If versioning is enabled, add a delete marker
            version_id = self._generate_version_id()
            if bucket_name not in self.versions:
                self.versions[bucket_name] = {}
            if object_key not in self.versions[bucket_name]:
                self.versions[bucket_name][object_key] = []
            self.versions[bucket_name][object_key].append({
                'version_id': version_id,
                'is_delete_marker': True,
                'last_modified': datetime.datetime.now(datetime.timezone.utc)
            })
        else:
            # If versioning is disabled, actually delete the object
            del self.buckets[bucket_name]['objects'][object_key]
            if bucket_name in self.versions and object_key in self.versions[bucket_name]:
                del self.versions[bucket_name][object_key]

        return True, None

    def list_objects(self, bucket_name):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"
        return list(self.buckets[bucket_name]['objects'].keys()), None

    def create_multipart_upload(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"

        upload_id = str(uuid.uuid4())
        self.multipart_uploads[upload_id] = {
            'bucket': bucket_name,
            'key': object_key,
            'parts': {},
            'started': datetime.datetime.now(datetime.timezone.utc)
        }
        return upload_id, None

    def upload_part(self, bucket_name, object_key, upload_id, part_number, data):
        if upload_id not in self.multipart_uploads:
            return None, "Upload ID does not exist"

        upload = self.multipart_uploads[upload_id]
        if upload['bucket'] != bucket_name or upload['key'] != object_key:
            return None, "Bucket or key does not match upload ID"

        # Store the part data
        etag = hashlib.md5(data).hexdigest()
        upload['parts'][part_number] = {
            'data': data,
            'etag': etag,
            'size': len(data)
        }
        return etag, None

    def complete_multipart_upload(self, bucket_name, object_key, upload_id, parts):
        if upload_id not in self.multipart_uploads:
            return False, "Upload ID does not exist"

        upload = self.multipart_uploads[upload_id]
        if upload['bucket'] != bucket_name or upload['key'] != object_key:
            return False, "Bucket or key does not match upload ID"

        # Combine all parts in order
        combined_data = b''
        for part_num in sorted(upload['parts'].keys()):
            combined_data += upload['parts'][part_num]['data']

        # Write the complete file
        success = self.fs_manager.writeFile(f'/{bucket_name}/{object_key}', combined_data)
        if success:
            self.buckets[bucket_name]['objects'][object_key] = len(combined_data)
            del self.multipart_uploads[upload_id]
        return success, None

    def abort_multipart_upload(self, bucket_name, object_key, upload_id):
        if upload_id not in self.multipart_uploads:
            return False, "Upload ID does not exist"

        upload = self.multipart_uploads[upload_id]
        if upload['bucket'] != bucket_name or upload['key'] != object_key:
            return False, "Bucket or key does not match upload ID"

        del self.multipart_uploads[upload_id]
        return True, None

    def list_multipart_uploads(self, bucket_name):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"

        bucket_uploads = [
            {
                'key': upload['key'],
                'upload_id': upload_id,
                'started': upload['started'].isoformat()
            }
            for upload_id, upload in self.multipart_uploads.items()
            if upload['bucket'] == bucket_name
        ]
        return bucket_uploads, None

    def enable_versioning(self, bucket_name):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        self.versioning[bucket_name] = True
        return True, None

    def disable_versioning(self, bucket_name):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        self.versioning[bucket_name] = False
        return True, None

    def get_versioning_status(self, bucket_name):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"
        return self.versioning.get(bucket_name, False), None

    def get_object_version(self, bucket_name, object_key, version_id):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"
        if object_key not in self.versions.get(bucket_name, {}):
            return None, "Object does not exist"

        # Find the specific version
        for version in self.versions[bucket_name][object_key]:
            if version['version_id'] == version_id:
                return version['data'], None
        return None, "Version not found"

    def delete_object_version(self, bucket_name, object_key, version_id):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        if object_key not in self.versions.get(bucket_name, {}):
            return False, "Object does not exist"

        # Remove the specific version
        versions = self.versions[bucket_name][object_key]
        for i, version in enumerate(versions):
            if version['version_id'] == version_id:
                versions.pop(i)
                if not versions:  # If no versions left
                    del self.versions[bucket_name][object_key]
                    del self.buckets[bucket_name]['objects'][object_key]
                return True, None
        return False, "Version not found"

    def list_object_versions(self, bucket_name, prefix=None):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"

        versions = []
        bucket_versions = self.versions.get(bucket_name, {})
        for key, obj_versions in bucket_versions.items():
            if prefix is None or key.startswith(prefix):
                for version in obj_versions:
                    versions.append({
                        'Key': key,
                        'VersionId': version['version_id'],
                        'IsLatest': version == obj_versions[-1],
                        'LastModified': version['last_modified'].isoformat(),
                        'Size': version.get('size', 0),
                        'IsDeleteMarker': version.get('is_delete_marker', False)
                    })
        return versions, None

class AWSStorageBackend(StorageBackend):
    def __init__(self):
        if not all([current_config['access_key'], current_config['secret_key']]):
            raise ValueError(
                'AWS credentials not found. Please set AWS_ACCESS_KEY and AWS_SECRET_KEY '
                'environment variables when using AWS storage.'
            )
            
        self.s3 = boto3.client(
            's3',
            endpoint_url=current_config.get('endpoint'),
            aws_access_key_id=current_config['access_key'],
            aws_secret_access_key=current_config['secret_key'],
            region_name=current_config['region']
        )

    def create_bucket(self, bucket_name):
        try:
            self.s3.create_bucket(Bucket=bucket_name)
            return True, None
        except Exception as e:
            return False, str(e)

    def delete_bucket(self, bucket_name):
        try:
            self.s3.delete_bucket(Bucket=bucket_name)
            return True, None
        except Exception as e:
            return False, str(e)

    def list_buckets(self):
        try:
            response = self.s3.list_buckets()
            return [bucket['Name'] for bucket in response['Buckets']], None
        except Exception as e:
            return None, str(e)

    def put_object(self, bucket_name, object_key, data):
        try:
            self.s3.put_object(Bucket=bucket_name, Key=object_key, Body=data)
            return True, None
        except Exception as e:
            return False, str(e)

    def get_object(self, bucket_name, object_key):
        try:
            response = self.s3.get_object(Bucket=bucket_name, Key=object_key)
            return response['Body'].read(), None
        except Exception as e:
            return None, str(e)

    def delete_object(self, bucket_name, object_key):
        try:
            self.s3.delete_object(Bucket=bucket_name, Key=object_key)
            return True, None
        except Exception as e:
            return False, str(e)

    def list_objects(self, bucket_name):
        try:
            response = self.s3.list_objects_v2(Bucket=bucket_name)
            return [obj['Key'] for obj in response.get('Contents', [])], None
        except Exception as e:
            return None, str(e)

    def create_multipart_upload(self, bucket_name, object_key):
        try:
            response = self.s3.create_multipart_upload(Bucket=bucket_name, Key=object_key)
            return response['UploadId'], None
        except Exception as e:
            return None, str(e)

    def upload_part(self, bucket_name, object_key, upload_id, part_number, data):
        try:
            response = self.s3.upload_part(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=data
            )
            return response['ETag'], None
        except Exception as e:
            return None, str(e)

    def complete_multipart_upload(self, bucket_name, object_key, upload_id, parts):
        try:
            response = self.s3.complete_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            return True, None
        except Exception as e:
            return False, str(e)

    def abort_multipart_upload(self, bucket_name, object_key, upload_id):
        try:
            self.s3.abort_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id
            )
            return True, None
        except Exception as e:
            return False, str(e)

    def list_multipart_uploads(self, bucket_name):
        try:
            response = self.s3.list_multipart_uploads(Bucket=bucket_name)
            uploads = [{
                'key': upload['Key'],
                'upload_id': upload['UploadId'],
                'started': upload['Initiated'].isoformat()
            } for upload in response.get('Uploads', [])]
            return uploads, None
        except Exception as e:
            return None, str(e)

    def enable_versioning(self, bucket_name):
        try:
            self.s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            return True, None
        except Exception as e:
            return False, str(e)

    def disable_versioning(self, bucket_name):
        try:
            self.s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Suspended'}
            )
            return True, None
        except Exception as e:
            return False, str(e)

    def get_versioning_status(self, bucket_name):
        try:
            response = self.s3.get_bucket_versioning(Bucket=bucket_name)
            return response.get('Status') == 'Enabled', None
        except Exception as e:
            return None, str(e)

    def list_object_versions(self, bucket_name, prefix=None):
        try:
            params = {'Bucket': bucket_name}
            if prefix:
                params['Prefix'] = prefix
            response = self.s3.list_object_versions(**params)
            
            versions = []
            for version in response.get('Versions', []):
                versions.append({
                    'Key': version['Key'],
                    'VersionId': version['VersionId'],
                    'IsLatest': version['IsLatest'],
                    'LastModified': version['LastModified'].isoformat(),
                    'Size': version['Size'],
                    'IsDeleteMarker': False
                })
            for marker in response.get('DeleteMarkers', []):
                versions.append({
                    'Key': marker['Key'],
                    'VersionId': marker['VersionId'],
                    'IsLatest': marker['IsLatest'],
                    'LastModified': marker['LastModified'].isoformat(),
                    'Size': 0,
                    'IsDeleteMarker': True
                })
            return versions, None
        except Exception as e:
            return None, str(e)

    def get_object_version(self, bucket_name, object_key, version_id):
        try:
            response = self.s3.get_object(
                Bucket=bucket_name,
                Key=object_key,
                VersionId=version_id
            )
            return response['Body'].read(), None
        except Exception as e:
            return None, str(e)

    def delete_object_version(self, bucket_name, object_key, version_id):
        try:
            self.s3.delete_object(
                Bucket=bucket_name,
                Key=object_key,
                VersionId=version_id
            )
            return True, None
        except Exception as e:
            return False, str(e)

def get_storage_backend(fs_manager=None):
    """Factory function to get the appropriate storage backend"""
    if STORAGE_ENV == 'local':
        if fs_manager is None:
            raise ValueError("fs_manager is required for local storage")
        return LocalStorageBackend(fs_manager)
    else:
        return AWSStorageBackend()