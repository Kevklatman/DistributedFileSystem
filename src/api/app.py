"""Main application entry point."""

import os
import sys
import logging
from quart import Quart
from quart_cors import cors
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
from src.api.routes.s3 import s3_api, S3ApiHandler
from src.api.routes.aws_s3_api import aws_s3_api, AWSS3ApiHandler
from src.api.routes.advanced_storage import advanced_storage
from src.infrastructure.manager import InfrastructureManager

# Configure logging
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
logger = logging.getLogger(__name__)

# Configure Quart app
app = Quart(__name__)
app = cors(app, allow_origin="*")

# Initialize infrastructure manager
try:
    infrastructure = InfrastructureManager()
    fs_manager = FileSystemManager(STORAGE_ROOT)
    
    # Initialize API handlers
    s3_handler = S3ApiHandler(fs_manager, infrastructure)
    aws_s3_handler = AWSS3ApiHandler(fs_manager, infrastructure)
except Exception as e:
    logger.error(f"Error initializing infrastructure: {str(e)}")
    raise

# Register blueprints
app.register_blueprint(s3_api, url_prefix='/s3')
app.register_blueprint(aws_s3_api, url_prefix='/aws-s3')
app.register_blueprint(advanced_storage, url_prefix='/storage')

# Health check endpoint
@app.route('/health')
async def health_check():
    """Health check endpoint."""
    return {'status': 'healthy'}

if __name__ == '__main__':
    # Ensure the data directory exists
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    
    # Run the application
    app.run(
        host=API_HOST,
        port=API_PORT,
        debug=DEBUG
    )
