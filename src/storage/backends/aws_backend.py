"""
AWS S3 storage backend implementation.
"""

import os
import boto3
from typing import Optional, Dict, List, Any, BinaryIO
import logging
from datetime import datetime
from src.api.services.config import current_config
from src.api.services.fs_manager import FileSystemManager
from .base import StorageBackend

logger = logging.getLogger(__name__)

class AWSStorageBackend(StorageBackend):
    """AWS S3 storage backend implementation"""

    def __init__(self):
        super().__init__(None)
        if not all([current_config['access_key'], current_config['secret_key']]):
            raise ValueError(
                'AWS credentials not found. Please set AWS_ACCESS_KEY and AWS_SECRET_KEY '
                'environment variables when using AWS storage.'
            )

        # Initialize S3 client with explicit region configuration
        self.region = current_config['region']
        if not self.region:
            self.region = 'us-east-2'  # Fallback to us-east-2 if not set

        logger.info(f"Initial region configuration: {self.region}")

        # Create a client for each AWS region to handle cross-region operations
        self.regional_clients = {}
        self.available_regions = [
            'eu-south-1', 'us-east-1', 'us-west-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1'
        ]

        # Initialize the default client
        self.s3 = self._create_client(self.region)

    def _create_client(self, region):
        """Create an S3 client for a specific region"""
        return boto3.client(
            's3',
            aws_access_key_id=current_config['access_key'],
            aws_secret_access_key=current_config['secret_key'],
            region_name=region,
            config={'signature_version': 's3v4'}
        )

    def _get_client_for_bucket(self, bucket_name):
        """Get the appropriate S3 client for a bucket, handling region differences"""
        try:
            location = self.s3.get_bucket_location(Bucket=bucket_name)
            region = location.get('LocationConstraint', self.region)
            
            if region not in self.regional_clients:
                self.regional_clients[region] = self._create_client(region)
            
            return self.regional_clients[region]
        except Exception as e:
            logger.error(f"Error getting client for bucket {bucket_name}: {str(e)}")
            return self.s3

    def list_objects(self, bucket_name: str, consistency_level: str = 'eventual'):
        """List objects in a bucket, handling region-specific requirements"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            response = client.list_objects_v2(Bucket=bucket_name)
            return [{'Key': obj['Key']} for obj in response.get('Contents', [])]
        except Exception as e:
            logger.error(f"Failed to list objects in bucket {bucket_name}: {str(e)}")
            return []

    def create_bucket(self, bucket_name: str, consistency_level: str = 'eventual'):
        """Create a bucket in the configured region"""
        try:
            kwargs = {'Bucket': bucket_name}
            if self.region != 'us-east-1':
                kwargs['CreateBucketConfiguration'] = {'LocationConstraint': self.region}
            
            self.s3.create_bucket(**kwargs)
            return True
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {str(e)}")
            return False

    def delete_bucket(self, bucket_name: str):
        """Delete a bucket"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            client.delete_bucket(Bucket=bucket_name)
            return True
        except Exception as e:
            logger.error(f"Failed to delete bucket {bucket_name}: {str(e)}")
            return False

    def list_buckets(self):
        """List all buckets"""
        try:
            response = self.s3.list_buckets()
            return [{'Name': bucket['Name'], 'CreationDate': bucket['CreationDate']}
                   for bucket in response['Buckets']]
        except Exception as e:
            logger.error(f"Failed to list buckets: {str(e)}")
            return []

    def put_object(self, bucket_name: str, object_key: str, data: BinaryIO,
                   consistency_level: str = 'eventual'):
        """Put an object into a bucket"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            client.put_object(Bucket=bucket_name, Key=object_key, Body=data)
            return True
        except Exception as e:
            logger.error(f"Failed to put object {object_key}: {str(e)}")
            return False

    def get_object(self, bucket_name: str, object_key: str, consistency_level: str = 'eventual'):
        """Get an object from a bucket"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            response = client.get_object(Bucket=bucket_name, Key=object_key)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Failed to get object {object_key}: {str(e)}")
            return None

    def delete_object(self, bucket_name: str, object_key: str):
        """Delete an object"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            client.delete_object(Bucket=bucket_name, Key=object_key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete object {object_key}: {str(e)}")
            return False

    def create_multipart_upload(self, bucket_name: str, object_key: str):
        """Initialize multipart upload"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            response = client.create_multipart_upload(Bucket=bucket_name, Key=object_key)
            return response['UploadId']
        except Exception as e:
            logger.error(f"Failed to create multipart upload: {str(e)}")
            return None

    def upload_part(self, bucket_name: str, object_key: str, upload_id: str,
                    part_number: int, data: BinaryIO):
        """Upload a part in multipart upload"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            response = client.upload_part(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=data
            )
            return response['ETag']
        except Exception as e:
            logger.error(f"Failed to upload part {part_number}: {str(e)}")
            return None

    def complete_multipart_upload(self, bucket_name: str, object_key: str,
                                 upload_id: str, parts: List[Dict[str, Any]]):
        """Complete multipart upload"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            client.complete_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to complete multipart upload: {str(e)}")
            return False

    def abort_multipart_upload(self, bucket_name: str, object_key: str, upload_id: str):
        """Abort multipart upload"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            client.abort_multipart_upload(
                Bucket=bucket_name,
                Key=object_key,
                UploadId=upload_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to abort multipart upload: {str(e)}")
            return False

    def list_multipart_uploads(self, bucket_name: str):
        """List multipart uploads"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            response = client.list_multipart_uploads(Bucket=bucket_name)
            return [
                {
                    'UploadId': upload['UploadId'],
                    'Key': upload['Key']
                }
                for upload in response.get('Uploads', [])
            ]
        except Exception as e:
            logger.error(f"Failed to list multipart uploads: {str(e)}")
            return []

    def enable_versioning(self, bucket_name: str):
        """Enable versioning"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to enable versioning: {str(e)}")
            return False

    def disable_versioning(self, bucket_name: str):
        """Disable versioning"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Suspended'}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to disable versioning: {str(e)}")
            return False

    def get_versioning_status(self, bucket_name: str):
        """Get versioning status"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            response = client.get_bucket_versioning(Bucket=bucket_name)
            return response.get('Status') == 'Enabled'
        except Exception as e:
            logger.error(f"Failed to get versioning status: {str(e)}")
            return False

    def list_object_versions(self, bucket_name: str, prefix: Optional[str] = None):
        """List object versions"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            kwargs = {'Bucket': bucket_name}
            if prefix:
                kwargs['Prefix'] = prefix
            
            response = client.list_object_versions(**kwargs)
            versions = []
            
            for version in response.get('Versions', []):
                versions.append({
                    'Key': version['Key'],
                    'VersionId': version['VersionId'],
                    'LastModified': version['LastModified'],
                    'IsLatest': version['IsLatest']
                })
            
            return versions
        except Exception as e:
            logger.error(f"Failed to list object versions: {str(e)}")
            return []

    def get_object_version(self, bucket_name: str, object_key: str, version_id: str):
        """Get specific version"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            response = client.get_object(
                Bucket=bucket_name,
                Key=object_key,
                VersionId=version_id
            )
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Failed to get object version: {str(e)}")
            return None

    def delete_object_version(self, bucket_name: str, object_key: str, version_id: str):
        """Delete specific version"""
        try:
            client = self._get_client_for_bucket(bucket_name)
            client.delete_object(
                Bucket=bucket_name,
                Key=object_key,
                VersionId=version_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete object version: {str(e)}")
            return False
