"""Cloud storage provider implementations."""
import os
import time
from typing import Optional, Union, BinaryIO, List, Dict, Any
import boto3
from botocore.exceptions import ClientError
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError
from dotenv import load_dotenv
import logging
import psutil
from storage.infrastructure.interfaces import BaseCloudProvider
from src.storage.metrics.collector import SystemMetricsCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class CloudProviderBase(BaseCloudProvider):
    """Base class for cloud storage providers with metrics collection."""

    def __init__(self):
        """Initialize the cloud provider with metrics collection."""
        super().__init__()
        self.metrics = SystemMetricsCollector()

    def _record_operation(self, operation: str, start_time: float) -> None:
        """Record operation metrics.

        Args:
            operation: Name of the operation
            start_time: Start time of the operation
        """
        duration = time.time() - start_time
        self.metrics.record_operation_latency(operation, duration)

        # Record current resource usage
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_io_counters()
        network = psutil.net_io_counters()

        self.metrics.record_resource_usage(
            cpu=cpu_percent,
            memory=memory.percent,
            disk_io=(disk.read_bytes + disk.write_bytes) / 1024 / 1024,  # MB
            network_io=(network.bytes_sent + network.bytes_recv) / 1024 / 1024  # MB
        )

class AWSS3Provider(CloudProviderBase):
    """AWS S3 storage provider implementation."""

    def __init__(self, aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 region_name: Optional[str] = None):
        """Initialize AWS S3 client.

        Args:
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            region_name: AWS region name
        """
        super().__init__()
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id or os.getenv('AWS_ACCESS_KEY'),
            aws_secret_access_key=aws_secret_access_key or os.getenv('AWS_SECRET_KEY'),
            region_name=region_name or os.getenv('AWS_REGION', 'us-east-2')
        )

    def upload_file(self, file_data: Union[bytes, BinaryIO], object_key: str, bucket: str, **kwargs) -> bool:
        """Upload a file to S3 bucket."""
        try:
            start_time = time.time()
            if isinstance(file_data, bytes):
                self.s3_client.put_object(Bucket=bucket, Key=object_key, Body=file_data)
            else:
                self.s3_client.upload_fileobj(file_data, bucket, object_key)
            self._record_operation('upload', start_time)
            return True
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            return False

    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        """Download a file from S3 bucket."""
        try:
            start_time = time.time()
            response = self.s3_client.get_object(Bucket=bucket, Key=object_key)
            data = response['Body'].read()
            self._record_operation('download', start_time)
            return data
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            return None

    def delete_file(self, object_key: str, bucket: str) -> bool:
        """Delete an object from S3 bucket."""
        try:
            start_time = time.time()
            self.s3_client.delete_object(Bucket=bucket, Key=object_key)
            self._record_operation('delete', start_time)
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            return False

    def list_files(self, bucket: str, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """List objects in S3 bucket."""
        try:
            start_time = time.time()
            if prefix:
                response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            else:
                response = self.s3_client.list_objects_v2(Bucket=bucket)
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'etag': obj['ETag']
                    })
            
            self._record_operation('list', start_time)
            return files
        except ClientError as e:
            logger.error(f"Failed to list files in S3: {e}")
            return []

    def get_file_metadata(self, object_key: str, bucket: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific file in S3."""
        try:
            start_time = time.time()
            response = self.s3_client.head_object(Bucket=bucket, Key=object_key)
            metadata = {
                'size': response['ContentLength'],
                'last_modified': response['LastModified'].isoformat(),
                'etag': response['ETag'],
                'content_type': response.get('ContentType', 'application/octet-stream'),
                'metadata': response.get('Metadata', {})
            }
            self._record_operation('get_metadata', start_time)
            return metadata
        except ClientError as e:
            logger.error(f"Failed to get file metadata from S3: {e}")
            return None

class GCPStorageProvider(CloudProviderBase):
    """Google Cloud Storage provider implementation."""

    def __init__(self):
        """Initialize Google Cloud Storage client using environment variables."""
        super().__init__()

        # Get credentials from environment variables
        project_id = os.getenv('GCP_PROJECT_ID')
        client_email = os.getenv('GCP_CLIENT_EMAIL')
        private_key = os.getenv('GCP_PRIVATE_KEY')

        if not all([project_id, client_email, private_key]):
            raise ValueError("GCP credentials not provided in environment variables")

        # Create credentials dictionary
        credentials_info = {
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key.replace('\\n', '\n'),  # Handle newline escaping
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token"
        }

        # Create credentials object
        credentials = storage.Credentials.from_service_account_info(credentials_info)
        self.storage_client = storage.Client(credentials=credentials, project=project_id)

    def upload_file(self, file_data: Union[bytes, BinaryIO], object_key: str, bucket: str, **kwargs) -> bool:
        """Upload a file to GCS bucket."""
        start_time = time.time()
        try:
            bucket = self.storage_client.bucket(bucket)
            blob = bucket.blob(object_key)

            if isinstance(file_data, bytes):
                blob.upload_from_string(file_data)
            else:
                blob.upload_from_file(file_data)
            return True
        except Exception as e:
            logger.error(f"Error uploading to GCS: {e}")
            return False
        finally:
            self._record_operation('gcs_upload', start_time)

    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        """Download a file from GCS bucket."""
        start_time = time.time()
        try:
            bucket = self.storage_client.bucket(bucket)
            blob = bucket.blob(object_key)
            return blob.download_as_bytes()
        except Exception as e:
            logger.error(f"Error downloading from GCS: {e}")
            return None
        finally:
            self._record_operation('gcs_download', start_time)

    def delete_object(self, object_key: str, bucket: str) -> bool:
        """Delete an object from GCS bucket."""
        start_time = time.time()
        try:
            bucket = self.storage_client.bucket(bucket)
            blob = bucket.blob(object_key)
            blob.delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting from GCS: {e}")
            return False
        finally:
            self._record_operation('gcs_delete', start_time)

    def list_objects(self, bucket: str, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """List objects in GCS bucket."""
        start_time = time.time()
        try:
            blobs = self.storage_client.list_blobs(bucket, prefix=prefix)
            return [{'Key': blob.name, 'Size': blob.size} for blob in blobs]
        except Exception as e:
            logger.error(f"Error listing GCS objects: {e}")
            return []
        finally:
            self._record_operation('gcs_list', start_time)

class AzureBlobProvider(CloudProviderBase):
    """Azure Blob Storage provider implementation."""

    def __init__(self, connection_string: Optional[str] = None):
        """Initialize Azure Blob Storage client.

        Args:
            connection_string: Azure storage account connection string
        """
        super().__init__()
        self.connection_string = connection_string or os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        if not self.connection_string:
            raise ValueError("Azure connection string not provided")
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)

    def upload_file(self, file_data: Union[bytes, BinaryIO], object_key: str, bucket: str, **kwargs) -> bool:
        """Upload a file to Azure container."""
        start_time = time.time()
        try:
            container_client = self.blob_service_client.get_container_client(bucket)
            blob_client = container_client.get_blob_client(object_key)

            if isinstance(file_data, bytes):
                blob_client.upload_blob(file_data, overwrite=True)
            else:
                blob_client.upload_blob(file_data.read(), overwrite=True)
            return True
        except AzureError as e:
            logger.error(f"Error uploading to Azure: {e}")
            return False
        finally:
            self._record_operation('azure_upload', start_time)

    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        """Download a file from Azure container."""
        start_time = time.time()
        try:
            container_client = self.blob_service_client.get_container_client(bucket)
            blob_client = container_client.get_blob_client(object_key)
            return blob_client.download_blob().readall()
        except AzureError as e:
            logger.error(f"Error downloading from Azure: {e}")
            return None
        finally:
            self._record_operation('azure_download', start_time)

    def delete_object(self, object_key: str, bucket: str) -> bool:
        """Delete an object from Azure container."""
        start_time = time.time()
        try:
            container_client = self.blob_service_client.get_container_client(bucket)
            blob_client = container_client.get_blob_client(object_key)
            blob_client.delete_blob()
            return True
        except AzureError as e:
            logger.error(f"Error deleting from Azure: {e}")
            return False
        finally:
            self._record_operation('azure_delete', start_time)

    def list_objects(self, bucket: str, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """List objects in Azure container."""
        start_time = time.time()
        try:
            container_client = self.blob_service_client.get_container_client(bucket)
            blobs = container_client.list_blobs(name_starts_with=prefix)
            return [{'Key': blob.name, 'Size': blob.size} for blob in blobs]
        except AzureError as e:
            logger.error(f"Error listing Azure objects: {e}")
            return []
        finally:
            self._record_operation('azure_list', start_time)

def get_cloud_provider(provider_type: str) -> BaseCloudProvider:
    """Factory function to get the appropriate cloud provider"""
    providers = {
        'aws': AWSS3Provider,
        'aws_s3': AWSS3Provider,  # Add aws_s3 as an alias for aws
        'azure': AzureBlobProvider,
        'gcp': GCPStorageProvider
    }

    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unsupported provider type: {provider_type}")

    return provider_class()
