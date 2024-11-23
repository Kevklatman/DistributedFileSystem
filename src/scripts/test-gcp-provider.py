#!/usr/bin/env python3
import os
import sys

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dotenv import load_dotenv
from storage.infrastructure.providers import get_cloud_provider

def test_gcp_operations():
    """Test all GCP storage operations."""
    # Load environment variables
    load_dotenv()

    # Initialize GCP provider
    gcp = get_cloud_provider('gcp')

    # Test bucket name
    bucket_name = "kevinklatman"  # Your bucket name
    test_file_key = "test/example.txt"
    test_content = b"Hello from Distributed File System!"

    print("\n=== Testing GCP Storage Operations ===")

    # Test upload
    print("\n1. Testing file upload...")
    upload_success = gcp.upload_file(test_content, test_file_key, bucket_name)
    if upload_success:
        print("✅ Upload successful")
    else:
        print("❌ Upload failed")
        return

    # Test download
    print("\n2. Testing file download...")
    downloaded_content = gcp.download_file(test_file_key, bucket_name)
    if downloaded_content == test_content:
        print("✅ Download successful")
        print(f"Downloaded content: {downloaded_content.decode()}")
    else:
        print("❌ Download failed or content mismatch")
        return

    # Test list objects
    print("\n3. Testing list objects...")
    objects = gcp.list_objects(bucket_name, prefix="test/")
    if objects:
        print("✅ List objects successful")
        print("Objects found:")
        for obj in objects:
            print(f"  - {obj['Key']} (Size: {obj['Size']} bytes)")
    else:
        print("❌ List objects failed or no objects found")

    # Test delete
    print("\n4. Testing file deletion...")
    delete_success = gcp.delete_object(test_file_key, bucket_name)
    if delete_success:
        print("✅ Delete successful")
    else:
        print("❌ Delete failed")

    # Verify deletion
    print("\n5. Verifying deletion...")
    deleted_content = gcp.download_file(test_file_key, bucket_name)
    if deleted_content is None:
        print("✅ File was properly deleted")
    else:
        print("❌ File still exists")

    print("\n=== GCP Storage Operations Test Complete ===")

if __name__ == "__main__":
    test_gcp_operations()
