#!/usr/bin/env python3
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

def test_azure_connection():
    # Load environment variables
    load_dotenv()
    
    # Get connection string
    connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if not connect_str:
        print("Error: AZURE_STORAGE_CONNECTION_STRING not found in environment variables")
        return False
    
    try:
        # Create the BlobServiceClient object
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        
        # Create a unique container name
        container_name = "testcontainer"
        
        # Create the container
        try:
            container_client = blob_service_client.create_container(container_name)
            print(f"Created container: {container_name}")
        except Exception as e:
            if "ContainerAlreadyExists" in str(e):
                print(f"Container {container_name} already exists")
            else:
                raise e
        
        # Create a test blob
        blob_name = "test.txt"
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        # Upload some test data
        test_data = "Hello, Azure Storage!"
        blob_client.upload_blob(test_data, overwrite=True)
        print(f"Uploaded blob: {blob_name}")
        
        # Download the blob
        download_stream = blob_client.download_blob()
        downloaded_data = download_stream.readall().decode('utf-8')
        print(f"Downloaded blob content: {downloaded_data}")
        
        # Clean up
        blob_client.delete_blob()
        container_client = blob_service_client.get_container_client(container_name)
        container_client.delete_container()
        print("Cleaned up test resources")
        
        return True
        
    except Exception as e:
        print(f"Error testing Azure connection: {str(e)}")
        return False

if __name__ == "__main__":
    if test_azure_connection():
        print("\nAzure Storage connection test successful!")
    else:
        print("\nAzure Storage connection test failed!")
