from abc import ABC, abstractmethod
from typing import Optional, BinaryIO, Dict, List, Union
import os
import boto3
from botocore.exceptions import ClientError
from google.cloud import storage
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class CloudStorageProvider(ABC):
    """Abstract base class for cloud storage providers"""
    
    @abstractmethod
    def upload_file(self, file_data: Union[bytes, BinaryIO], object_key: str, bucket: str, **kwargs) -> bool:
        """Upload a file to cloud storage"""
        pass
        
    @abstractmethod
    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        """Download a file from cloud storage"""
        pass
        
    @abstractmethod
    def delete_file(self, object_key: str, bucket: str) -> bool:
        """Delete a file from cloud storage"""
        pass
        
    @abstractmethod
    def create_bucket(self, bucket_name: str, region: Optional[str] = None) -> bool:
        """Create a new storage bucket"""
        pass
        
    @abstractmethod
    def list_objects(self, bucket: str, prefix: str = "") -> List[Dict]:
        """List objects in a bucket with optional prefix"""
        pass

class AWSS3Provider(CloudStorageProvider):
    """AWS S3 implementation of cloud storage provider"""
    
    def __init__(self):
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY')
        self.aws_secret_key = os.getenv('AWS_SECRET_KEY')
        self.region = os.getenv('AWS_REGION', 'us-east-2')
        
        if not all([self.aws_access_key, self.aws_secret_key]):
            raise ValueError("AWS credentials not found in environment variables")
            
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=self.region
        )
    
    def upload_file(self, file_data: Union[bytes, BinaryIO], object_key: str, bucket: str, **kwargs) -> bool:
        try:
            if isinstance(file_data, bytes):
                self.s3.put_object(Bucket=bucket, Key=object_key, Body=file_data)
            else:
                self.s3.upload_fileobj(file_data, bucket, object_key)
            return True
        except ClientError as e:
            logger.error(f"Error uploading to S3: {str(e)}")
            return False

    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        try:
            response = self.s3.get_object(Bucket=bucket, Key=object_key)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Error downloading from S3: {str(e)}")
            return None

    def delete_file(self, object_key: str, bucket: str) -> bool:
        try:
            self.s3.delete_object(Bucket=bucket, Key=object_key)
            return True
        except ClientError as e:
            logger.error(f"Error deleting from S3: {str(e)}")
            return False

    def create_bucket(self, bucket_name: str, region: Optional[str] = None) -> bool:
        try:
            if region is None:
                region = self.region
            self.s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
            return True
        except ClientError as e:
            logger.error(f"Error creating S3 bucket: {str(e)}")
            return False

    def list_objects(self, bucket: str, prefix: str = "") -> List[Dict]:
        try:
            response = self.s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            return response.get('Contents', [])
        except ClientError as e:
            logger.error(f"Error listing S3 objects: {str(e)}")
            return []

class AzureBlobProvider(CloudStorageProvider):
    """Azure Blob Storage implementation"""
    
    def __init__(self):
        self.connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        if not self.connection_string:
            raise ValueError("Azure connection string not found in environment variables")
        
        self.client = BlobServiceClient.from_connection_string(self.connection_string)
    
    def upload_file(self, file_data: Union[bytes, BinaryIO], object_key: str, bucket: str, **kwargs) -> bool:
        try:
            container_client = self.client.get_container_client(bucket)
            blob_client = container_client.get_blob_client(object_key)
            
            if isinstance(file_data, bytes):
                blob_client.upload_blob(file_data, overwrite=True)
            else:
                blob_client.upload_blob(file_data, overwrite=True)
            return True
        except AzureError as e:
            logger.error(f"Error uploading to Azure Blob: {str(e)}")
            return False

    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        try:
            container_client = self.client.get_container_client(bucket)
            blob_client = container_client.get_blob_client(object_key)
            return blob_client.download_blob().readall()
        except AzureError as e:
            logger.error(f"Error downloading from Azure Blob: {str(e)}")
            return None

    def delete_file(self, object_key: str, bucket: str) -> bool:
        try:
            container_client = self.client.get_container_client(bucket)
            blob_client = container_client.get_blob_client(object_key)
            blob_client.delete_blob()
            return True
        except AzureError as e:
            logger.error(f"Error deleting from Azure Blob: {str(e)}")
            return False

    def create_bucket(self, bucket_name: str, region: Optional[str] = None) -> bool:
        try:
            self.client.create_container(bucket_name)
            return True
        except AzureError as e:
            logger.error(f"Error creating Azure container: {str(e)}")
            return False

    def list_objects(self, bucket: str, prefix: str = "") -> List[Dict]:
        try:
            container_client = self.client.get_container_client(bucket)
            blobs = container_client.list_blobs(name_starts_with=prefix)
            return [{"Key": blob.name, "Size": blob.size, "LastModified": blob.last_modified} for blob in blobs]
        except AzureError as e:
            logger.error(f"Error listing Azure blobs: {str(e)}")
            return []

class GCPStorageProvider(CloudStorageProvider):
    """Google Cloud Storage implementation"""
    
    def __init__(self):
        # GCP uses application default credentials or explicit path to service account key
        self.credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not self.credentials_path:
            raise ValueError("GCP credentials path not found in environment variables")
            
        self.client = storage.Client()
    
    def upload_file(self, file_data: Union[bytes, BinaryIO], object_key: str, bucket: str, **kwargs) -> bool:
        try:
            bucket_obj = self.client.bucket(bucket)
            blob = bucket_obj.blob(object_key)
            
            if isinstance(file_data, bytes):
                blob.upload_from_string(file_data)
            else:
                blob.upload_from_file(file_data)
            return True
        except Exception as e:
            logger.error(f"Error uploading to GCS: {str(e)}")
            return False

    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        try:
            bucket_obj = self.client.bucket(bucket)
            blob = bucket_obj.blob(object_key)
            return blob.download_as_bytes()
        except Exception as e:
            logger.error(f"Error downloading from GCS: {str(e)}")
            return None

    def delete_file(self, object_key: str, bucket: str) -> bool:
        try:
            bucket_obj = self.client.bucket(bucket)
            blob = bucket_obj.blob(object_key)
            blob.delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting from GCS: {str(e)}")
            return False

    def create_bucket(self, bucket_name: str, region: Optional[str] = None) -> bool:
        try:
            self.client.create_bucket(bucket_name, location=region)
            return True
        except Exception as e:
            logger.error(f"Error creating GCS bucket: {str(e)}")
            return False

    def list_objects(self, bucket: str, prefix: str = "") -> List[Dict]:
        try:
            bucket_obj = self.client.bucket(bucket)
            blobs = bucket_obj.list_blobs(prefix=prefix)
            return [{"Key": blob.name, "Size": blob.size, "LastModified": blob.time_created} for blob in blobs]
        except Exception as e:
            logger.error(f"Error listing GCS objects: {str(e)}")
            return []

def get_cloud_provider(provider_type: str) -> CloudStorageProvider:
    """Factory function to get the appropriate cloud provider"""
    providers = {
        'aws': AWSS3Provider,
        'azure': AzureBlobProvider,
        'gcp': GCPStorageProvider
    }
    
    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unsupported provider type: {provider_type}")
        
    return provider_class()
