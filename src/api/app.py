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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000", "http://localhost:5000", "http://localhost:5555"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"],
        "expose_headers": ["ETag", "x-amz-request-id", "x-amz-id-2"],
        "supports_credentials": True
    }
})

# Initialize Flask-RESTX
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
@app.route('/', methods=['GET'])
def index():
    try:
        if request.headers.get('Accept') == 'application/json':
            # API request for listing buckets
            storage = get_storage_backend(fs_manager)
            buckets, error = storage.list_buckets()
            if error:
                logger.error(f"Error listing buckets: {error}")
                return make_response({'error': str(error)}, 400)
            return make_response({'buckets': buckets}, 200)
        else:
            # Web UI request - serve the static index.html
            return send_from_directory('static', 'index.html')
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        return make_response({'error': str(e)}, 500)

# Serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# Decorate existing routes with API documentation
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
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)
