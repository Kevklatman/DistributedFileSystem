"""S3-compatible API routes

This module implements a simplified S3-compatible API that provides basic object storage
functionality without the full complexity of AWS S3.
"""
from quart import request, Response, Blueprint
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
from typing import Dict, Any, List, Optional, Union

from src.storage.backends import get_storage_backend
from src.api.services.fs_manager import FileSystemManager
from src.api.services.system_service import SystemService
from src.api.routes.base import handle_s3_errors

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

    async def handle_storage_operation(self, operation: str, **kwargs) -> Union[Dict[str, Any], bool]:
        """Handle storage operation using infrastructure manager."""
        return await self.infrastructure.handle_storage_operation(operation, **kwargs)

    def create_error_response(self, code: str, message: str, status_code: int = 500) -> Response:
        """Format error response in S3-compatible XML format."""
        error_response = {
            'Error': {
                'Code': code,
                'Message': message,
                'RequestId': hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()
            }
        }
        return Response(
            xmltodict.unparse(error_response),
            status=status_code,
            content_type='application/xml'
        )

    def create_list_buckets_response(self, buckets_data: Dict[str, List[Dict[str, Any]]]) -> Response:
        """Format list buckets response in S3-compatible XML format."""
        if not isinstance(buckets_data, dict) or 'buckets' not in buckets_data:
            return self.create_error_response('InvalidResponse', 'Invalid bucket list format', 500)

        response = {
            'ListAllMyBucketsResult': {
                'Buckets': {
                    'Bucket': [
                        {
                            'Name': bucket.get('name', 'unnamed'),
                            'CreationDate': bucket.get('creation_date', datetime.datetime.now().isoformat())
                        }
                        for bucket in buckets_data['buckets']
                    ]
                },
                'Owner': {
                    'ID': 'default',
                    'DisplayName': 'default'
                }
            }
        }
        return Response(
            xmltodict.unparse(response),
            status=200,
            content_type='application/xml'
        )

    def create_list_objects_response(self, bucket_name: str, objects_data: Dict[str, Any]) -> Response:
        """Format list objects response in S3-compatible XML format."""
        if not isinstance(objects_data, dict) or 'objects' not in objects_data:
            return self.create_error_response('InvalidResponse', 'Invalid object list format', 500)

        response = {
            'ListBucketResult': {
                'Name': bucket_name,
                'Prefix': objects_data.get('prefix', ''),
                'MaxKeys': str(objects_data.get('max_keys', 1000)),
                'Delimiter': objects_data.get('delimiter', '/'),
                'IsTruncated': str(objects_data.get('is_truncated', False)).lower(),
                'Contents': [
                    {
                        'Key': obj.get('key', ''),
                        'LastModified': obj.get('last_modified', datetime.datetime.now().isoformat()),
                        'ETag': obj.get('etag', ''),
                        'Size': str(obj.get('size', 0)),
                        'StorageClass': obj.get('storage_class', 'STANDARD')
                    }
                    for obj in objects_data['objects']
                ]
            }
        }

        # Add CommonPrefixes if present
        if 'common_prefixes' in objects_data:
            response['ListBucketResult']['CommonPrefixes'] = [
                {'Prefix': prefix}
                for prefix in objects_data['common_prefixes']
            ]

        return Response(
            xmltodict.unparse(response),
            status=200,
            content_type='application/xml'
        )

    def register_basic_routes(self, blueprint):
        """Register the basic S3 API routes."""

        @blueprint.route('/', methods=['GET'])
        @handle_s3_errors()
        async def list_buckets():
            """List all buckets."""
            try:
                result = await self.handle_storage_operation('list_buckets')
                if isinstance(result, bool):
                    return self.create_error_response('ListBucketsError', 'Failed to list buckets', 500)
                return self.create_list_buckets_response(result)
            except Exception as e:
                logger.error(f"Error listing buckets: {str(e)}")
                return self.create_error_response('ListBucketsError', str(e), 500)

        @blueprint.route('/<bucket_name>', methods=['PUT'])
        @handle_s3_errors()
        async def create_bucket(bucket_name: str):
            """Create a new bucket."""
            try:
                result = await self.handle_storage_operation('create_bucket', bucket_name=bucket_name)
                if not result:
                    return self.create_error_response('BucketCreationError', 'Failed to create bucket', 400)
                return Response('', status=200)
            except Exception as e:
                logger.error(f"Error creating bucket: {str(e)}")
                return self.create_error_response('BucketCreationError', str(e), 500)

        @blueprint.route('/<bucket_name>', methods=['GET'])
        @handle_s3_errors()
        async def list_objects(bucket_name: str):
            """List objects in a bucket."""
            try:
                prefix = request.args.get('prefix', '')
                delimiter = request.args.get('delimiter', '/')
                max_keys = int(request.args.get('max-keys', '1000'))
                marker = request.args.get('marker', '')

                result = await self.handle_storage_operation(
                    'list_objects',
                    bucket_name=bucket_name,
                    prefix=prefix,
                    delimiter=delimiter,
                    max_keys=max_keys,
                    marker=marker
                )

                if isinstance(result, bool):
                    return self.create_error_response('ListObjectsError', 'Failed to list objects', 404)
                return self.create_list_objects_response(bucket_name, result)
            except Exception as e:
                logger.error(f"Error listing objects: {str(e)}")
                return self.create_error_response('ListObjectsError', str(e), 500)

        @blueprint.route('/<bucket_name>', methods=['DELETE'])
        @handle_s3_errors()
        async def delete_bucket(bucket_name: str):
            """Delete a bucket."""
            try:
                result = await self.handle_storage_operation('delete_bucket', bucket_name=bucket_name)
                if not result:
                    return self.create_error_response('BucketDeletionError', 'Failed to delete bucket', 404)
                return Response('', status=204)
            except Exception as e:
                logger.error(f"Error deleting bucket: {str(e)}")
                return self.create_error_response('BucketDeletionError', str(e), 500)

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['PUT'])
        @handle_s3_errors()
        async def put_object(bucket_name: str, object_key: str):
            """Upload an object."""
            try:
                data = await request.get_data()
                result = await self.handle_storage_operation(
                    'put_object',
                    bucket_name=bucket_name,
                    object_key=object_key,
                    data=data
                )

                if isinstance(result, bool):
                    if not result:
                        return self.create_error_response('PutObjectError', 'Failed to upload object', 400)
                    return Response('', status=200)

                response = Response('', status=200)
                if isinstance(result, dict):
                    response.headers['ETag'] = result.get('etag', '')
                return response
            except Exception as e:
                logger.error(f"Error uploading object: {str(e)}")
                return self.create_error_response('PutObjectError', str(e), 500)

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['GET'])
        @handle_s3_errors()
        async def get_object(bucket_name: str, object_key: str):
            """Download an object."""
            try:
                result = await self.handle_storage_operation(
                    'get_object',
                    bucket_name=bucket_name,
                    object_key=object_key
                )

                if isinstance(result, bool):
                    return self.create_error_response('GetObjectError', 'Object not found', 404)

                if not result or 'content' not in result:
                    return self.create_error_response('GetObjectError', 'Object not found', 404)

                response = Response(result['content'], status=200)
                response.headers.update({
                    'Content-Length': str(len(result['content'])),
                    'Last-Modified': result.get('last_modified', ''),
                    'ETag': result.get('etag', ''),
                    'Content-Type': result.get('content_type', 'application/octet-stream')
                })

                return response
            except Exception as e:
                logger.error(f"Error downloading object: {str(e)}")
                return self.create_error_response('GetObjectError', str(e), 500)

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['DELETE'])
        @handle_s3_errors()
        async def delete_object(bucket_name: str, object_key: str):
            """Delete an object."""
            try:
                result = await self.handle_storage_operation(
                    'delete_object',
                    bucket_name=bucket_name,
                    object_key=object_key
                )

                if not result:
                    return self.create_error_response('DeleteObjectError', 'Object not found', 404)
                return Response('', status=204)
            except Exception as e:
                logger.error(f"Error deleting object: {str(e)}")
                return self.create_error_response('DeleteObjectError', str(e), 500)
