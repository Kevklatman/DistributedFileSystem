"""AWS S3-compatible API routes with proper async handling."""

from quart import request, Response, Blueprint
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
        async def list_buckets():
            """List all buckets."""
            try:
                result = await self.list_buckets()
                if isinstance(result, bool):
                    return await format_error_response('ListBucketError', 'Failed to list buckets', 404)
                return result
            except Exception as e:
                logger.error(f"Error listing buckets: {str(e)}")
                return await format_error_response('ListBucketError', str(e))

        @blueprint.route('/<bucket_name>', methods=['PUT'])
        async def create_bucket(bucket_name):
            """Create a new bucket."""
            try:
                location = request.args.get('location', 'us-east-1')
                config = {
                    'LocationConstraint': location,
                    'Versioning': request.headers.get('x-amz-versioning', 'Disabled'),
                    'ACL': request.headers.get('x-amz-acl', 'private')
                }
                
                result = await self.create_bucket(bucket_name, config)
                if not result:
                    return await format_error_response('CreateBucketError', 'Failed to create bucket', 400)
                return Response('', status=200)
            except Exception as e:
                logger.error(f"Error creating bucket: {str(e)}")
                return await format_error_response('CreateBucketError', str(e))

        @blueprint.route('/<bucket_name>', methods=['DELETE'])
        async def delete_bucket(bucket_name):
            """Delete a bucket."""
            try:
                force = request.args.get('force', 'false').lower() == 'true'
                result = await self.delete_bucket(bucket_name, force)
                if not result:
                    return await format_error_response('DeleteBucketError', 'Bucket not found', 404)
                return Response('', status=204)
            except Exception as e:
                logger.error(f"Error deleting bucket: {str(e)}")
                return await format_error_response('DeleteBucketError', str(e))

        @blueprint.route('/<bucket_name>', methods=['GET'])
        async def list_objects(bucket_name):
            """List objects in a bucket."""
            try:
                params = {
                    'prefix': request.args.get('prefix', ''),
                    'delimiter': request.args.get('delimiter', '/'),
                    'max_keys': int(request.args.get('max-keys', '1000')),
                    'marker': request.args.get('marker', ''),
                    'encoding_type': request.args.get('encoding-type', 'url')
                }
                
                result = await self.list_objects(bucket_name, **params)
                if isinstance(result, bool):
                    return await format_error_response('ListObjectsError', 'Failed to list objects', 404)
                return result
            except Exception as e:
                logger.error(f"Error listing objects: {str(e)}")
                return await format_error_response('ListObjectsError', str(e))

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['PUT'])
        async def put_object(bucket_name, object_key):
            """Upload an object."""
            try:
                data = await request.get_data()
                metadata = {
                    k[11:]: v for k, v in request.headers.items()
                    if k.lower().startswith('x-amz-meta-')
                }
                
                storage_class = request.headers.get('x-amz-storage-class', 'STANDARD')
                
                result = await self.put_object(bucket_name, object_key, data, metadata, storage_class)
                if isinstance(result, bool):
                    if not result:
                        return await format_error_response('PutObjectError', 'Failed to upload object', 400)
                    return Response('', status=200)
                
                response = Response('', status=200)
                response.headers['ETag'] = result.get('etag', '')
                return response
            except Exception as e:
                logger.error(f"Error uploading object: {str(e)}")
                return await format_error_response('PutObjectError', str(e))

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['GET'])
        async def get_object(bucket_name, object_key):
            """Download an object."""
            try:
                result = await self.get_object(bucket_name, object_key)
                
                if isinstance(result, bool):
                    return await format_error_response('GetObjectError', 'Object not found', 404)
                
                if not result or 'content' not in result:
                    return await format_error_response('GetObjectError', 'Object not found', 404)
                
                response = Response(result['content'], status=200)
                response.headers.update({
                    'Content-Length': str(len(result['content'])),
                    'Last-Modified': result.get('last_modified', ''),
                    'ETag': result.get('etag', ''),
                    'Content-Type': result.get('content_type', 'application/octet-stream')
                })
                
                # Add user metadata
                for k, v in result.get('metadata', {}).items():
                    response.headers[f'x-amz-meta-{k}'] = v
                    
                return response
            except Exception as e:
                logger.error(f"Error downloading object: {str(e)}")
                return await format_error_response('GetObjectError', str(e))

        @blueprint.route('/<bucket_name>/<path:object_key>', methods=['DELETE'])
        async def delete_object(bucket_name, object_key):
            """Delete an object."""
            try:
                version_id = request.args.get('versionId')
                result = await self.delete_object(bucket_name, object_key, version_id)
                if not result:
                    return await format_error_response('DeleteObjectError', 'Object not found', 404)
                return Response('', status=204)
            except Exception as e:
                logger.error(f"Error deleting object: {str(e)}")
                return await format_error_response('DeleteObjectError', str(e))

    async def handle_storage_operation(self, operation: str, **kwargs) -> Union[Dict[str, Any], bool]:
        """Handle storage operation using infrastructure manager."""
        try:
            result = await self.infrastructure.handle_storage_operation(operation, **kwargs)
            return result
        except Exception as e:
            logger.error(f"Storage operation error: {operation} - {str(e)}")
            return False

    async def list_buckets(self) -> Union[Dict[str, Any], bool]:
        """List all buckets."""
        return await self.handle_storage_operation('list_buckets')

    async def create_bucket(self, bucket_name: str, config: Dict[str, Any]) -> bool:
        """Create a new bucket."""
        return await self.handle_storage_operation('create_bucket', bucket_name=bucket_name, config=config)

    async def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """Delete a bucket."""
        return await self.handle_storage_operation('delete_bucket', bucket_name=bucket_name, force=force)

    async def list_objects(self, bucket_name: str, **params) -> Union[Dict[str, Any], bool]:
        """List objects in a bucket."""
        return await self.handle_storage_operation('list_objects', bucket_name=bucket_name, **params)

    async def put_object(self, bucket_name: str, object_key: str, data: bytes,
                        metadata: Optional[Dict[str, str]] = None,
                        storage_class: Optional[str] = None) -> Union[Dict[str, Any], bool]:
        """Upload an object."""
        return await self.handle_storage_operation(
            'put_object',
            bucket_name=bucket_name,
            object_key=object_key,
            data=data,
            metadata=metadata,
            storage_class=storage_class
        )

    async def get_object(self, bucket_name: str, object_key: str) -> Union[Dict[str, Any], bool]:
        """Download an object."""
        return await self.handle_storage_operation('get_object', bucket_name=bucket_name, object_key=object_key)

    async def delete_object(self, bucket_name: str, object_key: str,
                          version_id: Optional[str] = None) -> bool:
        """Delete an object."""
        return await self.handle_storage_operation(
            'delete_object',
            bucket_name=bucket_name,
            object_key=object_key,
            version_id=version_id
        )
