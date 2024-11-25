"""Base route utilities and decorators."""

import functools
import logging
import traceback
from quart import request, Response
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
from typing import Dict, Any, Optional, Union

from src.storage.backends import get_storage_backend
from src.api.services.fs_manager import FileSystemManager

logger = logging.getLogger(__name__)

def handle_s3_errors():
    """Decorator to handle S3 API errors in a consistent way."""
    def decorator(f):
        @functools.wraps(f)
        async def decorated_function(*args, **kwargs):
            try:
                result = await f(*args, **kwargs)
                if isinstance(result, bool):
                    return Response('', status=200 if result else 404)
                return result
            except BadRequest as e:
                error_response = {
                    'Error': {
                        'Code': 'BadRequest',
                        'Message': str(e)
                    }
                }
                return Response(
                    xmltodict.unparse(error_response),
                    status=400,
                    content_type='application/xml'
                )
            except Exception as e:
                logger.error(f"Error in S3 API: {str(e)}\n{traceback.format_exc()}")
                error_response = {
                    'Error': {
                        'Code': 'InternalError',
                        'Message': str(e)
                    }
                }
                return Response(
                    xmltodict.unparse(error_response),
                    status=500,
                    content_type='application/xml'
                )
        return decorated_function
    return decorator

async def format_error_response(code: str, message: str, status_code: int = 500) -> Response:
    """Format error response with proper XML content type."""
    error_response = {
        'Error': {
            'Code': code,
            'Message': message
        }
    }
    return Response(
        xmltodict.unparse(error_response),
        status=status_code,
        content_type='application/xml'
    )

def format_list_buckets_response(buckets: list, aws_style: bool = True) -> Dict[str, Any]:
    """Format list buckets response."""
    response = {
        'ListAllMyBucketsResult': {
            'Buckets': {
                'Bucket': [
                    {'Name': bucket['name'], 'CreationDate': bucket['creation_date']}
                    for bucket in buckets
                ]
            },
            'Owner': {
                'ID': 'owner',
                'DisplayName': 'owner'
            }
        }
    }
    return response

def format_list_objects_response(bucket: str, objects: list, prefix: str = '',
                               max_keys: int = 1000, aws_style: bool = True) -> Dict[str, Any]:
    """Format list objects response."""
    response = {
        'ListBucketResult': {
            'Name': bucket,
            'Prefix': prefix,
            'MaxKeys': str(max_keys),
            'IsTruncated': len(objects) == max_keys,
            'Contents': [
                {
                    'Key': obj['key'],
                    'LastModified': obj['last_modified'],
                    'ETag': obj['etag'],
                    'Size': str(obj['size']),
                    'StorageClass': obj.get('storage_class', 'STANDARD')
                }
                for obj in objects
            ]
        }
    }
    return response

def format_object_response(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Format object response."""
    headers = {
        'Content-Length': str(len(obj['content'])),
        'Last-Modified': obj['last_modified'],
        'ETag': obj['etag']
    }
    return Response(obj['content'], status=200, headers=headers)

class BaseS3Handler:
    """Base handler for S3-compatible APIs with shared functionality."""
    
    def __init__(self, fs_manager, aws_style=True):
        """Initialize base handler.
        
        Args:
            fs_manager: FileSystem manager instance
            aws_style: Whether to use AWS-style paths
        """
        self.storage = get_storage_backend(fs_manager)
        self.aws_style = aws_style
    
    @handle_s3_errors()
    async def list_buckets(self):
        """List all buckets."""
        try:
            buckets = await self.storage.list_buckets()
            response = format_list_buckets_response(buckets, self.aws_style)
            return Response(xmltodict.unparse(response), status=200, content_type='application/xml')
        except Exception as e:
            logger.error(f"Error listing buckets: {str(e)}")
            raise
    
    @handle_s3_errors()
    async def create_bucket(self, bucket):
        """Create a new bucket."""
        try:
            await self.storage.create_bucket(bucket)
            return Response('', status=200)
        except Exception as e:
            logger.error(f"Error creating bucket: {str(e)}")
            raise
    
    @handle_s3_errors()
    async def delete_bucket(self, bucket):
        """Delete a bucket."""
        try:
            await self.storage.delete_bucket(bucket)
            return Response('', status=204)
        except Exception as e:
            logger.error(f"Error deleting bucket: {str(e)}")
            raise
    
    @handle_s3_errors()
    async def list_objects(self, bucket):
        """List objects in a bucket."""
        try:
            prefix = request.args.get('prefix', '')
            max_keys = int(request.args.get('max-keys', '1000'))
            
            objects = await self.storage.list_objects(bucket, prefix=prefix, max_keys=max_keys)
            response = format_list_objects_response(bucket, objects, prefix, max_keys, self.aws_style)
            return Response(xmltodict.unparse(response), status=200, content_type='application/xml')
        except Exception as e:
            logger.error(f"Error listing objects: {str(e)}")
            raise
    
    @handle_s3_errors()
    async def get_object(self, bucket, key):
        """Get an object."""
        try:
            obj = await self.storage.get_object(bucket, key)
            return format_object_response(obj)
        except Exception as e:
            logger.error(f"Error getting object: {str(e)}")
            raise
    
    @handle_s3_errors()
    async def put_object(self, bucket, key):
        """Upload an object."""
        try:
            data = await request.get_data()
            metadata = {
                k[11:]: v for k, v in request.headers.items()
                if k.lower().startswith('x-amz-meta-')
            }
            
            storage_class = request.headers.get('x-amz-storage-class', 'STANDARD')
            
            result = await self.storage.put_object(
                bucket, key, data,
                metadata=metadata,
                storage_class=storage_class
            )
            
            response = Response('', status=200)
            response.headers['ETag'] = result.get('etag', '')
            return response
        except Exception as e:
            logger.error(f"Error putting object: {str(e)}")
            raise
    
    @handle_s3_errors()
    async def delete_object(self, bucket, key):
        """Delete an object."""
        try:
            await self.storage.delete_object(bucket, key)
            return Response('', status=204)
        except Exception as e:
            logger.error(f"Error deleting object: {str(e)}")
            raise
    
    def register_basic_routes(self, blueprint):
        """Register basic S3-compatible routes.
        
        Args:
            blueprint: Quart blueprint to register routes on
        """
        # Basic bucket operations
        blueprint.add_url_rule(
            '/' if self.aws_style else '/buckets',
            'list_buckets',
            self.list_buckets,
            methods=['GET']
        )
        blueprint.add_url_rule(
            '/<bucket>',
            'create_bucket',
            self.create_bucket,
            methods=['PUT']
        )
        blueprint.add_url_rule(
            '/<bucket>',
            'delete_bucket',
            self.delete_bucket,
            methods=['DELETE']
        )
        blueprint.add_url_rule(
            '/<bucket>',
            'list_objects',
            self.list_objects,
            methods=['GET']
        )
        
        # Basic object operations
        blueprint.add_url_rule(
            '/<bucket>/<key>',
            'put_object',
            self.put_object,
            methods=['PUT']
        )
        blueprint.add_url_rule(
            '/<bucket>/<key>',
            'get_object',
            self.get_object,
            methods=['GET']
        )
        blueprint.add_url_rule(
            '/<bucket>/<key>',
            'delete_object',
            self.delete_object,
            methods=['DELETE']
        )
