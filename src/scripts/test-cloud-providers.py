#!/usr/bin/env python3
import os
import sys
import uuid
import time
from dotenv import load_dotenv

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Cloud provider imports
from google.cloud import storage as gcp_storage
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from storage.infrastructure.providers import get_cloud_provider

def test_gcp(test_bucket="kevinklatman"):
    """Test GCP storage connection and operations."""
    print("\n=== Testing Google Cloud Storage ===")

    try:
        # Basic connection test
        storage_client = gcp_storage.Client()
        bucket = storage_client.bucket(test_bucket)

        # Test file operations
        test_file = "test.txt"
        test_content = "Hello from DFS!"

        print("1. Testing upload...")
        blob = bucket.blob(test_file)
        blob.upload_from_string(test_content)
        print("✅ Upload successful")

        print("\n2. Testing download...")
        content = blob.download_as_string().decode('utf-8')
        assert content == test_content
        print("✅ Download successful")

        print("\n3. Testing deletion...")
        blob.delete()
        print("✅ Cleanup successful")

        # Test provider implementation
        print("\n4. Testing provider implementation...")
        gcp = get_cloud_provider('gcp')
        assert gcp.upload_file(test_content.encode(), "test/example.txt", test_bucket)
        assert gcp.delete_file("test/example.txt", test_bucket)
        print("✅ Provider implementation successful")

        return True

    except Exception as e:
        print(f"❌ GCP test failed: {str(e)}")
        return False

def test_azure():
    """Test Azure storage connection and operations."""
    print("\n=== Testing Azure Storage ===")

    # Get connection string
    connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if not connect_str:
        print("❌ Error: AZURE_STORAGE_CONNECTION_STRING not found")
        return False

    try:
        # Create the BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)

        # Create test container
        container_name = f"testcontainer-{str(uuid.uuid4())}"
        print(f"1. Creating test container: {container_name}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                container_client = blob_service_client.create_container(container_name)
                break
            except ResourceExistsError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)
        print("✅ Container created")

        # Test blob operations
        test_file = "test.txt"
        test_content = "Hello from DFS!"

        print("\n2. Testing upload...")
        blob_client = container_client.get_blob_client(test_file)
        blob_client.upload_blob(test_content)
        print("✅ Upload successful")

        print("\n3. Testing download...")
        download_stream = blob_client.download_blob()
        content = download_stream.readall().decode('utf-8')
        assert content == test_content
        print("✅ Download successful")

        print("\n4. Cleaning up...")
        container_client.delete_container()
        print("✅ Cleanup successful")

        return True

    except Exception as e:
        print(f"❌ Azure test failed: {str(e)}")
        return False

def main():
    """Run all cloud provider tests."""
    load_dotenv()

    results = {
        "GCP": test_gcp(),
        "Azure": test_azure()
    }

    print("\n=== Test Results ===")
    for provider, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{provider}: {status}")

    # Exit with appropriate status code
    if all(results.values()):
        print("\nAll cloud provider tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed. Check the logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
