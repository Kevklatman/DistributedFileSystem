"""Base route utilities and decorators."""

import functools
import logging
import traceback
from quart import request, make_response, Blueprint
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
from src.storage.backends import get_storage_backend
from src.api.services.fs_manager import FileSystemManager

logger = logging.getLogger(__name__)

def handle_s3_errors():
    """Decorator to handle S3 API errors in a consistent way."""
    def decorator(f):
        @functools.wraps(f)
        async def decorated_function(*args, **kwargs):
            try:
                return await f(*args, **kwargs)
            except BadRequest as e:
                error_response = {
                    'Error': {
                        'Code': 'BadRequest',
                        'Message': str(e)
                    }
                }
                return await make_response(xmltodict.unparse(error_response), 400)
            except Exception as e:
                logger.error(f"Error in S3 API: {str(e)}\n{traceback.format_exc()}")
                error_response = {
                    'Error': {
                        'Code': 'InternalError',
                        'Message': str(e)
                    }
                }
                return await make_response(xmltodict.unparse(error_response), 500)
        return decorated_function
    return decorator

async def format_list_buckets_response(buckets, aws_style=True):
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
                'ID': 'default',
                'DisplayName': 'default'
            }
        }
    }
    return await make_response(xmltodict.unparse(response), 200)

async def format_list_objects_response(bucket, objects, prefix, max_keys, aws_style=True):
    """Format list objects response."""
    response = {
        'ListBucketResult': {
            'Name': bucket,
            'Prefix': prefix,
            'MaxKeys': max_keys,
            'IsTruncated': False,
            'Contents': [
                {
                    'Key': obj['key'],
                    'LastModified': obj['last_modified'],
                    'ETag': obj['etag'],
                    'Size': obj['size'],
                    'StorageClass': 'STANDARD'
                }
                for obj in objects
            ]
        }
    }
    return await make_response(xmltodict.unparse(response), 200)

async def format_object_response(obj):
    """Format object response."""
    headers = {
        'Content-Type': obj.get('content_type', 'application/octet-stream'),
        'Content-Length': str(len(obj['content'])),
        'ETag': f"\"{obj.get('etag', '')}\""
    }
    return await make_response(obj['content'], 200, headers)

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
        buckets = self.storage.list_buckets()
        return await format_list_buckets_response(buckets, self.aws_style)
    
    @handle_s3_errors()
    async def create_bucket(self, bucket):
        """Create a new bucket."""
        self.storage.create_bucket(bucket)
        return await make_response('', 200)
    
    @handle_s3_errors()
    async def delete_bucket(self, bucket):
        """Delete a bucket."""
        self.storage.delete_bucket(bucket)
        return await make_response('', 204)
    
    @handle_s3_errors()
    async def list_objects(self, bucket):
        """List objects in a bucket."""
        prefix = request.args.get('prefix', '')
        max_keys = int(request.args.get('max-keys', '1000'))
        
        objects = self.storage.list_objects(bucket, prefix=prefix, max_keys=max_keys)
        return await format_list_objects_response(bucket, objects, prefix, max_keys, self.aws_style)
    
    @handle_s3_errors()
    async def get_object(self, bucket, key):
        """Get an object."""
        obj = self.storage.get_object(bucket, key)
        return await format_object_response(obj)
    
    @handle_s3_errors()
    async def put_object(self, bucket, key):
        """Upload an object."""
        content = await request.get_data()
        self.storage.put_object(bucket, key, content)
        etag = f"\"{self.storage.calculate_etag(content)}\""
        return await make_response('', 200, {'ETag': etag})
    
    @handle_s3_errors()
    async def delete_object(self, bucket, key):
        """Delete an object."""
        self.storage.delete_object(bucket, key)
        return await make_response('', 204)
    
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
