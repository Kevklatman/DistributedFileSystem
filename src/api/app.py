from flask import Flask, request, jsonify, Response, make_response, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
from storage_backend import get_storage_backend
from s3_api import S3ApiHandler
from mock_fs_manager import FileSystemManager

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000", "http://localhost:5173"],  # Add both development server URLs
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept", "Authorization"],
        "expose_headers": ["ETag"],
        "supports_credentials": True
    }
})

# Add CORS preflight handler
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin", "*"))
        response.headers.add("Access-Control-Allow-Methods", "DELETE, GET, POST, PUT, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization")
        response.headers.add("Access-Control-Max-Age", "3600")
        return response

fs_manager = FileSystemManager()
s3_handler = S3ApiHandler(fs_manager)

@app.route('/', methods=['GET'])
def index():
    if request.headers.get('Accept') == 'application/json':
        # API request for listing buckets
        storage = get_storage_backend(fs_manager)
        buckets, error = storage.list_buckets()
        if error:
            return make_response({'error': error}, 400)
        return make_response({'buckets': buckets}, 200)
    else:
        # Web UI request
        return render_template('index.html')

# Serve static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# S3-compatible API endpoints
@app.route('/<bucket_name>', methods=['PUT'])
def create_bucket(bucket_name):
    return s3_handler.create_bucket(bucket_name)

@app.route('/<bucket_name>', methods=['DELETE'])
def delete_bucket(bucket_name):
    return s3_handler.delete_bucket(bucket_name)

@app.route('/<bucket_name>', methods=['GET'])
def list_objects(bucket_name):
    return s3_handler.list_objects(bucket_name)

@app.route('/<bucket_name>/<object_key>', methods=['PUT'])
def put_object(bucket_name, object_key):
    return s3_handler.put_object(bucket_name, object_key)

@app.route('/<bucket_name>/<object_key>', methods=['GET'])
def get_object(bucket_name, object_key):
    return s3_handler.get_object(bucket_name, object_key)

@app.route('/<bucket_name>/<object_key>', methods=['DELETE'])
def delete_object(bucket_name, object_key):
    try:
        response = s3_handler.delete_object(bucket_name, object_key)
        return response
    except Exception as e:
        return make_response({'error': str(e)}, 400)

if __name__ == '__main__':
    from config import API_HOST, API_PORT, DEBUG
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)
