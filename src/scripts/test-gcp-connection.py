#!/usr/bin/env python3
import os
from google.cloud import storage
from dotenv import load_dotenv

def test_gcp_connection():
    # Load environment variables
    load_dotenv()
    
    try:
        # Create a client
        storage_client = storage.Client()
        
        # Use a specific bucket
        bucket_name = "kevinklatman"  # Your bucket name
        print(f"\nTesting with bucket: {bucket_name}")
        
        try:
            bucket = storage_client.bucket(bucket_name)
            
            # Upload a test file
            blob = bucket.blob("test.txt")
            blob.upload_from_string("Hello, Google Cloud Storage!")
            print("Test file uploaded successfully")
            
            # Download the test file
            content = blob.download_as_string().decode('utf-8')
            print(f"Downloaded content: {content}")
            
            # Clean up
            print("Cleaning up resources...")
            blob.delete()
            print("Test file deleted")
            
            return True
            
        except Exception as e:
            print(f"Error during bucket operations: {str(e)}")
            return False
            
    except Exception as e:
        print(f"Error testing GCP connection: {str(e)}")
        return False

if __name__ == "__main__":
    if test_gcp_connection():
        print("\nGoogle Cloud Storage connection test successful!")
    else:
        print("\nGoogle Cloud Storage connection test failed!")
