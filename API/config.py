import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Environment can be 'local' or 'aws'
STORAGE_ENV = os.getenv('STORAGE_ENV', 'local')

# API Configuration
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', 5555))
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# Storage configuration
STORAGE_CONFIG = {
    'local': {
        'endpoint': f'http://{API_HOST}:{API_PORT}',
        'access_key': 'dev',
        'secret_key': 'dev',
    },
    'aws': {
        'endpoint': 'https://s3.amazonaws.com',
        'access_key': os.getenv('AWS_ACCESS_KEY'),
        'secret_key': os.getenv('AWS_SECRET_KEY'),
        'region': os.getenv('AWS_REGION', 'us-east-1'),
    }
}

# Get current storage configuration
current_config = STORAGE_CONFIG[STORAGE_ENV]

# Validate AWS credentials if using AWS
if STORAGE_ENV == 'aws':
    if not all([current_config['access_key'], current_config['secret_key']]):
        raise ValueError(
            'AWS credentials not found. Please set AWS_ACCESS_KEY and AWS_SECRET_KEY '
            'environment variables in your .env file when using AWS storage.'
        )
