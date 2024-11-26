"""AWS S3-compatible API routes."""

from flask import request, Response, Blueprint
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
from typing import Dict, Any, Optional, List, Union

from src.storage.backends import get_storage_backend
from src.api.services.fs_manager import FileSystemManager
from src.api.services.system_service import SystemService
from src.api.routes.base import BaseS3Handler, format_error_response

logger = logging.getLogger(__name__)

# Create Blueprint for AWS S3-compatible API routes
aws_s3_api = Blueprint('aws_s3_api', __name__)

class AWSS3ApiHandler(BaseS3Handler):
    """Handler for AWS S3-compatible API operations."""

    def __init__(self, fs_manager, infrastructure):
        """Initialize the handler with AWS S3 compatibility."""
        super().__init__(fs_manager, aws_style=True)
        self.infrastructure = infrastructure
        self.system = SystemService(os.getenv('STORAGE_ROOT', '/data/dfs'))
        self.register_aws_routes(aws_s3_api)

    def register_aws_routes(self, blueprint):
        """Register AWS S3-compatible routes."""
        
        @blueprint.route('/', methods=['GET'])
        def list_buckets():
            """List all buckets."""
            try:
                result = self.list_buckets()
                if isinstance(result, bool):
                    return format_error_response('ListBucketError', 'Failed to list buckets', 404)
                return result
            except Exception as e:
                logger.error(f"Error listing buckets: {str(e)}")
                return format_error_response('ListBucketError', str(e))

        @blueprint.route('/<bucket_name>', methods=['PUT'])
        def create_bucket(bucket_name):
            """Create a new bucket."""
            try:
                location = request.args.get('location', 'us-east-1')
                result = self.create_bucket(bucket_name, location)
                if not result:
                    return format_error_response('BucketCreationError', 'Failed to create bucket', 400)
                return Response('', status=200)
            except Exception as e:
                logger.error(f"Error creating bucket: {str(e)}")
                return format_error_response('BucketCreationError', str(e))

        @blueprint.route('/<bucket_name>', methods=['DELETE'])
        def delete_bucket(bucket_name):
            """Delete a bucket."""
            try:
                result = self.delete_bucket(bucket_name)
                if not result:
                    return format_error_response('BucketDeletionError', 'Failed to delete bucket', 404)
                return Response('', status=204)
            except Exception as e:
                logger.error(f"Error deleting bucket: {str(e)}")
                return format_error_response('BucketDeletionError', str(e))

        @blueprint.route('/<bucket_name>', methods=['GET'])
        def list_objects(bucket_name):
            """List objects in a bucket."""
            try:
                prefix = request.args.get('prefix', '')
                delimiter = request.args.get('delimiter', '/')
                max_keys = int(request.args.get('max-keys', '1000'))
                marker = request.args.get('marker', '')
                
                result = self.list_objects(
                    bucket_name,
                    prefix=prefix,
                    delimiter=delimiter,
                    max_keys=max_keys,
                    marker=marker
                )
                
                if isinstance(result, bool):
                    return format_error_response('ListObjectsError', 'Failed to list objects', 404)
                return result
            except Exception as e:
                logger.error(f"Error listing objects: {str(e)}")
                return format_error_response('ListObjectsError', str(e))

        @blueprint.route('/<bucket_name>/<path:key>', methods=['PUT'])
        def put_object(bucket_name, key):
            """Upload an object."""
            try:
                content = request.get_data()
                metadata = {
                    'Content-Type': request.headers.get('Content-Type', 'application/octet-stream'),
                    'Content-Length': len(content)
                }
                
                result = self.put_object(bucket_name, key, content, metadata)
                if not result:
                    return format_error_response('PutObjectError', 'Failed to upload object', 400)
                
                return Response('', status=200)
            except Exception as e:
                logger.error(f"Error uploading object: {str(e)}")
                return format_error_response('PutObjectError', str(e))

        @blueprint.route('/<bucket_name>/<path:key>', methods=['GET'])
        def get_object(bucket_name, key):
            """Download an object."""
            try:
                result = self.get_object(bucket_name, key)
                if not result:
                    return format_error_response('GetObjectError', 'Object not found', 404)
                
                return Response(
                    result.content,
                    headers=result.metadata,
                    content_type=result.metadata.get('Content-Type', 'application/octet-stream')
                )
            except Exception as e:
                logger.error(f"Error downloading object: {str(e)}")
                return format_error_response('GetObjectError', str(e))

        @blueprint.route('/<bucket_name>/<path:key>', methods=['DELETE'])
        def delete_object(bucket_name, key):
            """Delete an object."""
            try:
                result = self.delete_object(bucket_name, key)
                if not result:
                    return format_error_response('DeleteObjectError', 'Object not found', 404)
                return Response('', status=204)
            except Exception as e:
                logger.error(f"Error deleting object: {str(e)}")
                return format_error_response('DeleteObjectError', str(e))

    def handle_storage_operation(self, operation: str, **kwargs) -> Union[Dict[str, Any], bool]:
        """Handle storage operation using infrastructure manager."""
        try:
            result = self.infrastructure.handle_storage_operation(operation, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Storage operation error: {operation} - {str(e)}")
            return False

    def list_buckets(self) -> Union[Dict[str, Any], bool]:
        """List all buckets."""
        return self.handle_storage_operation('list_buckets')

    def create_bucket(self, bucket_name: str, location: str) -> bool:
        """Create a new bucket."""
        return self.handle_storage_operation('create_bucket', bucket_name=bucket_name, location=location)

    def delete_bucket(self, bucket_name: str) -> bool:
        """Delete a bucket."""
        return self.handle_storage_operation('delete_bucket', bucket_name=bucket_name)

    def list_objects(self, bucket_name: str, **params) -> Union[Dict[str, Any], bool]:
        """List objects in a bucket."""
        return self.handle_storage_operation('list_objects', bucket_name=bucket_name, **params)

    def put_object(self, bucket_name: str, object_key: str, data: bytes,
                   metadata: Optional[Dict[str, str]] = None) -> Union[Dict[str, Any], bool]:
        """Upload an object."""
        return self.handle_storage_operation(
            'put_object',
            bucket_name=bucket_name,
            object_key=object_key,
            data=data,
            metadata=metadata
        )

    def get_object(self, bucket_name: str, object_key: str) -> Union[Dict[str, Any], bool]:
        """Download an object."""
        return self.handle_storage_operation('get_object', bucket_name=bucket_name, object_key=object_key)

    def delete_object(self, bucket_name: str, object_key: str) -> bool:
        """Delete an object."""
        return self.handle_storage_operation('delete_object', bucket_name=bucket_name, object_key=object_key)
