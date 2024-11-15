from flask import Flask
from s3_api import S3ApiHandler
from mock_fs_manager import FileSystemManager

app = Flask(__name__)
fs_manager = FileSystemManager()
s3_handler = S3ApiHandler(fs_manager)

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
    from config import API_HOST, API_PORT, DEBUG
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)
