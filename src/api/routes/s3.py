"""S3-compatible API routes

This module implements a simplified S3-compatible API that provides basic object storage
functionality without the full complexity of AWS S3.
"""
from flask import request, jsonify, Response, make_response, Blueprint
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
from ..core.storage_backend import get_storage_backend
from ..core.fs_manager import FileSystemManager

logger = logging.getLogger(__name__)

# Create Blueprint for S3-compatible API routes
s3_api = Blueprint('s3_api', __name__)

class S3ApiHandler:
    def __init__(self, fs_manager):
        self.storage = get_storage_backend(fs_manager)
        self.register_routes()

    def register_routes(self):
        """Register basic S3-compatible routes"""
        # Basic bucket operations
        s3_api.add_url_rule('/buckets', 'list_buckets', self.list_buckets, methods=['GET'])
        s3_api.add_url_rule('/<bucket>', 'create_bucket', self.create_bucket, methods=['PUT'])
        s3_api.add_url_rule('/<bucket>', 'delete_bucket', self.delete_bucket, methods=['DELETE'])
        s3_api.add_url_rule('/<bucket>', 'list_objects', self.list_objects, methods=['GET'])

        # Basic object operations
        s3_api.add_url_rule('/<bucket>/<key>', 'put_object', self.put_object, methods=['PUT'])
        s3_api.add_url_rule('/<bucket>/<key>', 'get_object', self.get_object, methods=['GET'])
        s3_api.add_url_rule('/<bucket>/<key>', 'delete_object', self.delete_object, methods=['DELETE'])

    def list_buckets(self):
        """List all buckets"""
        try:
            buckets = self.storage.list_buckets()
            response = {
                'Buckets': [{'Name': bucket} for bucket in buckets],
                'Owner': {'ID': 'dfs-owner'}
            }
            return make_response(xmltodict.unparse({'ListAllMyBucketsResult': response}), 200)
        except Exception as e:
            logger.error(f"Error listing buckets: {str(e)}")
            return make_response(xmltodict.unparse({'Error': {'Message': str(e)}}), 500)

    def create_bucket(self, bucket):
        """Create a new bucket"""
        try:
            self.storage.create_bucket(bucket)
            return make_response('', 200)
        except Exception as e:
            logger.error(f"Error creating bucket {bucket}: {str(e)}")
            return make_response(xmltodict.unparse({'Error': {'Message': str(e)}}), 500)

    def delete_bucket(self, bucket):
        """Delete a bucket"""
        try:
            self.storage.delete_bucket(bucket)
            return make_response('', 204)
        except Exception as e:
            logger.error(f"Error deleting bucket {bucket}: {str(e)}")
            return make_response(xmltodict.unparse({'Error': {'Message': str(e)}}), 500)

    def list_objects(self, bucket):
        """List objects in a bucket"""
        try:
            prefix = request.args.get('prefix', '')
            max_keys = int(request.args.get('max-keys', '1000'))
            
            objects = self.storage.list_objects(bucket, prefix=prefix, max_keys=max_keys)
            response = {
                'Name': bucket,
                'Prefix': prefix,
                'MaxKeys': max_keys,
                'Contents': [
                    {
                        'Key': obj['key'],
                        'LastModified': obj.get('last_modified', datetime.datetime.now().isoformat()),
                        'Size': obj.get('size', 0),
                        'ETag': obj.get('etag', '')
                    } for obj in objects
                ]
            }
            return make_response(xmltodict.unparse({'ListBucketResult': response}), 200)
        except Exception as e:
            logger.error(f"Error listing objects in bucket {bucket}: {str(e)}")
            return make_response(xmltodict.unparse({'Error': {'Message': str(e)}}), 500)

    def put_object(self, bucket, key):
        """Upload an object"""
        try:
            content = request.get_data()
            etag = hashlib.md5(content).hexdigest()
            
            self.storage.put_object(bucket, key, content)
            return make_response('', 200, {'ETag': f'"{etag}"'})
        except Exception as e:
            logger.error(f"Error uploading object {key} to bucket {bucket}: {str(e)}")
            return make_response(xmltodict.unparse({'Error': {'Message': str(e)}}), 500)

    def get_object(self, bucket, key):
        """Download an object"""
        try:
            obj = self.storage.get_object(bucket, key)
            if obj is None:
                return make_response(xmltodict.unparse({'Error': {'Message': 'Not Found'}}), 404)
                
            return Response(
                obj['content'],
                mimetype='application/octet-stream',
                headers={
                    'ETag': f'"{obj.get("etag", "")}"',
                    'Last-Modified': obj.get('last_modified', datetime.datetime.now().isoformat()),
                    'Content-Length': str(len(obj['content']))
                }
            )
        except Exception as e:
            logger.error(f"Error downloading object {key} from bucket {bucket}: {str(e)}")
            return make_response(xmltodict.unparse({'Error': {'Message': str(e)}}), 500)

    def delete_object(self, bucket, key):
        """Delete an object"""
        try:
            self.storage.delete_object(bucket, key)
            return make_response('', 204)
        except Exception as e:
            logger.error(f"Error deleting object {key} from bucket {bucket}: {str(e)}")
            return make_response(xmltodict.unparse({'Error': {'Message': str(e)}}), 500)
