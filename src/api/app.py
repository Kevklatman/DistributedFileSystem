from quart import Quart, request, jsonify, Response, make_response, render_template, send_from_directory
from quart_cors import cors
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import sys
import json
import atexit
import asyncio
import quart.json.provider
import logging

# Add the src directory to Python path
src_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(src_path)

# Import local modules
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

# Configure Quart app
app = Quart(__name__,
           static_url_path='',
           static_folder='static')
app = cors(app, allow_origin="*")

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize infrastructure manager
try:
    infrastructure = InfrastructureManager()
    infrastructure.start()
except Exception as e:
    logger.error(f"Failed to start infrastructure: {str(e)}")
    raise

# System status endpoint
@app.route('/system/status')
async def system_status():
    """Get current system status"""
    return jsonify(infrastructure.get_system_status())

# Add request logging
@app.before_request
async def log_request_info():
    logger.debug('Headers: %s', dict(request.headers))
    body = await request.get_data()
    logger.debug('Body: %s', body)

@app.after_request
async def after_request(response):
    logger.debug('Response Headers: %s', dict(response.headers))
    return response

# Handle favicon.ico requests
@app.route('/favicon.ico')
async def favicon():
    return '', 204

# Add CORS preflight handler
@app.before_request
async def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin", "*"))
        response.headers.add("Access-Control-Allow-Methods", "DELETE, GET, POST, PUT, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token")
        response.headers.add("Access-Control-Expose-Headers", "*")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Access-Control-Max-Age", "3600")
        return response

@app.errorhandler(Exception)
async def handle_error(error):
    logger.error(f"Error: {str(error)}")
    return jsonify({'error': str(error)}), 500

# Add back the index route
@app.route('/')
async def index():
    """Serve the web UI"""
    return await send_from_directory(app.static_folder, 'index.html')

@app.route('/static/<path:path>')
async def serve_static(path):
    """Serve static files"""
    return await send_from_directory(app.static_folder, path)

# Health check endpoint
@app.route('/health', methods=['GET'])
async def health_check():
    return jsonify({
        'status': 'available',
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
    })

# Register blueprints
app.register_blueprint(s3_api, url_prefix='/s3')
app.register_blueprint(aws_s3_api, url_prefix='/aws-s3')
app.register_blueprint(advanced_storage, url_prefix='/storage')

# Set custom JSON encoder
class CustomJSONProvider(quart.json.provider.DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        return super().default(obj)

app.json = CustomJSONProvider(app)

if __name__ == '__main__':
    # Ensure the data directory exists
    os.makedirs(os.getenv('STORAGE_ROOT', '/data/dfs'), exist_ok=True)
    
    # Run the Quart app with hypercorn
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)
