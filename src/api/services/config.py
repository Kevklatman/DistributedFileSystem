import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Environment can be 'local' or 'aws'
STORAGE_ENV = os.getenv('STORAGE_ENV', 'local')

# API Configuration
API_HOST = os.getenv('API_HOST', '0.0.0.0')  # Change to 0.0.0.0 to allow external connections
API_PORT = int(os.getenv('API_PORT', 8001))  # Change default port to 8001
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# AWS Configuration
AWS_CONFIG = {
    'access_key': os.environ.get('AWS_ACCESS_KEY'),
    'secret_key': os.environ.get('AWS_SECRET_KEY'),
    'session_token': os.environ.get('AWS_SESSION_TOKEN'),  # Added STS session token
    'region': os.environ.get('AWS_REGION', 'us-east-2'),  # Updated default region
    'endpoint': os.environ.get('AWS_ENDPOINT_URL', None)
}

# Storage configuration
STORAGE_CONFIG = {
    'local': {
        'storage_dir': os.getenv('LOCAL_STORAGE_DIR', './storage')
    },
    'aws': AWS_CONFIG
}

# Get current storage configuration
current_config = STORAGE_CONFIG.get(STORAGE_ENV, STORAGE_CONFIG['local'])
