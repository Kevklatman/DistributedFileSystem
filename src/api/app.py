"""Main application entry point."""

import os
import sys
import logging
from flask import Flask
from flask_cors import CORS
from src.api.services.fs_manager import FileSystemManager
from src.config.base_config import (
    API_HOST,
    API_PORT,
    DEBUG,
    STORAGE_ROOT,
    NODE_ID,
    CLOUD_PROVIDER_TYPE,
    MAX_WORKERS,
    CHUNK_SIZE,
    CACHE_ENABLED,
    REPLICATION_FACTOR
)

from src.config.infrastructure_config import infrastructure_config
from src.api.routes.s3 import s3_api
from src.api.routes.aws_s3_api import aws_s3_api
from src.api.routes.advanced_storage import advanced_storage
from src.infrastructure.manager import InfrastructureManager

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize infrastructure manager
try:
    infrastructure = InfrastructureManager()
    fs_manager = FileSystemManager(
        storage_root=STORAGE_ROOT,
        node_id=NODE_ID,
        cloud_provider=CLOUD_PROVIDER_TYPE,
        max_workers=MAX_WORKERS,
        chunk_size=CHUNK_SIZE,
        cache_enabled=CACHE_ENABLED,
        replication_factor=REPLICATION_FACTOR
    )
except Exception as e:
    logger.error(f"Failed to initialize infrastructure: {str(e)}")
    sys.exit(1)

# Register blueprints
app.register_blueprint(s3_api)
app.register_blueprint(aws_s3_api)
app.register_blueprint(advanced_storage)

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return {'status': 'healthy'}

if __name__ == '__main__':
    # Ensure the data directory exists
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    
    # Run the Flask application
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)
