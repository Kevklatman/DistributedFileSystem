"""AWS S3-compatible API routes

This module implements a more complete AWS S3-compatible API with additional
features and compatibility with AWS SDKs.
"""
from flask import request, jsonify, Response, make_response, Blueprint
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
from typing import Dict, Any, Optional, List
import asyncio

from src.storage.backends import get_storage_backend
from src.api.services.fs_manager import FileSystemManager
from src.api.services.system_service import SystemService
from src.api.routes.base import BaseS3Handler

logger = logging.getLogger(__name__)

# Create Blueprint for AWS S3-compatible API routes
aws_s3_api = Blueprint('aws_s3_api', __name__)

class AWSS3ApiHandler(BaseS3Handler):
    """Handler for AWS S3-compatible API operations."""

    def __init__(self, fs_manager, infrastructure):
        """Initialize the handler with AWS S3 compatibility.

        Args:
            fs_manager: FileSystem manager instance
            infrastructure: Infrastructure manager instance
        """
        super().__init__(fs_manager, aws_style=True)
        self.infrastructure = infrastructure
        self.system = SystemService(os.getenv('STORAGE_ROOT', '/data/dfs'))
        self.register_aws_routes(aws_s3_api)

    async def handle_storage_operation(self, operation: str, **kwargs):
        """Handle storage operation using infrastructure manager."""
        return await self.infrastructure.handle_storage_operation(operation, **kwargs)

    def register_aws_routes(self, blueprint):
        """Register AWS S3-compatible routes with additional features."""
        
        @blueprint.route('/', methods=['GET'])
        def list_buckets():
            """List all buckets with AWS-style response."""
            try:
                buckets = asyncio.run(self.handle_storage_operation('list_buckets'))
                return self.format_aws_list_buckets_response(buckets)
            except Exception as e:
                logger.error(f"Error listing buckets: {str(e)}")
                return self.format_aws_error_response('ListBucketError', str(e))

        @blueprint.route('/<bucket_name>', methods=['PUT'])
        def create_bucket(bucket_name):
            """Create a new bucket with AWS-style configuration."""
            try:
                location = request.args.get('location', 'us-east-1')
                config = {
                    'LocationConstraint': location,
                    'Versioning': request.headers.get('x-amz-versioning', 'Disabled'),
                    'ACL': request.headers.get('x-amz-acl', 'private')
                }
                
                asyncio.run(self.handle_storage_operation(
                    'create_bucket',
                    bucket_name=bucket_name,
                    config=config
                ))
                return '', 200
            except Exception as e:
                logger.error(f"Error creating bucket: {str(e)}")
                return self.format_aws_error_response('CreateBucketError', str(e))

        @blueprint.route('/<bucket_name>', methods=['DELETE'])
        def delete_bucket(bucket_name):
            """Delete a bucket with AWS-style verification."""
            try:
                force = request.args.get('force', 'false').lower() == 'true'
                asyncio.run(self.handle_storage_operation(
                    'delete_bucket',
                    bucket_name=bucket_name,
                    force=force
                ))
                return '', 204
            except Exception as e:
                logger.error(f"Error deleting bucket: {str(e)}")
                return self.format_aws_error_response('DeleteBucketError', str(e))

        @blueprint.route('/<bucket_name>', methods=['GET'])
        def list_objects(bucket_name):
            """List objects with AWS-style pagination and filtering."""
            try:
                params = {
                    'prefix': request.args.get('prefix', ''),
                    'delimiter': request.args.get('delimiter', '/'),
                    'max_keys': int(request.args.get('max-keys', 1000)),
                    'marker': request.args.get('marker', ''),
                    'encoding_type': request.args.get('encoding-type', 'url')
                }
                
                objects = asyncio.run(self.handle_storage_operation(
                    'list_objects_v2',
                    bucket_name=bucket_name,
                    **params
                ))
                return self.format_aws_list_objects_response(objects)
            except Exception as e:
                logger.error(f"Error listing objects: {str(e)}")
                return self.format_aws_error_response('ListObjectsError', str(e))

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['PUT'])
        def put_object(bucket_name, object_key):
            """Upload an object with AWS-style metadata and storage options."""
            try:
                content = request.get_data()
                metadata = {k.lower(): v for k, v in request.headers.items() 
                          if k.lower().startswith('x-amz-meta-')}
                
                params = {
                    'storage_class': request.headers.get('x-amz-storage-class', 'STANDARD'),
                    'acl': request.headers.get('x-amz-acl', 'private'),
                    'content_type': request.headers.get('Content-Type', 'application/octet-stream'),
                    'content_encoding': request.headers.get('Content-Encoding'),
                    'content_language': request.headers.get('Content-Language'),
                    'content_disposition': request.headers.get('Content-Disposition'),
                    'cache_control': request.headers.get('Cache-Control'),
                    'expires': request.headers.get('Expires'),
                    'website_redirect_location': request.headers.get('x-amz-website-redirect-location'),
                    'tagging': request.headers.get('x-amz-tagging'),
                    'server_side_encryption': request.headers.get('x-amz-server-side-encryption'),
                    'metadata': metadata
                }
                
                result = asyncio.run(self.handle_storage_operation(
                    'put_object',
                    bucket_name=bucket_name,
                    object_key=object_key,
                    content=content,
                    **params
                ))
                
                response = make_response('', 200)
                response.headers['ETag'] = result.get('etag', '')
                response.headers['x-amz-version-id'] = result.get('version_id', '')
                return response
            except Exception as e:
                logger.error(f"Error uploading object: {str(e)}")
                return self.format_aws_error_response('PutObjectError', str(e))

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['GET'])
        def get_object(bucket_name, object_key):
            """Download an object with AWS-style response headers."""
            try:
                params = {
                    'version_id': request.args.get('versionId'),
                    'response_content_type': request.args.get('response-content-type'),
                    'response_content_language': request.args.get('response-content-language'),
                    'response_expires': request.args.get('response-expires'),
                    'response_cache_control': request.args.get('response-cache-control'),
                    'response_content_disposition': request.args.get('response-content-disposition'),
                    'response_content_encoding': request.args.get('response-content-encoding')
                }
                
                result = asyncio.run(self.handle_storage_operation(
                    'get_object',
                    bucket_name=bucket_name,
                    object_key=object_key,
                    **params
                ))
                
                response = make_response(result['content'])
                for header, value in result.get('metadata', {}).items():
                    response.headers[f'x-amz-meta-{header}'] = value
                    
                response.headers.update({
                    'Content-Type': result.get('content_type', 'application/octet-stream'),
                    'Content-Length': str(len(result['content'])),
                    'ETag': result.get('etag', ''),
                    'Last-Modified': result.get('last_modified', ''),
                    'x-amz-version-id': result.get('version_id', ''),
                    'x-amz-server-side-encryption': result.get('server_side_encryption'),
                    'x-amz-storage-class': result.get('storage_class', 'STANDARD')
                })
                return response
            except Exception as e:
                logger.error(f"Error downloading object: {str(e)}")
                return self.format_aws_error_response('GetObjectError', str(e))

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['DELETE'])
        def delete_object(bucket_name, object_key):
            """Delete an object with AWS-style version handling."""
            try:
                version_id = request.args.get('versionId')
                asyncio.run(self.handle_storage_operation(
                    'delete_object',
                    bucket_name=bucket_name,
                    object_key=object_key,
                    version_id=version_id
                ))
                return '', 204
            except Exception as e:
                logger.error(f"Error deleting object: {str(e)}")
                return self.format_aws_error_response('DeleteObjectError', str(e))
