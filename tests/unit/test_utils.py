"""Test utilities and mock classes."""
from unittest.mock import create_autospec
from src.api.storage.cloud.providers import CloudStorageProvider

def create_mock_provider(success=True, latency=50, offline_mode=False):
    """Create a mock cloud provider with configurable behavior."""
    mock = create_autospec(CloudStorageProvider, instance=True)
    mock.success = success
    mock.latency = latency
    mock.offline_mode = offline_mode

    # Configure default return values
    mock.upload_file.return_value = success
    mock.download_file.return_value = b"test_data" if success else None
    mock.delete_file.return_value = success
    mock.create_bucket.return_value = success
    mock.list_objects.return_value = [{"Key": "test.txt"}] if success else []

    if offline_mode:
        mock.upload_file.side_effect = Exception("Offline mode: Cannot upload file")
        mock.download_file.side_effect = Exception("Offline mode: Cannot download file")
        mock.delete_file.side_effect = Exception("Offline mode: Cannot delete file")
        mock.create_bucket.side_effect = Exception("Offline mode: Cannot create bucket")
        mock.list_objects.side_effect = Exception("Offline mode: Cannot list objects")

    return mock
