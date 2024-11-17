"""Unit tests for cloud storage providers."""
import unittest
from unittest.mock import patch, MagicMock
import os
import boto3
from botocore.exceptions import ClientError
from google.cloud import storage
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError

from src.api.storage.cloud.providers import (
    AWSS3Provider,
    AzureBlobProvider,
    GCPStorageProvider,
    get_cloud_provider
)
from tests.test_config import TEST_CONFIG, TEST_DATA

class TestAWSS3Provider(unittest.TestCase):
    """Test AWS S3 provider implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.env_patcher = patch.dict('os.environ', {
            'AWS_ACCESS_KEY': 'test-key',
            'AWS_SECRET_KEY': 'test-secret',
            'AWS_REGION': 'us-east-1'
        })
        self.env_patcher.start()
        
        self.boto3_patcher = patch('boto3.client')
        self.mock_boto3 = self.boto3_patcher.start()
        self.mock_s3 = MagicMock()
        self.mock_boto3.return_value = self.mock_s3
        self.provider = AWSS3Provider()
        
    def tearDown(self):
        """Clean up test environment."""
        self.boto3_patcher.stop()
        self.env_patcher.stop()
        
    def test_upload_file_success(self):
        """Test successful file upload."""
        self.mock_s3.put_object.return_value = {}
        result = self.provider.upload_file(
            TEST_DATA['small_file'],
            'test.txt',
            TEST_CONFIG['aws']['bucket']
        )
        self.assertTrue(result)
        self.mock_s3.put_object.assert_called_once()
        
    def test_upload_file_failure(self):
        """Test file upload failure."""
        self.mock_s3.put_object.side_effect = ClientError(
            {'Error': {'Code': '500', 'Message': 'Error'}},
            'put_object'
        )
        result = self.provider.upload_file(
            TEST_DATA['small_file'],
            'test.txt',
            TEST_CONFIG['aws']['bucket']
        )
        self.assertFalse(result)
        
    def test_download_file_success(self):
        """Test successful file download."""
        mock_body = MagicMock()
        mock_body.read.return_value = TEST_DATA['small_file']
        self.mock_s3.get_object.return_value = {'Body': mock_body}
        
        result = self.provider.download_file(
            'test.txt',
            TEST_CONFIG['aws']['bucket']
        )
        self.assertEqual(result, TEST_DATA['small_file'])
        
    def test_download_file_failure(self):
        """Test file download failure."""
        self.mock_s3.get_object.side_effect = ClientError(
            {'Error': {'Code': '500', 'Message': 'Error'}},
            'get_object'
        )
        result = self.provider.download_file(
            'test.txt',
            TEST_CONFIG['aws']['bucket']
        )
        self.assertIsNone(result)
        
    def test_delete_file_success(self):
        """Test successful file deletion."""
        self.mock_s3.delete_object.return_value = {}
        result = self.provider.delete_file(
            'test.txt',
            TEST_CONFIG['aws']['bucket']
        )
        self.assertTrue(result)
        self.mock_s3.delete_object.assert_called_once_with(
            Bucket=TEST_CONFIG['aws']['bucket'],
            Key='test.txt'
        )
        
    def test_delete_file_failure(self):
        """Test file deletion failure."""
        self.mock_s3.delete_object.side_effect = ClientError(
            {'Error': {'Code': '500', 'Message': 'Error'}},
            'delete_object'
        )
        result = self.provider.delete_file(
            'test.txt',
            TEST_CONFIG['aws']['bucket']
        )
        self.assertFalse(result)
        
    def test_create_bucket_success(self):
        """Test successful bucket creation."""
        self.mock_s3.create_bucket.return_value = {}
        result = self.provider.create_bucket(
            TEST_CONFIG['aws']['bucket'],
            'us-east-1'
        )
        self.assertTrue(result)
        self.mock_s3.create_bucket.assert_called_once_with(
            Bucket=TEST_CONFIG['aws']['bucket'],
            CreateBucketConfiguration={'LocationConstraint': 'us-east-1'}
        )
        
    def test_create_bucket_failure(self):
        """Test bucket creation failure."""
        self.mock_s3.create_bucket.side_effect = ClientError(
            {'Error': {'Code': '500', 'Message': 'Error'}},
            'create_bucket'
        )
        result = self.provider.create_bucket(TEST_CONFIG['aws']['bucket'])
        self.assertFalse(result)
        
    def test_list_objects_success(self):
        """Test successful object listing."""
        mock_objects = {
            'Contents': [
                {'Key': 'test1.txt', 'Size': 100},
                {'Key': 'test2.txt', 'Size': 200}
            ]
        }
        self.mock_s3.list_objects_v2.return_value = mock_objects
        result = self.provider.list_objects(TEST_CONFIG['aws']['bucket'])
        self.assertEqual(result, mock_objects['Contents'])
        self.mock_s3.list_objects_v2.assert_called_once_with(
            Bucket=TEST_CONFIG['aws']['bucket'],
            Prefix=''
        )
        
    def test_list_objects_failure(self):
        """Test object listing failure."""
        self.mock_s3.list_objects_v2.side_effect = ClientError(
            {'Error': {'Code': '500', 'Message': 'Error'}},
            'list_objects_v2'
        )
        result = self.provider.list_objects(TEST_CONFIG['aws']['bucket'])
        self.assertEqual(result, [])

class TestAzureBlobProvider(unittest.TestCase):
    """Test Azure Blob Storage provider implementation."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;'
        })
        self.env_patcher.start()
        
        # Mock Azure client
        self.mock_service = MagicMock()
        self.mock_container = MagicMock()
        self.mock_blob = MagicMock()
        
        # Set up the mock chain
        self.mock_service.get_container_client.return_value = self.mock_container
        self.mock_container.get_blob_client.return_value = self.mock_blob
        
        # Patch BlobServiceClient.from_connection_string to return our mock
        self.azure_patcher = patch('azure.storage.blob.BlobServiceClient.from_connection_string', return_value=self.mock_service)
        self.azure_patcher.start()
        
        # Create provider after setting up all mocks
        self.provider = AzureBlobProvider()
        
    def tearDown(self):
        """Clean up test environment."""
        self.azure_patcher.stop()
        self.env_patcher.stop()
        
    def test_upload_file_success(self):
        """Test successful file upload."""
        # Configure mock to simulate successful upload
        self.mock_blob.upload_blob.return_value = None  # Azure returns None on success
        
        result = self.provider.upload_file(
            TEST_DATA['small_file'],
            'test.txt',
            TEST_CONFIG['azure']['container']
        )
        self.assertTrue(result)
        
        # Verify mock was called correctly
        self.mock_service.get_container_client.assert_called_once_with(TEST_CONFIG['azure']['container'])
        self.mock_container.get_blob_client.assert_called_once_with('test.txt')
        self.mock_blob.upload_blob.assert_called_once_with(TEST_DATA['small_file'], overwrite=True)
        
    def test_upload_file_failure(self):
        """Test file upload failure."""
        # Configure mock to simulate upload failure
        class CustomAzureError(AzureError):
            def __init__(self):
                super().__init__(message="Test Azure Error")
        
        self.mock_blob.upload_blob.side_effect = CustomAzureError()
        
        result = self.provider.upload_file(
            TEST_DATA['small_file'],
            'test.txt',
            TEST_CONFIG['azure']['container']
        )
        self.assertFalse(result)
        
        # Verify mock was called correctly
        self.mock_service.get_container_client.assert_called_once_with(TEST_CONFIG['azure']['container'])
        self.mock_container.get_blob_client.assert_called_once_with('test.txt')
        self.mock_blob.upload_blob.assert_called_once_with(TEST_DATA['small_file'], overwrite=True)

    def test_download_file_success(self):
        """Test successful file download."""
        mock_blob_data = MagicMock()
        mock_blob_data.readall.return_value = TEST_DATA['small_file']
        self.mock_blob.download_blob.return_value = mock_blob_data
        
        result = self.provider.download_file(
            'test.txt',
            TEST_CONFIG['azure']['container']
        )
        self.assertEqual(result, TEST_DATA['small_file'])
        
        # Verify mock was called correctly
        self.mock_service.get_container_client.assert_called_once_with(TEST_CONFIG['azure']['container'])
        self.mock_container.get_blob_client.assert_called_once_with('test.txt')
        self.mock_blob.download_blob.assert_called_once()
        
    def test_download_file_failure(self):
        """Test file download failure."""
        class CustomAzureError(AzureError):
            def __init__(self):
                super().__init__(message="Test Azure Error")
        
        self.mock_blob.download_blob.side_effect = CustomAzureError()
        
        result = self.provider.download_file(
            'test.txt',
            TEST_CONFIG['azure']['container']
        )
        self.assertIsNone(result)
        
    def test_delete_file_success(self):
        """Test successful file deletion."""
        self.mock_blob.delete_blob.return_value = None
        result = self.provider.delete_file(
            'test.txt',
            TEST_CONFIG['azure']['container']
        )
        self.assertTrue(result)
        
        # Verify mock was called correctly
        self.mock_service.get_container_client.assert_called_once_with(TEST_CONFIG['azure']['container'])
        self.mock_container.get_blob_client.assert_called_once_with('test.txt')
        self.mock_blob.delete_blob.assert_called_once()
        
    def test_delete_file_failure(self):
        """Test file deletion failure."""
        class CustomAzureError(AzureError):
            def __init__(self):
                super().__init__(message="Test Azure Error")
        
        self.mock_blob.delete_blob.side_effect = CustomAzureError()
        result = self.provider.delete_file(
            'test.txt',
            TEST_CONFIG['azure']['container']
        )
        self.assertFalse(result)
        
    def test_create_bucket_success(self):
        """Test successful container creation."""
        self.mock_service.create_container.return_value = None
        result = self.provider.create_bucket(TEST_CONFIG['azure']['container'])
        self.assertTrue(result)
        self.mock_service.create_container.assert_called_once_with(TEST_CONFIG['azure']['container'])
        
    def test_create_bucket_failure(self):
        """Test container creation failure."""
        class CustomAzureError(AzureError):
            def __init__(self):
                super().__init__(message="Test Azure Error")
        
        self.mock_service.create_container.side_effect = CustomAzureError()
        result = self.provider.create_bucket(TEST_CONFIG['azure']['container'])
        self.assertFalse(result)
        
    def test_list_objects_success(self):
        """Test successful object listing."""
        mock_blob1 = MagicMock()
        mock_blob1.name = 'test1.txt'
        mock_blob1.size = 100
        mock_blob1.last_modified = '2023-01-01'
        
        mock_blob2 = MagicMock()
        mock_blob2.name = 'test2.txt'
        mock_blob2.size = 200
        mock_blob2.last_modified = '2023-01-02'
        
        self.mock_container.list_blobs.return_value = [mock_blob1, mock_blob2]
        result = self.provider.list_objects(TEST_CONFIG['azure']['container'])
        
        expected = [
            {'Key': 'test1.txt', 'Size': 100, 'LastModified': '2023-01-01'},
            {'Key': 'test2.txt', 'Size': 200, 'LastModified': '2023-01-02'}
        ]
        self.assertEqual(result, expected)
        self.mock_container.list_blobs.assert_called_once_with(name_starts_with='')
        
    def test_list_objects_failure(self):
        """Test object listing failure."""
        class CustomAzureError(AzureError):
            def __init__(self):
                super().__init__(message="Test Azure Error")
        
        self.mock_container.list_blobs.side_effect = CustomAzureError()
        result = self.provider.list_objects(TEST_CONFIG['azure']['container'])
        self.assertEqual(result, [])

class TestGCPStorageProvider(unittest.TestCase):
    """Test Google Cloud Storage provider implementation."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/credentials.json'
        })
        self.env_patcher.start()
        
        # Mock GCP client
        self.storage_patcher = patch('google.cloud.storage.Client', autospec=True)
        self.mock_storage = self.storage_patcher.start()
        self.mock_client = MagicMock()
        self.mock_bucket = MagicMock()
        self.mock_blob = MagicMock()
        
        self.mock_storage.return_value = self.mock_client
        self.mock_client.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob
        
        # Mock credentials
        self.credentials_patcher = patch('google.auth.default', return_value=(MagicMock(), 'test-project'))
        self.credentials_patcher.start()
        
        self.provider = GCPStorageProvider()
        
    def tearDown(self):
        """Clean up test environment."""
        self.storage_patcher.stop()
        self.credentials_patcher.stop()
        self.env_patcher.stop()
        
    def test_upload_file_success(self):
        """Test successful file upload."""
        result = self.provider.upload_file(
            TEST_DATA['small_file'],
            'test.txt',
            TEST_CONFIG['gcp']['bucket']
        )
        self.assertTrue(result)
        self.mock_blob.upload_from_string.assert_called_once()
        
    def test_upload_file_failure(self):
        """Test file upload failure."""
        self.mock_blob.upload_from_string.side_effect = Exception()
        result = self.provider.upload_file(
            TEST_DATA['small_file'],
            'test.txt',
            TEST_CONFIG['gcp']['bucket']
        )
        self.assertFalse(result)

    def test_download_file_success(self):
        """Test successful file download."""
        self.mock_blob.download_as_bytes.return_value = TEST_DATA['small_file']
        
        result = self.provider.download_file(
            'test.txt',
            TEST_CONFIG['gcp']['bucket']
        )
        self.assertEqual(result, TEST_DATA['small_file'])
        
        # Verify mock was called correctly
        self.mock_client.bucket.assert_called_once_with(TEST_CONFIG['gcp']['bucket'])
        self.mock_bucket.blob.assert_called_once_with('test.txt')
        self.mock_blob.download_as_bytes.assert_called_once()
        
    def test_download_file_failure(self):
        """Test file download failure."""
        self.mock_blob.download_as_bytes.side_effect = Exception("Test GCP Error")
        result = self.provider.download_file(
            'test.txt',
            TEST_CONFIG['gcp']['bucket']
        )
        self.assertIsNone(result)
        
    def test_delete_file_success(self):
        """Test successful file deletion."""
        self.mock_blob.delete.return_value = None
        result = self.provider.delete_file(
            'test.txt',
            TEST_CONFIG['gcp']['bucket']
        )
        self.assertTrue(result)
        
        # Verify mock was called correctly
        self.mock_client.bucket.assert_called_once_with(TEST_CONFIG['gcp']['bucket'])
        self.mock_bucket.blob.assert_called_once_with('test.txt')
        self.mock_blob.delete.assert_called_once()
        
    def test_delete_file_failure(self):
        """Test file deletion failure."""
        self.mock_blob.delete.side_effect = Exception("Test GCP Error")
        result = self.provider.delete_file(
            'test.txt',
            TEST_CONFIG['gcp']['bucket']
        )
        self.assertFalse(result)
        
    def test_create_bucket_success(self):
        """Test successful bucket creation."""
        mock_bucket = MagicMock()
        self.mock_client.create_bucket.return_value = mock_bucket
        result = self.provider.create_bucket(TEST_CONFIG['gcp']['bucket'])
        self.assertTrue(result)
        self.mock_client.create_bucket.assert_called_once_with(TEST_CONFIG['gcp']['bucket'], location=None)
        
    def test_create_bucket_failure(self):
        """Test bucket creation failure."""
        self.mock_client.create_bucket.side_effect = Exception("Test GCP Error")
        result = self.provider.create_bucket(TEST_CONFIG['gcp']['bucket'])
        self.assertFalse(result)
        
    def test_list_objects_success(self):
        """Test successful object listing."""
        mock_blob1 = MagicMock()
        mock_blob1.name = 'test1.txt'
        mock_blob1.size = 100
        mock_blob1.time_created = '2023-01-01'
        
        mock_blob2 = MagicMock()
        mock_blob2.name = 'test2.txt'
        mock_blob2.size = 200
        mock_blob2.time_created = '2023-01-02'
        
        self.mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2]
        
        result = self.provider.list_objects(TEST_CONFIG['gcp']['bucket'])
        expected = [
            {'Key': 'test1.txt', 'Size': 100, 'LastModified': '2023-01-01'},
            {'Key': 'test2.txt', 'Size': 200, 'LastModified': '2023-01-02'}
        ]
        self.assertEqual(result, expected)
        self.mock_client.bucket.assert_called_once_with(TEST_CONFIG['gcp']['bucket'])
        self.mock_bucket.list_blobs.assert_called_once_with(prefix='')
        
    def test_list_objects_failure(self):
        """Test object listing failure."""
        self.mock_bucket.list_blobs.side_effect = Exception("Test GCP Error")
        result = self.provider.list_objects(TEST_CONFIG['gcp']['bucket'])
        self.assertEqual(result, [])

class TestCloudProviderFactory(unittest.TestCase):
    """Test cloud provider factory function."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'AWS_ACCESS_KEY': 'test-key',
            'AWS_SECRET_KEY': 'test-secret',
            'AWS_REGION': 'us-east-1',
            'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;',
            'GOOGLE_APPLICATION_CREDENTIALS': '/path/to/credentials.json'
        })
        self.env_patcher.start()
        
        # Mock cloud clients
        self.boto3_patcher = patch('boto3.client', return_value=MagicMock())
        self.azure_patcher = patch('azure.storage.blob.BlobServiceClient.from_connection_string', return_value=MagicMock())
        self.gcp_patcher = patch('google.cloud.storage.Client', return_value=MagicMock())
        self.credentials_patcher = patch('google.auth.default', return_value=(MagicMock(), 'test-project'))
        
        self.boto3_patcher.start()
        self.azure_patcher.start()
        self.gcp_patcher.start()
        self.credentials_patcher.start()
        
    def tearDown(self):
        """Clean up test environment."""
        self.boto3_patcher.stop()
        self.azure_patcher.stop()
        self.gcp_patcher.stop()
        self.credentials_patcher.stop()
        self.env_patcher.stop()
        
    def test_get_aws_provider(self):
        """Test getting AWS provider."""
        provider = get_cloud_provider('aws')
        self.assertIsInstance(provider, AWSS3Provider)
        
    def test_get_azure_provider(self):
        """Test getting Azure provider."""
        provider = get_cloud_provider('azure')
        self.assertIsInstance(provider, AzureBlobProvider)
        
    def test_get_gcp_provider(self):
        """Test getting GCP provider."""
        provider = get_cloud_provider('gcp')
        self.assertIsInstance(provider, GCPStorageProvider)
        
    def test_get_invalid_provider(self):
        """Test getting invalid provider."""
        with self.assertRaises(ValueError):
            get_cloud_provider('invalid')
