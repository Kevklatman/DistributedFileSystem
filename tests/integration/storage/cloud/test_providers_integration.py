"""Integration tests for cloud storage providers."""
import os
import unittest
import uuid
from io import BytesIO

from src.api.storage.cloud.providers import (
    AWSS3Provider,
    AzureBlobProvider,
    GCPStorageProvider
)
from tests.test_config import TEST_CONFIG, TEST_DATA

def generate_test_key():
    """Generate a unique test key."""
    return f'test-{uuid.uuid4()}'

class BaseCloudProviderTest:
    """Base class for cloud provider integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_keys = []
        
    def tearDown(self):
        """Clean up test environment."""
        for key in self.test_keys:
            try:
                self.provider.delete_file(key, self.bucket)
            except:
                pass
                
    def test_upload_download_small_file(self):
        """Test upload and download of a small file."""
        key = generate_test_key()
        self.test_keys.append(key)
        
        # Upload
        result = self.provider.upload_file(
            TEST_DATA['small_file'],
            key,
            self.bucket
        )
        self.assertTrue(result)
        
        # Download
        downloaded = self.provider.download_file(key, self.bucket)
        self.assertEqual(downloaded, TEST_DATA['small_file'])
        
    def test_upload_download_medium_file(self):
        """Test upload and download of a medium file."""
        key = generate_test_key()
        self.test_keys.append(key)
        
        # Upload
        result = self.provider.upload_file(
            TEST_DATA['medium_file'],
            key,
            self.bucket
        )
        self.assertTrue(result)
        
        # Download
        downloaded = self.provider.download_file(key, self.bucket)
        self.assertEqual(downloaded, TEST_DATA['medium_file'])
        
    def test_upload_stream(self):
        """Test upload from a file-like object."""
        key = generate_test_key()
        self.test_keys.append(key)
        
        # Create file-like object
        stream = BytesIO(TEST_DATA['small_file'])
        
        # Upload
        result = self.provider.upload_file(
            stream,
            key,
            self.bucket
        )
        self.assertTrue(result)
        
        # Download and verify
        downloaded = self.provider.download_file(key, self.bucket)
        self.assertEqual(downloaded, TEST_DATA['small_file'])
        
    def test_delete_file(self):
        """Test file deletion."""
        key = generate_test_key()
        
        # Upload file
        result = self.provider.upload_file(
            TEST_DATA['small_file'],
            key,
            self.bucket
        )
        self.assertTrue(result)
        
        # Delete file
        result = self.provider.delete_file(key, self.bucket)
        self.assertTrue(result)
        
        # Verify deletion
        downloaded = self.provider.download_file(key, self.bucket)
        self.assertIsNone(downloaded)
        
    def test_list_objects(self):
        """Test listing objects."""
        # Upload multiple files
        keys = [generate_test_key() for _ in range(3)]
        self.test_keys.extend(keys)
        
        for key in keys:
            result = self.provider.upload_file(
                TEST_DATA['small_file'],
                key,
                self.bucket
            )
            self.assertTrue(result)
            
        # List objects
        objects = self.provider.list_objects(self.bucket)
        listed_keys = [obj['Key'] for obj in objects]
        
        # Verify all test files are listed
        for key in keys:
            self.assertIn(key, listed_keys)

@unittest.skipUnless(
    all([TEST_CONFIG['aws']['access_key'], TEST_CONFIG['aws']['secret_key']]),
    "AWS credentials not configured"
)
class TestAWSS3ProviderIntegration(BaseCloudProviderTest, unittest.TestCase):
    """Integration tests for AWS S3 provider."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.provider = AWSS3Provider()
        self.bucket = TEST_CONFIG['aws']['bucket']
        
        # Create test bucket if it doesn't exist
        self.provider.create_bucket(self.bucket)

@unittest.skipUnless(
    TEST_CONFIG['azure']['connection_string'],
    "Azure credentials not configured"
)
class TestAzureBlobProviderIntegration(BaseCloudProviderTest, unittest.TestCase):
    """Integration tests for Azure Blob Storage provider."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.provider = AzureBlobProvider()
        self.bucket = TEST_CONFIG['azure']['container']
        
        # Create test container if it doesn't exist
        self.provider.create_bucket(self.bucket)

@unittest.skipUnless(
    TEST_CONFIG['gcp']['credentials_path'],
    "GCP credentials not configured"
)
class TestGCPStorageProviderIntegration(BaseCloudProviderTest, unittest.TestCase):
    """Integration tests for Google Cloud Storage provider."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        self.provider = GCPStorageProvider()
        self.bucket = TEST_CONFIG['gcp']['bucket']
        
        # Create test bucket if it doesn't exist
        self.provider.create_bucket(self.bucket)

if __name__ == '__main__':
    unittest.main()
