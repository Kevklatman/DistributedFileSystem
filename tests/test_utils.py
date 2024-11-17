"""Test utilities and mock classes."""
from unittest.mock import create_autospec
from src.api.storage.cloud.providers import CloudStorageProvider

def create_mock_provider(success=True, latency=50):
    """Create a mock cloud provider with configurable behavior."""
    mock = create_autospec(CloudStorageProvider, instance=True)
    mock.success = success
    mock.latency = latency
    
    # Configure default return values
    mock.upload_file.return_value = success
    mock.download_file.return_value = b"test_data" if success else None
    mock.delete_file.return_value = success
    mock.create_bucket.return_value = success
    mock.list_objects.return_value = [{"Key": "test.txt"}] if success else []
    
    return mock
