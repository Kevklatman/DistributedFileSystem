from flask import Flask, request, jsonify, Response, make_response, render_template, send_from_directory
from flask_cors import CORS
from flask_restx import Api, Resource, fields
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
from storage_backend import get_storage_backend
from s3_api import S3ApiHandler
from mock_fs_manager import FileSystemManager

# Configure Flask app
app = Flask(__name__,
           static_url_path='',
           static_folder='static')

# Enable CORS
CORS(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
          doc='/docs',
          prefix='/api',  
          authorizations=authorizations)

# Define namespaces
s3_ns = api.namespace('s3',
                      description='S3-compatible operations',
                      path='/')

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

@app.before_request
def log_request_info():
    logger.debug('Headers: %s', request.headers)
    logger.debug('Body: %s', request.get_data())

@app.after_request
def log_response_info(response):
    logger.debug('Response: %s', response.get_data())
    return response

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Error: {str(error)}")
    return jsonify({'error': str(error)}), 500

fs_manager = FileSystemManager()
s3_handler = S3ApiHandler(fs_manager)

# Add back the index route
@app.route('/', methods=['GET', 'OPTIONS'])
def index():
    try:
        if request.headers.get('Accept') == 'application/json':
            # API request for listing buckets
            storage = get_storage_backend(fs_manager)
            logger.debug("Using storage backend: %s", storage.__class__.__name__)

            buckets, error = storage.list_buckets()

            if error:
                logger.error("Error listing buckets: %s", error)
                return jsonify({'error': str(error)}), 500

            # Ensure buckets is a list
            if buckets is None:
                buckets = []
            elif not isinstance(buckets, list):
                buckets = list(buckets)

            logger.debug("Found buckets: %s", buckets)
            return jsonify({'buckets': buckets}), 200
        else:
            # Web UI request - serve the static index.html
            return send_from_directory('static', 'index.html')
    except Exception as e:
        logger.error("Error in index route: %s", str(e), exc_info=True)
        return jsonify({'error': str(e)}), 500

# Serve static files
@app.route('/<path:path>')
def serve_static(path):
    try:
        if path.startswith('swaggerui/'):
            return send_from_directory('static/swaggerui', path[10:])
        return send_from_directory('static', path)
    except Exception as e:
        logger.error(f"Error serving static file {path}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Serve Swagger UI files
@app.route('/swaggerui/<path:path>')
def swagger_ui(path):
    return send_from_directory('static/swaggerui', path)

# Decorate existing routes with API documentation
@s3_ns.route('/buckets')
class BucketList(Resource):
    @s3_ns.doc('list_buckets')
    @s3_ns.response(200, 'Success')
    def get(self):
        """List all buckets"""
        return s3_handler.list_buckets()

@s3_ns.route('/buckets/<string:bucket_name>')
@s3_ns.param('bucket_name', 'The bucket name')
class BucketOperations(Resource):
    @s3_ns.doc('create_bucket')
    @s3_ns.response(200, 'Success')
    @s3_ns.response(400, 'Bad Request', error_model)
    def put(self, bucket_name):
        """Create a new bucket"""
        return s3_handler.create_bucket(bucket_name)

    @s3_ns.doc('delete_bucket')
    @s3_ns.response(204, 'Bucket deleted')
    @s3_ns.response(404, 'Bucket not found', error_model)
    def delete(self, bucket_name):
        """Delete a bucket"""
        return s3_handler.delete_bucket(bucket_name)

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

if __name__ == '__main__':
    from config import API_HOST, API_PORT, DEBUG
    # Ensure the buckets directory exists
    os.makedirs('buckets', exist_ok=True)

    # Start the Flask app
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)
