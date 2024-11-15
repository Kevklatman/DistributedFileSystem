from flask import Flask, request, jsonify
import os
from s3_api import S3ApiHandler
from mock_fs_manager import FileSystemManager  # Using mock implementation temporarily

app = Flask(__name__)
fs_manager = FileSystemManager()
s3_handler = S3ApiHandler(fs_manager)

# Original REST API endpoints
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    filename = file.filename
    content = file.read()
    success = fs_manager.writeFile(filename, content)
    if success:
        return jsonify({"message": "File uploaded successfully"}), 200
    else:
        return jsonify({"message": "Failed to upload file"}), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    content = fs_manager.readFile(filename)
    if content:
        return content, 200
    else:
        return jsonify({"message": "File not found"}), 404

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    success = fs_manager.deleteFile(filename)
    if success:
        return jsonify({"message": "File deleted successfully"}), 200
    else:
        return jsonify({"message": "Failed to delete file"}), 500

@app.route('/list', methods=['GET'])
def list_files():
    files = fs_manager.listAllFiles()
    return jsonify(files), 200

# S3-compatible API endpoints
@app.route('/', methods=['GET'])
def list_buckets():
    return s3_handler.list_buckets()

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
    return s3_handler.delete_object(bucket_name, object_key)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
