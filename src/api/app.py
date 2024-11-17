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

from storage_backend import get_storage_backend
from s3_api import S3ApiHandler
from mock_fs_manager import FileSystemManager
from config import API_HOST, API_PORT, DEBUG

# Configure Flask app
app = Flask(__name__,
           static_url_path='',
           static_folder='static')

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "http://localhost:5000"]}})

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add request logging
@app.before_request
def log_request_info():
    logger.debug('Headers: %s', dict(request.headers))
    logger.debug('Body: %s', request.get_data())

@app.after_request
def after_request(response):
    logger.debug('Response Headers: %s', dict(response.headers))
    return response

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
          doc='/api/v1/docs',
          prefix='/api/v1')

# Define namespaces
s3_ns = api.namespace('s3',
                      description='S3-compatible operations')

# Define models for request/response documentation
bucket_model = api.model('Bucket', {
    'Name': fields.String(required=True, description='Name of the bucket'),
    'CreationDate': fields.DateTime(description='When the bucket was created')
})

object_model = api.model('Object', {
    'Key': fields.String(required=True, description='Object key/path'),
    'Size': fields.Integer(description='Size of object in bytes'),
    'LastModified': fields.DateTime(description='Last modification timestamp')
})

error_model = api.model('Error', {
    'Code': fields.String(required=True, description='Error code'),
    'Message': fields.String(required=True, description='Error message')
})

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

fs_manager = FileSystemManager()
s3_handler = S3ApiHandler(fs_manager)

# Add back the index route
@app.route('/')
def index():
    """Serve the web UI or list buckets based on Accept header"""
    accept_header = request.headers.get('Accept', '')
    
    # If client accepts JSON, return bucket list
    if 'application/json' in accept_header:
        try:
            storage = get_storage_backend(fs_manager)
            logger.debug("Using storage backend: %s", storage.__class__.__name__)

            buckets, error = storage.list_buckets()

            if error:
                logger.error("Error listing buckets: %s", error)
                return jsonify({'error': str(error)}), 500

            # Ensure buckets is a list and contains valid data
            if buckets is None:
                buckets = []
            elif not isinstance(buckets, list):
                buckets = list(buckets)

            # Convert bucket objects to dictionaries
            bucket_list = []
            for bucket in buckets:
                if isinstance(bucket, dict):
                    bucket_list.append(bucket)
                else:
                    # Handle case where bucket might be a string or other object
                    bucket_list.append({'Name': str(bucket)})

            logger.debug("Found buckets: %s", bucket_list)
            return jsonify({'buckets': bucket_list}), 200
        except Exception as e:
            logger.error("Unexpected error listing buckets: %s", str(e))
            return jsonify({'error': 'Internal server error'}), 500
    
    # Otherwise serve the web UI
    return send_from_directory('static', 'index.html')

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)

app.json_encoder = JSONEncoder

# Health check endpoint
@app.route('/api/v1/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'available',
        'timestamp': datetime.datetime.now().isoformat()
    })

# Decorate existing routes with API documentation
@s3_ns.route('/buckets')
class BucketList(Resource):
    @s3_ns.doc('list_buckets')
    @s3_ns.response(200, 'Success')
    def get(self):
        """List all buckets"""
        try:
            storage = get_storage_backend(fs_manager)
            logger.debug("Using storage backend: %s", storage.__class__.__name__)

            buckets, error = storage.list_buckets()

            if error:
                logger.error("Error listing buckets: %s", error)
                return {'error': str(error)}, 500

            # Ensure buckets is a list and contains valid data
            if buckets is None:
                buckets = []
            elif not isinstance(buckets, list):
                buckets = list(buckets)

            # Convert bucket objects to dictionaries
            bucket_list = []
            for bucket in buckets:
                if isinstance(bucket, dict):
                    # Convert any datetime objects to ISO format strings
                    bucket_dict = {}
                    for key, value in bucket.items():
                        if isinstance(value, datetime.datetime):
                            bucket_dict[key] = value.isoformat()
                        else:
                            bucket_dict[key] = value
                    bucket_list.append(bucket_dict)
                else:
                    # Handle case where bucket might be a string or other object
                    bucket_list.append({'Name': str(bucket)})

            logger.debug("Found buckets: %s", bucket_list)
            return bucket_list, 200
        except Exception as e:
            logger.error("Unexpected error listing buckets: %s", str(e))
            return {'error': 'Internal server error'}, 500

@s3_ns.route('/buckets/<string:bucket_name>')
@s3_ns.param('bucket_name', 'The bucket name')
class BucketOperations(Resource):
    @s3_ns.doc('create_bucket')
    @s3_ns.response(200, 'Success')
    @s3_ns.response(400, 'Bad Request', error_model)
    def put(self, bucket_name):
        """Create a new bucket"""
        storage = get_storage_backend(fs_manager)
        result, error = storage.create_bucket(bucket_name)
        if error:
            return {'error': str(error)}, 400
        return {'message': 'Bucket created successfully'}, 200

    @s3_ns.doc('delete_bucket')
    @s3_ns.response(204, 'Bucket deleted')
    @s3_ns.response(404, 'Bucket not found', error_model)
    def delete(self, bucket_name):
        """Delete a bucket"""
        storage = get_storage_backend(fs_manager)
        result, error = storage.delete_bucket(bucket_name)
        if error:
            return {'error': str(error)}, 404
        return '', 204

@s3_ns.route('/buckets/<string:bucket_name>/objects')
@s3_ns.param('bucket_name', 'The bucket name')
class ObjectList(Resource):
    @s3_ns.doc('list_objects')
    @s3_ns.response(200, 'Success', [object_model])
    @s3_ns.response(404, 'Bucket not found', error_model)
    def get(self, bucket_name):
        """List objects in a bucket"""
        return s3_handler.list_objects(bucket_name)

@s3_ns.route('/buckets/<string:bucket_name>/objects/<path:object_key>')
@s3_ns.param('bucket_name', 'The bucket name')
@s3_ns.param('object_key', 'The object key/path')
class ObjectOperations(Resource):
    @s3_ns.doc('get_object')
    @s3_ns.response(200, 'Success')
    @s3_ns.response(404, 'Object not found', error_model)
    def get(self, bucket_name, object_key):
        """Get an object"""
        return s3_handler.get_object(bucket_name, object_key)

    @s3_ns.doc('put_object')
    @s3_ns.response(200, 'Success')
    @s3_ns.response(400, 'Bad Request', error_model)
    def put(self, bucket_name, object_key):
        """Upload an object"""
        return s3_handler.put_object(bucket_name, object_key)

    @s3_ns.doc('delete_object')
    @s3_ns.response(204, 'Object deleted')
    @s3_ns.response(404, 'Object not found', error_model)
    def delete(self, bucket_name, object_key):
        """Delete an object"""
        return s3_handler.delete_object(bucket_name, object_key)

@s3_ns.route('/buckets/<string:bucket_name>/versioning')
@s3_ns.param('bucket_name', 'The bucket name')
class VersioningOperations(Resource):
    @s3_ns.doc('get_versioning_status')
    @s3_ns.response(200, 'Success')
    @s3_ns.response(404, 'Bucket not found', error_model)
    def get(self, bucket_name):
        """Get versioning status"""
        return s3_handler.get_versioning_status(bucket_name)

    @s3_ns.doc('set_versioning_status')
    @s3_ns.response(200, 'Success')
    @s3_ns.response(400, 'Bad Request', error_model)
    def put(self, bucket_name):
        """Set versioning status"""
        data = request.get_json()
        if data is None:
            return make_response({'error': 'Missing request body'}, 400)

        if 'VersioningEnabled' not in data:
            return make_response({'error': 'Missing VersioningEnabled field'}, 400)

        if data['VersioningEnabled']:
            return s3_handler.enable_versioning(bucket_name)
        else:
            return s3_handler.disable_versioning(bucket_name)

# Serve Swagger UI files
@app.route('/swaggerui/<path:path>')
def swagger_ui(path):
    return send_from_directory('static/swaggerui', path)

if __name__ == '__main__':
    # Ensure the buckets directory exists
    os.makedirs('buckets', exist_ok=True)
    
    print(f"Starting server on {API_HOST}:{API_PORT}")
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)
