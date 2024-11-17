from abc import ABC, abstractmethod
import boto3
from botocore.client import Config
from config import current_config, STORAGE_ENV
import uuid
import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)

class StorageBackend(ABC):
    def __init__(self):
        self.io_metrics = {
            'bytes_in': 0,
            'bytes_out': 0,
            'latency_ms': 0,
            'iops': 0,
            'bandwidth_mbps': 0,
            'throughput_mbps': 0
        }
        self._start_time = datetime.datetime.now()

    def _update_io_metrics(self, bytes_in=0, bytes_out=0, latency_ms=0):
        """Update I/O metrics"""
        self.io_metrics['bytes_in'] += bytes_in
        self.io_metrics['bytes_out'] += bytes_out
        self.io_metrics['latency_ms'] = latency_ms  # Use latest latency

        # Calculate rates
        time_diff = (datetime.datetime.now() - self._start_time).total_seconds()
        if time_diff > 0:
            total_bytes = self.io_metrics['bytes_in'] + self.io_metrics['bytes_out']
            self.io_metrics['bandwidth_mbps'] = (total_bytes * 8) / (time_diff * 1000000)  # Convert to Mbps
            self.io_metrics['throughput_mbps'] = total_bytes / (time_diff * 1000000)  # MB/s
            self.io_metrics['iops'] = int((self.io_metrics['bytes_in'] + self.io_metrics['bytes_out']) / (time_diff * 1024))  # Operations per second

    def get_io_metrics(self):
        """Get current I/O metrics"""
        return self.io_metrics

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
        super().__init__()
        self.fs_manager = fs_manager
        self.buckets = {}  # In-memory bucket storage
        self.multipart_uploads = {}  # Store multipart upload data
        self.versioning = {}  # Store versioning configuration
        self.versions = {}  # Store object versions
        
        # Create root directory for buckets if it doesn't exist
        self.fs_manager.createDirectory('/buckets')
        
        # Initialize buckets from filesystem
        self._init_buckets_from_fs()
        
    def _init_buckets_from_fs(self):
        """Initialize buckets from the filesystem"""
        try:
            # List all directories under /buckets
            all_files = self.fs_manager.listAllFiles()
            for path in all_files:
                if path.startswith('/buckets/'):
                    bucket_name = path.split('/')[2]  # /buckets/name/...
                    if bucket_name and bucket_name not in self.buckets:
                        self.buckets[bucket_name] = {
                            'name': bucket_name,
                            'creation_date': datetime.datetime.now().isoformat()
                        }
        except Exception as e:
            logger.error(f"Error initializing buckets from filesystem: {e}")
            
    def create_bucket(self, bucket_name):
        """Create a new bucket"""
        if bucket_name in self.buckets:
            return False, "Bucket already exists"
            
        try:
            # Create bucket directory
            bucket_path = f'/buckets/{bucket_name}'
            if not self.fs_manager.createDirectory(bucket_path):
                return False, "Failed to create bucket directory"
                
            # Add bucket to memory
            self.buckets[bucket_name] = {
                'name': bucket_name,
                'creation_date': datetime.datetime.now().isoformat()
            }
            return True, None
        except Exception as e:
            logger.error(f"Error creating bucket: {e}")
            return False, str(e)
            
    def list_buckets(self):
        try:
            buckets = [
                {
                    'Name': bucket_info['name'],
                    'CreationDate': bucket_info['creation_date']
                }
                for bucket_info in self.buckets.values()
            ]
            return buckets, None
        except Exception as e:
            logger.error(f"Error listing buckets: {e}")
            return None, str(e)

    def delete_bucket(self, bucket_name):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        if self.buckets[bucket_name]['objects']:
            return False, "Bucket not empty"

        del self.buckets[bucket_name]
        self.fs_manager.deleteDirectory(f'/buckets/{bucket_name}')
        return True, None

    def put_object(self, bucket_name, object_key, data):
        start_time = datetime.datetime.now()
        
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"

        try:
            # Track incoming bytes
            data_size = len(data)
            self._update_io_metrics(bytes_in=data_size)

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
                    'size': data_size,
                    'last_modified': datetime.datetime.now(datetime.timezone.utc)
                })
            else:
                # If versioning is disabled, just keep the latest version
                self.versions[bucket_name][object_key] = [{
                    'version_id': 'latest',
                    'data': data,
                    'size': data_size,
                    'last_modified': datetime.datetime.now(datetime.timezone.utc)
                }]

            # Update latency
            end_time = datetime.datetime.now()
            latency = (end_time - start_time).total_seconds() * 1000  # Convert to milliseconds
            self._update_io_metrics(latency_ms=latency)

            return True, version_id
        except Exception as e:
            logger.error(f"Error putting object: {e}")
            return False, str(e)

    def get_object(self, bucket_name, object_key):
        start_time = datetime.datetime.now()
        
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"
            
        try:
            # Get the latest version
            if bucket_name in self.versions and object_key in self.versions[bucket_name]:
                versions = self.versions[bucket_name][object_key]
                if versions:
                    latest = versions[-1]
                    data = latest['data']
                    
                    # Track outgoing bytes and latency
                    self._update_io_metrics(bytes_out=len(data))
                    end_time = datetime.datetime.now()
                    latency = (end_time - start_time).total_seconds() * 1000
                    self._update_io_metrics(latency_ms=latency)
                    
                    return data, None
            
            return None, "Object not found"
        except Exception as e:
            logger.error(f"Error getting object: {e}")
            return None, str(e)

    def delete_object(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"

        # Normalize the object key and create file path
        object_key = object_key.lstrip('/')
        file_path = f'/buckets/{bucket_name}/{object_key}'

        # Check if object exists
        if object_key not in self.buckets[bucket_name]['objects']:
            return False, "Object does not exist"

        try:
            # Handle versioning
            if self.versioning.get(bucket_name):
                # If versioning is enabled, add a delete marker
                version_id = self._generate_version_id()
                if bucket_name not in self.versions:
                    self.versions[bucket_name] = {}
                if object_key not in self.versions[bucket_name]:
                    self.versions[bucket_name][object_key] = []

                # Add delete marker
                self.versions[bucket_name][object_key].append({
                    'version_id': version_id,
                    'is_delete_marker': True,
                    'last_modified': datetime.datetime.now(datetime.timezone.utc)
                })

                # Remove from current objects but keep versions
                del self.buckets[bucket_name]['objects'][object_key]
            else:
                # If versioning is not enabled, remove everything
                del self.buckets[bucket_name]['objects'][object_key]
                if bucket_name in self.versions and object_key in self.versions[bucket_name]:
                    del self.versions[bucket_name][object_key]

            # Delete the file from filesystem
            if not self.fs_manager.deleteFile(file_path):
                logger.error(f"Failed to delete file from filesystem: {file_path}")
                # Even if file deletion fails, we've already removed it from our records
                # This is consistent with S3's behavior where delete operations are idempotent

            # Clean up any orphaned data
            self._cleanup_orphaned_data(bucket_name, object_key)

            return True, None

        except Exception as e:
            logger.error(f"Error deleting object {object_key} from bucket {bucket_name}: {str(e)}")
            return False, f"Internal error: {str(e)}"

    def list_objects(self, bucket_name):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"
        return list(self.buckets[bucket_name]['objects'].keys()), None

    def create_multipart_upload(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"

        upload_id = str(uuid.uuid4())
        self.multipart_uploads[f"{bucket_name}/{object_key}"] = {
            'bucket': bucket_name,
            'key': object_key,
            'parts': {},
            'started': datetime.datetime.now(datetime.timezone.utc)
        }
        return upload_id, None

    def upload_part(self, bucket_name, object_key, upload_id, part_number, data):
        if upload_id not in [upload['started'] for upload in self.multipart_uploads.values()]:
            return None, "Upload ID does not exist"

        upload_key = f"{bucket_name}/{object_key}"
        upload = self.multipart_uploads[upload_key]
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
        if upload_id not in [upload['started'] for upload in self.multipart_uploads.values()]:
            return False, "Upload ID does not exist"

        upload_key = f"{bucket_name}/{object_key}"
        upload = self.multipart_uploads[upload_key]
        if upload['bucket'] != bucket_name or upload['key'] != object_key:
            return False, "Bucket or key does not match upload ID"

        # Combine all parts in order
        combined_data = b''
        for part_num in sorted(upload['parts'].keys()):
            combined_data += upload['parts'][part_num]['data']

        # Write the complete file
        success = self.fs_manager.writeFile(f'/buckets/{bucket_name}/{object_key}', combined_data)
        if success:
            self.buckets[bucket_name]['objects'][object_key] = len(combined_data)
            del self.multipart_uploads[upload_key]
        return success, None

    def abort_multipart_upload(self, bucket_name, object_key, upload_id):
        if upload_id not in [upload['started'] for upload in self.multipart_uploads.values()]:
            return False, "Upload ID does not exist"

        upload_key = f"{bucket_name}/{object_key}"
        upload = self.multipart_uploads[upload_key]
        if upload['bucket'] != bucket_name or upload['key'] != object_key:
            return False, "Bucket or key does not match upload ID"

        del self.multipart_uploads[upload_key]
        return True, None

    def list_multipart_uploads(self, bucket_name):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"

        bucket_uploads = [
            {
                'key': upload['key'],
                'upload_id': upload['started'].isoformat(),
                'started': upload['started'].isoformat()
            }
            for upload_key, upload in self.multipart_uploads.items()
            if upload['bucket'] == bucket_name
        ]
        return bucket_uploads, None

    def enable_versioning(self, bucket_name):
        """Enable versioning for a bucket."""
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        self.versioning[bucket_name] = True
        return True, None

    def disable_versioning(self, bucket_name):
        """Disable versioning for a bucket."""
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        self.versioning[bucket_name] = False
        return True, None

    def get_versioning_status(self, bucket_name):
        """Get the versioning status of a bucket."""
        if bucket_name not in self.buckets:
            return False
        return self.versioning.get(bucket_name, False)

    def delete_object_version(self, bucket_name, object_key, version_id):
        """Delete a specific version of an object."""
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"

        # Normalize the object key
        object_key = object_key.lstrip('/')

        # Check if versioning is enabled and versions exist
        if not self.versioning.get(bucket_name):
            return False, "Versioning not enabled for this bucket"

        if bucket_name not in self.versions or object_key not in self.versions[bucket_name]:
            return False, "No versions found for this object"

        # Find and remove the specific version
        versions = self.versions[bucket_name][object_key]
        for i, version in enumerate(versions):
            if version.get('version_id') == version_id:
                versions.pop(i)

                # If this was the last version, clean up the object
                if not versions:
                    del self.versions[bucket_name][object_key]
                    if object_key in self.buckets[bucket_name]['objects']:
                        del self.buckets[bucket_name]['objects'][object_key]

                    # Clean up the file if no versions remain
                    file_path = f'/buckets/{bucket_name}/{object_key}'
                    self.fs_manager.deleteFile(file_path)

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

    def get_object_version(self, bucket_name, object_key, version_id):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"

        # Normalize the object key
        object_key = object_key.lstrip('/')

        # Check if versioning is enabled and versions exist
        if not self.versioning.get(bucket_name):
            return None, "Versioning not enabled for this bucket"

        if bucket_name not in self.versions or object_key not in self.versions[bucket_name]:
            return None, "No versions found for this object"

        # Find and return the specific version
        versions = self.versions[bucket_name][object_key]
        for version in versions:
            if version.get('version_id') == version_id:
                return version['data'], None

        return None, "Version not found"

    def _generate_version_id(self):
        return str(uuid.uuid4())

    def _cleanup_orphaned_data(self, bucket_name, object_key):
        """Clean up any orphaned data for an object"""
        # Clean up versions
        if bucket_name in self.versions:
            if object_key in self.versions[bucket_name]:
                del self.versions[bucket_name][object_key]
            # Remove bucket from versions if empty
            if not self.versions[bucket_name]:
                del self.versions[bucket_name]

        # Clean up multipart uploads
        upload_key = f"{bucket_name}/{object_key}"
        if upload_key in self.multipart_uploads:
            del self.multipart_uploads[upload_key]

class AWSStorageBackend(StorageBackend):
    def __init__(self):
        super().__init__()
        if not all([current_config['access_key'], current_config['secret_key']]):
            raise ValueError(
                'AWS credentials not found. Please set AWS_ACCESS_KEY and AWS_SECRET_KEY '
                'environment variables when using AWS storage.'
            )

        # Initialize S3 client with explicit region configuration
        self.region = current_config['region']
        if not self.region:
            self.region = 'us-east-2'  # Fallback to us-east-2 if not set

        print(f"Initial region configuration: {self.region}")

        # Create a client for each AWS region to handle cross-region operations
        self.regional_clients = {}
        self.available_regions = [
            'eu-south-1', 'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1'
        ]

        # Initialize the default client
        self.s3 = self._create_client(self.region)

    def _create_client(self, region):
        """Create an S3 client for a specific region."""
        kwargs = {
            'aws_access_key_id': current_config['access_key'],
            'aws_secret_access_key': current_config['secret_key'],
            'region_name': region,
            'config': Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            )
        }

        # Add session token if available
        if current_config.get('session_token'):
            kwargs['aws_session_token'] = current_config['session_token']

        # Only add endpoint_url if it's explicitly set and not None or a comment
        endpoint = current_config.get('endpoint')
        if endpoint and isinstance(endpoint, str) and not endpoint.startswith('#'):
            kwargs['endpoint_url'] = endpoint

        return boto3.client('s3', **kwargs)

    def _get_client_for_bucket(self, bucket_name):
        """Get the appropriate S3 client for a bucket, handling region differences."""
        try:
            # Try to get the bucket location
            location = self.s3.get_bucket_location(Bucket=bucket_name)
            region = location.get('LocationConstraint')

            # Handle the special case where None means us-east-1
            if region is None:
                region = 'us-east-1'

            print(f"Bucket {bucket_name} is in region: {region}")

            # If we're already in the right region, use the current client
            if region == self.region:
                return self.s3

            # Create or get a client for the bucket's region
            if region not in self.regional_clients:
                print(f"Creating new client for region: {region}")
                self.regional_clients[region] = self._create_client(region)

            return self.regional_clients[region]

        except self.s3.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                print(f"Access denied when getting bucket location. Trying all available regions...")
                # Try each region until we find one that works
                for region in self.available_regions:
                    try:
                        client = self._create_client(region)
                        # Try a simple operation to test if this is the right region
                        client.head_bucket(Bucket=bucket_name)
                        print(f"Found working region for bucket: {region}")
                        self.regional_clients[region] = client
                        return client
                    except:
                        continue

            # If we couldn't find the right region, use the default client
            print(f"Could not determine bucket region, using default client")
            return self.s3
        except Exception as e:
            print(f"Error getting bucket region: {str(e)}")
            return self.s3

    def list_objects(self, bucket_name):
        """List objects in a bucket, handling region-specific requirements."""
        try:
            # Get the appropriate client for this bucket
            client = self._get_client_for_bucket(bucket_name)

            # Use the region-specific client to list objects
            response = client.list_objects_v2(Bucket=bucket_name)

            objects = response.get('Contents', [])
            return [{'Key': obj['Key'], 'Size': obj['Size'], 'LastModified': obj['LastModified']} for obj in objects]
        except Exception as e:
            print(f"Error listing objects: {str(e)}")
            raise

    def create_bucket(self, bucket_name):
        try:
            # Always specify LocationConstraint for non-us-east-1 regions
            if self.region != 'us-east-1':
                self.s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            else:
                self.s3.create_bucket(Bucket=bucket_name)
            return True, None
        except Exception as e:
            print(f"Error creating bucket: {str(e)}")
            return False, str(e)

    def delete_bucket(self, bucket_name):
        try:
            self.s3.delete_bucket(Bucket=bucket_name)
            return True, None
        except Exception as e:
            return False, str(e)

    def list_buckets(self):
        try:
            logger.debug("Attempting to list buckets with AWS credentials: access_key=%s, region=%s", 
                        current_config['access_key'][:8] + '...', self.region)
            response = self.s3.list_buckets()
            logger.debug("Raw S3 list_buckets response: %s", response)
            buckets = [{'Name': bucket['Name'], 'CreationDate': bucket['CreationDate']} for bucket in response['Buckets']]
            logger.debug("Processed bucket list: %s", buckets)
            return buckets, None
        except Exception as e:
            logger.error("Error listing buckets: %s", str(e), exc_info=True)
            return None, str(e)

    def put_object(self, bucket_name, object_key, data):
        start_time = datetime.datetime.now()
        
        try:
            self.s3.put_object(Bucket=bucket_name, Key=object_key, Body=data)
            
            # Track incoming bytes and latency
            self._update_io_metrics(bytes_in=len(data))
            end_time = datetime.datetime.now()
            latency = (end_time - start_time).total_seconds() * 1000
            self._update_io_metrics(latency_ms=latency)
            
            return True, None
        except Exception as e:
            return False, str(e)

    def get_object(self, bucket_name, object_key):
        start_time = datetime.datetime.now()
        
        try:
            response = self.s3.get_object(Bucket=bucket_name, Key=object_key)
            data = response['Body'].read()
            
            # Track outgoing bytes and latency
            self._update_io_metrics(bytes_out=len(data))
            end_time = datetime.datetime.now()
            latency = (end_time - start_time).total_seconds() * 1000
            self._update_io_metrics(latency_ms=latency)
            
            return data, None
        except Exception as e:
            return None, str(e)

    def delete_object(self, bucket_name, object_key):
        try:
            self.s3.delete_object(Bucket=bucket_name, Key=object_key)
            return True, None
        except Exception as e:
            return False, str(e)

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
