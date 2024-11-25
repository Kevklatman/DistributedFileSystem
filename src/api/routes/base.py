"""Base handler for S3-compatible API operations."""

from flask import request, jsonify, Response, make_response, Blueprint
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from functools import wraps

from src.storage.backends import get_storage_backend
from src.api.services.fs_manager import FileSystemManager

logger = logging.getLogger(__name__)

def handle_s3_errors():
    """Decorator to handle S3 API errors and format responses."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(result)
                    finally:
                        loop.close()
                return result
            except BadRequest as e:
                return make_response(
                    xmltodict.unparse({
                        'Error': {
                            'Code': 'BadRequest',
                            'Message': str(e)
                        }
                    }), 400
                )
            except Exception as e:
                logger.error(f"Error in S3 API: {str(e)}")
                return make_response(
                    xmltodict.unparse({
                        'Error': {
                            'Code': 'InternalError',
                            'Message': str(e)
                        }
                    }), 500
                )
        return wrapper
    return decorator

class BaseS3Handler:
    """Base handler for S3-compatible APIs with shared functionality."""
    
    def __init__(self, fs_manager, aws_style=False):
        """Initialize the handler.
        
        Args:
            fs_manager: FileSystem manager instance
            aws_style (bool): If True, use AWS S3-style responses
        """
        self.storage = get_storage_backend(fs_manager)
        self.aws_style = aws_style
    
    @handle_s3_errors()
    def list_buckets(self):
        """List all buckets."""
        buckets = self.storage.list_buckets()
        return format_list_buckets_response(buckets, self.aws_style)
    
    @handle_s3_errors()
    def create_bucket(self, bucket):
        """Create a new bucket."""
        self.storage.create_bucket(bucket)
        return make_response('', 200)
    
    @handle_s3_errors()
    def delete_bucket(self, bucket):
        """Delete a bucket."""
        self.storage.delete_bucket(bucket)
        return make_response('', 204)
    
    @handle_s3_errors()
    def list_objects(self, bucket):
        """List objects in a bucket."""
        prefix = request.args.get('prefix', '')
        max_keys = int(request.args.get('max-keys', '1000'))
        
        objects = self.storage.list_objects(bucket, prefix=prefix, max_keys=max_keys)
        return format_list_objects_response(bucket, objects, prefix, max_keys, self.aws_style)
    
    @handle_s3_errors()
    def get_object(self, bucket, key):
        """Get an object."""
        obj = self.storage.get_object(bucket, key)
        return format_object_response(obj)
    
    @handle_s3_errors()
    def put_object(self, bucket, key):
        """Upload an object."""
        content = request.get_data()
        self.storage.put_object(bucket, key, content)
        etag = f"\"{self.storage.calculate_etag(content)}\""
        return make_response('', 200, {'ETag': etag})
    
    @handle_s3_errors()
    def delete_object(self, bucket, key):
        """Delete an object."""
        self.storage.delete_object(bucket, key)
        return make_response('', 204)
    
    def register_basic_routes(self, blueprint):
        """Register basic S3-compatible routes.
        
        Args:
            blueprint: Flask blueprint to register routes on
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
