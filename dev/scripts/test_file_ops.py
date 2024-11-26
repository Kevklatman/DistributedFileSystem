"""Test script for distributed file operations."""

import requests
import json
import os
from pathlib import Path

# Set environment variables
os.environ["STORAGE_ROOT"] = (
    "/Users/kevinklatman/Development/Code/DistributedFileSystem/data/dfs"
)
os.environ["NODE_ID"] = "test-node-1"
os.environ["CLOUD_PROVIDER_TYPE"] = "aws"

# API endpoints
API_BASE = "http://localhost:8080"  # Flask API
NODE_BASE = "http://localhost:8080"  # Storage Node


def test_file_operations():
    """Test basic file operations through the API."""
    print("Testing file operations...")

    # Create a test bucket
    bucket_name = "test-bucket"
    bucket_url = f"{API_BASE}/s3/buckets/{bucket_name}"
    print(f"\n1. Creating bucket: {bucket_name}")
    response = requests.put(bucket_url)
    print(f"Response: {response.status_code}")
    if response.status_code >= 400:
        print(f"Error: {response.text}")

    # Create a test file
    test_content = b"Hello, Distributed File System!"
    object_key = "test-file.txt"
    object_url = f"{API_BASE}/s3/buckets/{bucket_name}/objects/{object_key}"

    print(f"\n2. Uploading file: {object_key}")
    headers = {"Content-Type": "text/plain", "x-amz-storage-class": "STANDARD"}
    response = requests.put(object_url, data=test_content, headers=headers)
    print(f"Response: {response.status_code}")
    if response.status_code == 200:
        print(f"ETag: {response.headers.get('ETag', 'N/A')}")
    else:
        print(f"Error: {response.text}")

    # Read the file back
    print(f"\n3. Reading file: {object_key}")
    response = requests.get(object_url)
    print(f"Response: {response.status_code}")
    if response.status_code == 200:
        print(f"Content: {response.content.decode()}")
        print(f"ETag: {response.headers.get('ETag', 'N/A')}")
    else:
        print(f"Error: {response.text}")

    # List bucket contents
    print(f"\n4. Listing bucket contents")
    response = requests.get(bucket_url)
    print(f"Response: {response.status_code}")
    if response.status_code == 200:
        print(f"Objects: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Error: {response.text}")

    # Delete the file
    print(f"\n5. Deleting file: {object_key}")
    response = requests.delete(object_url)
    print(f"Response: {response.status_code}")
    if response.status_code >= 400:
        print(f"Error: {response.text}")

    # Delete the bucket
    print(f"\n6. Deleting bucket: {bucket_name}")
    response = requests.delete(bucket_url)
    print(f"Response: {response.status_code}")
    if response.status_code >= 400:
        print(f"Error: {response.text}")

    # Check storage node metrics
    print(f"\n7. Checking storage node metrics")
    response = requests.get(f"{NODE_BASE}/metrics")
    if response.status_code == 200:
        metrics = response.text.split("\n")
        print("\nRelevant metrics:")
        for metric in metrics:
            if any(
                key in metric for key in ["file_operations", "storage_usage", "cache"]
            ):
                print(metric)
    else:
        print(f"Error getting metrics: {response.text}")


if __name__ == "__main__":
    test_file_operations()
