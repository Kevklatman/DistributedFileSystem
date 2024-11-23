from flask import Flask, request, jsonify, Response, make_response, render_template, send_from_directory
from flask_cors import CORS
from flask_restx import Api, Resource, fields
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
import sys
import json

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.fs_manager import FileSystemManager
from core.config import API_HOST, API_PORT, DEBUG
from models.api_models import create_api_models
from services.api_metrics import get_policy_metrics, get_dashboard_metrics, metrics
from services.utils.serializers import JSONEncoder
from routes.resources import BucketList, BucketOperations, ObjectOperations
from storage.backends import get_storage_backend
from routes.s3 import s3_api, S3ApiHandler
from routes.aws_s3_api import aws_s3_api, AWSS3ApiHandler

# Configure Flask app
app = Flask(__name__,
           static_url_path='',
           static_folder='static')

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "http://localhost:5000", "http://localhost:8000"],
                            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                            "allow_headers": ["Content-Type", "Authorization"]}})

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize filesystem manager and storage backend
fs_manager = FileSystemManager()
storage_backend = get_storage_backend(fs_manager)

# Initialize S3-compatible API handler and register blueprint
s3_handler = S3ApiHandler(fs_manager)
app.register_blueprint(s3_api, url_prefix='/s3')

# Initialize AWS S3 API handler and register blueprint
aws_s3_handler = AWSS3ApiHandler(fs_manager)
app.register_blueprint(aws_s3_api, url_prefix='/aws-s3')

# Add request logging
@app.before_request
def log_request_info():
    logger.debug('Headers: %s', dict(request.headers))
    logger.debug('Body: %s', request.get_data())

@app.after_request
def after_request(response):
    logger.debug('Response Headers: %s', dict(response.headers))
    return response

# Handle favicon.ico requests
@app.route('/favicon.ico')
def favicon():
    return '', 204  # Return no content

# Initialize Flask-RESTX with Swagger UI
authorizations = {
    'apikey': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'X-Api-Key'
    }
}

api = Api(app, version='1.0',
          title='Distributed File System API',
          description='S3-compatible API for distributed file storage',
          doc='/docs')

# Define namespaces
s3_ns = api.namespace('',
                      description='S3-compatible operations',
                      path='/')

# Initialize API models
api_models = create_api_models(api)

# Register resources
s3_ns.add_resource(BucketList, '/buckets')
s3_ns.add_resource(BucketOperations, '/buckets/<string:bucket_name>')
s3_ns.add_resource(ObjectOperations, '/buckets/<string:bucket_name>/objects/<string:object_key>')

# Add CORS preflight handler
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin", "*"))
        response.headers.add("Access-Control-Allow-Methods", "DELETE, GET, POST, PUT, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token")
        response.headers.add("Access-Control-Expose-Headers", "ETag, x-amz-request-id, x-amz-id-2")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Access-Control-Max-Age", "3600")
        return response

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Error: {str(error)}")
    return jsonify({'error': str(error)}), 500

# Add back the index route
@app.route('/')
def index():
    """Serve the web UI"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory(app.static_folder, path)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'available',
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
    })

# Dashboard metrics endpoint
@app.route('/dashboard/metrics', methods=['GET'])
def get_dashboard_metrics():
    """Get all dashboard metrics"""
    return metrics.get_dashboard_metrics()

# Metrics endpoint
@app.route('/metrics')
def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return metrics.metrics()

# Serve Swagger UI files
@app.route('/swaggerui/<path:path>')
def swagger_ui(path):
    return send_from_directory('static/swaggerui', path)

# Set custom JSON encoder
app.json_encoder = JSONEncoder

if __name__ == '__main__':
    # Ensure the buckets directory exists
    os.makedirs('buckets', exist_ok=True)
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)
