"""Unit tests for cloud storage providers."""
import unittest
from unittest.mock import Mock, patch, MagicMock, ANY
import io
import os
from src.api.storage.cloud.providers import AWSS3Provider, AzureBlobProvider, GCPStorageProvider
from src.api.storage.cloud.config import TransferConfig
from src.api.storage.cloud.transfer import TransferManager

class TestAWSS3Provider(unittest.TestCase):
    """Test cases for AWS S3 provider"""

    def setUp(self):
        """Set up test environment"""
        self.mock_env = {
            'AWS_ACCESS_KEY': 'test-key',
            'AWS_SECRET_KEY': 'test-secret',
            'AWS_REGION': 'us-east-1'
        }
        self.patcher = patch.dict('os.environ', self.mock_env)
        self.patcher.start()

        # Create a custom transfer config for testing
        self.transfer_config = TransferConfig(
            multipart_threshold=5 * 1024 * 1024,  # 5MB
            multipart_chunksize=1 * 1024 * 1024,  # 1MB
            max_attempts=3,
            retry_mode='exponential',
            upload_bandwidth_limit=1024 * 1024,  # 1MB/s
            download_bandwidth_limit=1024 * 1024  # 1MB/s
        )

        self.provider = AWSS3Provider(self.transfer_config)
        self.mock_s3 = Mock()
        self.provider.s3 = self.mock_s3

    def tearDown(self):
        """Clean up test environment"""
        self.patcher.stop()

    def test_init_with_transfer_config(self):
        """Test initialization with transfer config"""
        provider = AWSS3Provider(self.transfer_config)
        self.assertEqual(provider.transfer_config.multipart_threshold, 5 * 1024 * 1024)
        self.assertEqual(provider.transfer_config.multipart_chunksize, 1 * 1024 * 1024)

    def test_upload_small_file_bytes(self):
        """Test uploading small file with bytes"""
        data = b"test data"
        self.provider.upload_file(data, "test.txt", "test-bucket")
        self.mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test.txt",
            Body=data,
            StorageClass=self.transfer_config.storage_class
        )

    def test_upload_small_file_stream(self):
        """Test uploading small file with file stream"""
        data = io.BytesIO(b"test data")
        self.provider.upload_file(data, "test.txt", "test-bucket")
        self.mock_s3.upload_fileobj.assert_called_once_with(
            data,
            "test-bucket",
            "test.txt",
            ExtraArgs={'StorageClass': self.transfer_config.storage_class}
        )

    def test_upload_large_file_multipart(self):
        """Test multipart upload for large files"""
        # Create a large file that exceeds multipart threshold
        large_data = b"x" * (6 * 1024 * 1024)  # 6MB
        file_obj = io.BytesIO(large_data)

        # Mock multipart upload responses
        self.mock_s3.create_multipart_upload.return_value = {'UploadId': 'test-upload-id'}
        self.mock_s3.upload_part.return_value = {'ETag': 'test-etag'}

        self.provider.upload_file(file_obj, "large.txt", "test-bucket")

        # Verify multipart upload was initiated
        self.mock_s3.create_multipart_upload.assert_called_once()

        # Verify parts were uploaded
        self.assertTrue(self.mock_s3.upload_part.called)

        # Verify multipart upload was completed
        self.mock_s3.complete_multipart_upload.assert_called_once()

    def test_download_with_bandwidth_limit(self):
        """Test downloading with bandwidth throttling"""
        mock_response = {'Body': io.BytesIO(b"test data")}
        self.mock_s3.get_object.return_value = mock_response

        result = self.provider.download_file("test.txt", "test-bucket")

        self.assertEqual(result, b"test data")
        self.mock_s3.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test.txt"
        )

    def test_retry_on_failure(self):
        """Test retry mechanism on failure"""
        self.mock_s3.get_object.side_effect = [
            Exception("Temporary failure"),
            Exception("Another failure"),
            {'Body': io.BytesIO(b"success")}
        ]

        result = self.provider.download_file("test.txt", "test-bucket")

        self.assertEqual(result, b"success")
        self.assertEqual(self.mock_s3.get_object.call_count, 3)

    def test_abort_multipart_on_failure(self):
        """Test multipart upload abort on failure"""
        large_data = b"x" * (6 * 1024 * 1024)
        file_obj = io.BytesIO(large_data)

        self.mock_s3.create_multipart_upload.return_value = {'UploadId': 'test-upload-id'}
        self.mock_s3.upload_part.side_effect = Exception("Upload failed")

        self.provider.upload_file(file_obj, "large.txt", "test-bucket")

        self.mock_s3.abort_multipart_upload.assert_called_once_with(
            Bucket="test-bucket",
            Key="large.txt",
            UploadId="test-upload-id"
        )

    def test_transfer_acceleration(self):
        """Test S3 transfer acceleration configuration"""
        config = TransferConfig(use_transfer_acceleration=True)
        provider = AWSS3Provider(config)

        # Verify S3 client was configured with acceleration endpoint
        self.assertTrue(provider.s3._client_config.s3['use_accelerate_endpoint'])

    def test_storage_class_setting(self):
        """Test storage class configuration"""
        config = TransferConfig(storage_class="STANDARD_IA")
        provider = AWSS3Provider(config)

        data = b"test data"
        provider.s3 = self.mock_s3
        provider.upload_file(data, "test.txt", "test-bucket")

        self.mock_s3.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test.txt",
            Body=data,
            StorageClass="STANDARD_IA"
        )

class TestAzureBlobProvider(unittest.TestCase):
    """Test cases for Azure Blob provider"""

    def setUp(self):
        """Set up test environment"""
        self.mock_env = {
            'AZURE_STORAGE_CONNECTION_STRING': 'test-connection-string'
        }
        self.patcher = patch.dict('os.environ', self.mock_env)
        self.patcher.start()

        self.transfer_config = TransferConfig()
        self.provider = AzureBlobProvider(self.transfer_config)
        self.mock_blob_service = Mock()
        self.provider.blob_service = self.mock_blob_service

    def tearDown(self):
        """Clean up test environment"""
        self.patcher.stop()

    def test_init_with_transfer_config(self):
        """Test initialization with transfer config"""
        provider = AzureBlobProvider(self.transfer_config)
        self.assertEqual(provider.transfer_config.multipart_threshold, 5 * 1024 * 1024)
        self.assertEqual(provider.transfer_config.multipart_chunksize, 1 * 1024 * 1024)

    def test_upload_small_file_bytes(self):
        """Test uploading small file with bytes"""
        data = b"test data"
        self.provider.upload_file(data, "test.txt", "test-container")
        self.mock_blob_service.get_blob_client.assert_called_once_with("test.txt")
        self.mock_blob_service.get_blob_client.return_value.upload_blob.assert_called_once_with(data, overwrite=True)

    def test_upload_small_file_stream(self):
        """Test uploading small file with file stream"""
        data = io.BytesIO(b"test data")
        self.provider.upload_file(data, "test.txt", "test-container")
        self.mock_blob_service.get_blob_client.assert_called_once_with("test.txt")
        self.mock_blob_service.get_blob_client.return_value.upload_blob.assert_called_once_with(data, overwrite=True)

    def test_upload_large_file_multipart(self):
        """Test multipart upload for large files"""
        # Create a large file that exceeds multipart threshold
        large_data = b"x" * (6 * 1024 * 1024)  # 6MB
        file_obj = io.BytesIO(large_data)

        # Mock multipart upload responses
        self.mock_blob_service.get_blob_client.return_value.stage_block.side_effect = ['block1', 'block2']
        self.mock_blob_service.get_blob_client.return_value.commit_block_list.side_effect = ['commit1', 'commit2']

        self.provider.upload_file(file_obj, "large.txt", "test-container")

        # Verify multipart upload was initiated
        self.mock_blob_service.get_blob_client.assert_called_once_with("large.txt")

        # Verify parts were uploaded
        self.assertTrue(self.mock_blob_service.get_blob_client.return_value.stage_block.called)

        # Verify multipart upload was completed
        self.mock_blob_service.get_blob_client.return_value.commit_block_list.assert_called_once()

    def test_download_with_bandwidth_limit(self):
        """Test downloading with bandwidth throttling"""
        mock_response = {'content': io.BytesIO(b"test data")}
        self.mock_blob_service.get_blob_client.return_value.download_blob.return_value = mock_response

        result = self.provider.download_file("test.txt", "test-container")

        self.assertEqual(result, b"test data")
        self.mock_blob_service.get_blob_client.assert_called_once_with("test.txt")
        self.mock_blob_service.get_blob_client.return_value.download_blob.assert_called_once()

    def test_retry_on_failure(self):
        """Test retry mechanism on failure"""
        self.mock_blob_service.get_blob_client.return_value.download_blob.side_effect = [
            Exception("Temporary failure"),
            Exception("Another failure"),
            {'content': io.BytesIO(b"success")}
        ]

        result = self.provider.download_file("test.txt", "test-container")

        self.assertEqual(result, b"success")
        self.assertEqual(self.mock_blob_service.get_blob_client.return_value.download_blob.call_count, 3)

    def test_abort_multipart_on_failure(self):
        """Test multipart upload abort on failure"""
        large_data = b"x" * (6 * 1024 * 1024)
        file_obj = io.BytesIO(large_data)

        self.mock_blob_service.get_blob_client.return_value.stage_block.side_effect = Exception("Upload failed")

        self.provider.upload_file(file_obj, "large.txt", "test-container")

        self.mock_blob_service.get_blob_client.return_value.abort_upload.assert_called_once()

class TestGCPStorageProvider(unittest.TestCase):
    """Test cases for GCP Storage provider"""

    def setUp(self):
        """Set up test environment"""
        self.mock_env = {
            'GOOGLE_APPLICATION_CREDENTIALS': 'test-credentials.json'
        }
        self.patcher = patch.dict('os.environ', self.mock_env)
        self.patcher.start()

        self.transfer_config = TransferConfig()
        self.provider = GCPStorageProvider(self.transfer_config)
        self.mock_client = Mock()
        self.provider.client = self.mock_client

    def tearDown(self):
        """Clean up test environment"""
        self.patcher.stop()

    def test_init_with_transfer_config(self):
        """Test initialization with transfer config"""
        provider = GCPStorageProvider(self.transfer_config)
        self.assertEqual(provider.transfer_config.multipart_threshold, 5 * 1024 * 1024)
        self.assertEqual(provider.transfer_config.multipart_chunksize, 1 * 1024 * 1024)

    def test_upload_small_file_bytes(self):
        """Test uploading small file with bytes"""
        data = b"test data"
        self.provider.upload_file(data, "test.txt", "test-bucket")
        self.mock_client.bucket.assert_called_once_with("test-bucket")
        self.mock_client.bucket.return_value.blob.assert_called_once_with("test.txt")
        self.mock_client.bucket.return_value.blob.return_value.upload_from_string.assert_called_once_with(data)

    def test_upload_small_file_stream(self):
        """Test uploading small file with file stream"""
        data = io.BytesIO(b"test data")
        self.provider.upload_file(data, "test.txt", "test-bucket")
        self.mock_client.bucket.assert_called_once_with("test-bucket")
        self.mock_client.bucket.return_value.blob.assert_called_once_with("test.txt")
        self.mock_client.bucket.return_value.blob.return_value.upload_from_file.assert_called_once_with(data)

    def test_upload_large_file_multipart(self):
        """Test multipart upload for large files"""
        # Create a large file that exceeds multipart threshold
        large_data = b"x" * (6 * 1024 * 1024)  # 6MB
        file_obj = io.BytesIO(large_data)

        # Mock multipart upload responses
        self.mock_client.bucket.return_value.blob.return_value.chunk_size = 1 * 1024 * 1024

        self.provider.upload_file(file_obj, "large.txt", "test-bucket")

        # Verify multipart upload was initiated
        self.mock_client.bucket.assert_called_once_with("test-bucket")

        # Verify parts were uploaded
        self.assertTrue(self.mock_client.bucket.return_value.blob.return_value.upload_from_file.called)

        # Verify multipart upload was completed
        self.mock_client.bucket.return_value.blob.return_value.upload_from_file.assert_called_once()

    def test_download_with_bandwidth_limit(self):
        """Test downloading with bandwidth throttling"""
        mock_response = {'content': io.BytesIO(b"test data")}
        self.mock_client.bucket.return_value.blob.return_value.download_as_bytes.return_value = mock_response

        result = self.provider.download_file("test.txt", "test-bucket")

        self.assertEqual(result, b"test data")
        self.mock_client.bucket.assert_called_once_with("test-bucket")
        self.mock_client.bucket.return_value.blob.assert_called_once_with("test.txt")
        self.mock_client.bucket.return_value.blob.return_value.download_as_bytes.assert_called_once()

    def test_retry_on_failure(self):
        """Test retry mechanism on failure"""
        self.mock_client.bucket.return_value.blob.return_value.download_as_bytes.side_effect = [
            Exception("Temporary failure"),
            Exception("Another failure"),
            {'content': io.BytesIO(b"success")}
        ]

        result = self.provider.download_file("test.txt", "test-bucket")

        self.assertEqual(result, b"success")
        self.assertEqual(self.mock_client.bucket.return_value.blob.return_value.download_as_bytes.call_count, 3)

    def test_abort_multipart_on_failure(self):
        """Test multipart upload abort on failure"""
        large_data = b"x" * (6 * 1024 * 1024)
        file_obj = io.BytesIO(large_data)

        self.mock_client.bucket.return_value.blob.return_value.upload_from_file.side_effect = Exception("Upload failed")

        self.provider.upload_file(file_obj, "large.txt", "test-bucket")

        self.mock_client.bucket.return_value.blob.return_value.delete_blob.assert_called_once()
