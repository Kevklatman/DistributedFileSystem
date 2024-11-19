"""Test configuration and utilities."""
import os
from dotenv import load_dotenv

# Load test environment variables
load_dotenv()

# Test configuration
TEST_CONFIG = {
    'aws': {
        'bucket': 'test-dfs-bucket',
        'region': os.getenv('AWS_REGION', 'us-east-2'),
        'access_key': os.getenv('AWS_ACCESS_KEY'),
        'secret_key': os.getenv('AWS_SECRET_KEY'),
    },
    'azure': {
        'container': 'test-dfs-container',
        'connection_string': os.getenv('AZURE_STORAGE_CONNECTION_STRING'),
    },
    'gcp': {
        'bucket': 'test-dfs-bucket',
        'credentials_path': os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
    }
}

# Test data
TEST_DATA = {
    'small_file': b'Hello, World!',
    'medium_file': b'x' * 1024 * 1024,  # 1MB
    'large_file': b'x' * 1024 * 1024 * 10,  # 10MB
}
