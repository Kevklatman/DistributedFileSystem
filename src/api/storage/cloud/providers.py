from abc import ABC, abstractmethod
from typing import Optional, BinaryIO, Dict, List
import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class CloudStorageProvider(ABC):
    """Abstract base class for cloud storage providers"""
    
    @abstractmethod
    def upload_file(self, file_data: bytes, object_key: str, bucket: str) -> bool:
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
        
    def upload_file(self, file_data: bytes, object_key: str, bucket: str) -> bool:
        """Upload a file to S3"""
        try:
            from io import BytesIO
            self.s3.upload_fileobj(BytesIO(file_data), bucket, object_key)
            return True
        except ClientError as e:
            print(f"Error uploading to S3: {e}")
            return False
            
    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        """Download a file from S3"""
        try:
            from io import BytesIO
            buffer = BytesIO()
            self.s3.download_fileobj(bucket, object_key, buffer)
            return buffer.getvalue()
        except ClientError as e:
            print(f"Error downloading from S3: {e}")
            return None
            
    def delete_file(self, object_key: str, bucket: str) -> bool:
        """Delete a file from S3"""
        try:
            self.s3.delete_object(Bucket=bucket, Key=object_key)
            return True
        except ClientError as e:
            print(f"Error deleting from S3: {e}")
            return False
            
    def create_bucket(self, bucket_name: str, region: Optional[str] = None) -> bool:
        """Create a new S3 bucket"""
        try:
            region = region or self.region
            location = {'LocationConstraint': region}
            self.s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration=location
            )
            return True
        except ClientError as e:
            print(f"Error creating bucket: {e}")
            return False
            
    def list_objects(self, bucket: str, prefix: str = "") -> List[Dict]:
        """List objects in an S3 bucket"""
        try:
            response = self.s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            return response.get('Contents', [])
        except ClientError as e:
            print(f"Error listing objects: {e}")
            return []

class AzureBlobProvider(CloudStorageProvider):
    """Azure Blob Storage implementation (placeholder)"""
    # TODO: Implement Azure Blob Storage integration
    pass

class GCPStorageProvider(CloudStorageProvider):
    """Google Cloud Storage implementation (placeholder)"""
    # TODO: Implement Google Cloud Storage integration
    pass

def get_cloud_provider(provider_type: str) -> CloudStorageProvider:
    """Factory function to get the appropriate cloud provider"""
    providers = {
        'aws_s3': AWSS3Provider,
        'azure_blob': AzureBlobProvider,
        'gcp_storage': GCPStorageProvider
    }
    
    provider_class = providers.get(provider_type)
    if not provider_class:
        raise ValueError(f"Unsupported cloud provider: {provider_type}")
        
    return provider_class()
