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
from src.storage.backends import get_storage_backend
from src.api.services.fs_manager import FileSystemManager
from src.api.services.system_service import SystemService
from src.api.routes.base import handle_s3_errors
import asyncio

logger = logging.getLogger(__name__)

# Create Blueprint for S3-compatible API routes
s3_api = Blueprint('s3_api', __name__)

class S3ApiHandler:
    """Handler for S3-compatible API operations."""

    def __init__(self, fs_manager, infrastructure):
        """Initialize the S3 API handler."""
        self.fs_manager = fs_manager
        self.infrastructure = infrastructure
        self.system = SystemService(os.getenv('STORAGE_ROOT', '/data/dfs'))
        self.register_basic_routes(s3_api)

    async def handle_storage_operation(self, operation: str, **kwargs):
        """Handle storage operation using infrastructure manager."""
        return await self.infrastructure.handle_storage_operation(operation, **kwargs)

    def format_error_response(self, error_message: str, status_code: int = 500) -> Response:
        """Format error response in S3-compatible XML format.

        Args:
            error_message: Error message to include
            status_code: HTTP status code

        Returns:
            Flask Response with XML error message
        """
        error_response = {
            'Error': {
                'Code': str(status_code),
                'Message': error_message,
                'RequestId': hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()
            }
        }
        return make_response(xmltodict.unparse(error_response), status_code)

    def format_list_buckets_response(self, buckets):
        response = {
            'ListAllMyBucketsResult': {
                'Buckets': {
                    'Bucket': [
                        {'Name': bucket['name'], 'CreationDate': bucket['creation_date']}
                        for bucket in buckets
                    ]
                },
                'Owner': {
                    'ID': 'default',
                    'DisplayName': 'default'
                }
            }
        }
        return make_response(xmltodict.unparse(response), 200)

    def format_list_objects_response(self, objects):
        response = {
            'ListBucketResult': {
                'Name': objects['bucket_name'],
                'Prefix': objects.get('prefix', ''),
                'MaxKeys': objects.get('max_keys', 1000),
                'Delimiter': objects.get('delimiter', '/'),
                'IsTruncated': objects.get('is_truncated', False),
                'Contents': [
                    {'Key': obj['key'], 'LastModified': obj['last_modified'], 'ETag': obj['etag'], 'Size': obj['size'], 'StorageClass': 'STANDARD'}
                    for obj in objects['objects']
                ],
                'CommonPrefixes': [
                    {'Prefix': prefix}
                    for prefix in objects.get('prefixes', [])
                ]
            }
        }
        return make_response(xmltodict.unparse(response), 200)

    def register_basic_routes(self, blueprint):
        """Register the basic S3 API routes."""

        @blueprint.route('/', methods=['GET'], endpoint='list_buckets')
        @handle_s3_errors()
        async def list_buckets():
            """List all buckets."""
            try:
                buckets = await self.handle_storage_operation('list_buckets')
                return self.format_list_buckets_response(buckets)
            except Exception as e:
                logger.error(f"Error listing buckets: {str(e)}")
                return self.format_error_response('ListBucketsError', str(e))

        @blueprint.route('/<bucket_name>', methods=['PUT'], endpoint='create_bucket')
        @handle_s3_errors()
        async def create_bucket(bucket_name):
            """Create a new bucket."""
            try:
                await self.handle_storage_operation('create_bucket', bucket_name=bucket_name)
                return '', 200
            except Exception as e:
                logger.error(f"Error creating bucket: {str(e)}")
                return self.format_error_response('CreateBucketError', str(e))

        @blueprint.route('/<bucket_name>', methods=['DELETE'], endpoint='delete_bucket')
        @handle_s3_errors()
        async def delete_bucket(bucket_name):
            """Delete a bucket."""
            try:
                await self.handle_storage_operation('delete_bucket', bucket_name=bucket_name)
                return '', 204
            except Exception as e:
                logger.error(f"Error deleting bucket: {str(e)}")
                return self.format_error_response('DeleteBucketError', str(e))

        @blueprint.route('/<bucket_name>', methods=['GET'], endpoint='list_objects')
        @handle_s3_errors()
        async def list_objects(bucket_name):
            """List objects in a bucket."""
            try:
                prefix = request.args.get('prefix', '')
                delimiter = request.args.get('delimiter', '/')
                max_keys = int(request.args.get('max-keys', 1000))
                
                objects = await self.handle_storage_operation(
                    'list_objects',
                    bucket_name=bucket_name,
                    prefix=prefix,
                    delimiter=delimiter,
                    max_keys=max_keys
                )
                return self.format_list_objects_response(objects)
            except Exception as e:
                logger.error(f"Error listing objects: {str(e)}")
                return self.format_error_response('ListObjectsError', str(e))

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['PUT'], endpoint='put_object')
        @handle_s3_errors()
        async def put_object(bucket_name, object_key):
            """Upload an object."""
            content = request.get_data()
            try:
                await self.handle_storage_operation('put_object', bucket=bucket_name, key=object_key, content=content)
                etag = f"\"{hashlib.md5(content).hexdigest()}\""
                return make_response('', 200, {'ETag': etag})
            except Exception as e:
                logger.error(f"Error uploading object: {str(e)}")
                return self.format_error_response('PutObjectError', str(e))

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['GET'], endpoint='get_object')
        @handle_s3_errors()
        async def get_object(bucket_name, object_key):
            """Get an object."""
            try:
                obj = await self.handle_storage_operation('get_object', bucket=bucket_name, key=object_key)
                return make_response(obj['content'], 200, {
                    'Content-Type': obj.get('content_type', 'application/octet-stream'),
                    'Content-Length': len(obj['content']),
                    'ETag': f"\"{obj.get('etag', '')}\""
                })
            except Exception as e:
                logger.error(f"Error getting object: {str(e)}")
                return self.format_error_response('GetObjectError', str(e))

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['DELETE'], endpoint='delete_object')
        @handle_s3_errors()
        async def delete_object(bucket_name, object_key):
            """Delete an object."""
            try:
                await self.handle_storage_operation('delete_object', bucket=bucket_name, key=object_key)
                return '', 204
            except Exception as e:
                logger.error(f"Error deleting object: {str(e)}")
                return self.format_error_response('DeleteObjectError', str(e))
