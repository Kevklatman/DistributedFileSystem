"""Base route utilities and decorators."""

import functools
import logging
import traceback
from flask import request, Response
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
        def decorated_function(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
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

def format_error_response(code: str, message: str, status_code: int = 500) -> Response:
    """Format error response with proper XML content type."""
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

def format_list_buckets_response(buckets: list, aws_style: bool = True) -> Response:
    """Format list buckets response."""
    response = {
        'ListAllMyBucketsResult': {
            'Owner': {
                'ID': 'dfs-owner',
                'DisplayName': 'DFS Owner'
            },
            'Buckets': {
                'Bucket': [
                    {
                        'Name': bucket.name,
                        'CreationDate': bucket.creation_date.isoformat()
                    } for bucket in buckets
                ]
            }
        }
    }
    return Response(xmltodict.unparse(response), content_type='application/xml')

def format_list_objects_response(bucket: str, objects: list, prefix: str = '',
                               max_keys: int = 1000, aws_style: bool = True) -> Response:
    """Format list objects response."""
    response = {
        'ListBucketResult': {
            'Name': bucket,
            'Prefix': prefix,
            'MaxKeys': max_keys,
            'Contents': [
                {
                    'Key': obj.key,
                    'LastModified': obj.last_modified.isoformat(),
                    'Size': obj.size,
                    'StorageClass': obj.storage_class
                } for obj in objects
            ]
        }
    }
    return Response(xmltodict.unparse(response), content_type='application/xml')

def format_object_response(obj: Dict[str, Any]) -> Response:
    """Format object response."""
    return Response(
        obj['content'],
        headers=obj.get('metadata', {}),
        content_type=obj.get('content_type', 'application/octet-stream')
    )

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

    def list_buckets(self) -> Union[Dict[str, Any], bool]:
        """List all buckets."""
        try:
            buckets = self.storage.list_buckets()
            return format_list_buckets_response(buckets, self.aws_style)
        except Exception as e:
            logger.error(f"Error listing buckets: {str(e)}")
            return False

    def create_bucket(self, bucket: str) -> bool:
        """Create a new bucket."""
        try:
            self.storage.create_bucket(bucket)
            return True
        except Exception as e:
            logger.error(f"Error creating bucket {bucket}: {str(e)}")
            return False

    def delete_bucket(self, bucket: str) -> bool:
        """Delete a bucket."""
        try:
            self.storage.delete_bucket(bucket)
            return True
        except Exception as e:
            logger.error(f"Error deleting bucket {bucket}: {str(e)}")
            return False

    def list_objects(self, bucket: str, prefix: str = '', delimiter: str = '/',
                    max_keys: int = 1000, marker: str = '') -> Union[Dict[str, Any], bool]:
        """List objects in a bucket."""
        try:
            objects = self.storage.list_objects(bucket, prefix, delimiter, max_keys, marker)
            return format_list_objects_response(bucket, objects, prefix, max_keys, self.aws_style)
        except Exception as e:
            logger.error(f"Error listing objects in bucket {bucket}: {str(e)}")
            return False

    def get_object(self, bucket: str, key: str) -> Union[Dict[str, Any], bool]:
        """Get an object."""
        try:
            obj = self.storage.get_object(bucket, key)
            return format_object_response(obj)
        except Exception as e:
            logger.error(f"Error getting object {key} from bucket {bucket}: {str(e)}")
            return False

    def put_object(self, bucket: str, key: str, data: bytes,
                  metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload an object."""
        try:
            self.storage.put_object(bucket, key, data, metadata)
            return True
        except Exception as e:
            logger.error(f"Error putting object {key} to bucket {bucket}: {str(e)}")
            return False

    def delete_object(self, bucket: str, key: str) -> bool:
        """Delete an object."""
        try:
            self.storage.delete_object(bucket, key)
            return True
        except Exception as e:
            logger.error(f"Error deleting object {key} from bucket {bucket}: {str(e)}")
            return False

    def register_basic_routes(self, blueprint):
        """Register basic S3-compatible routes.
        
        Args:
            blueprint: Flask blueprint to register routes on
        """
        @blueprint.route('/', methods=['GET'])
        @handle_s3_errors()
        def list_buckets():
            return self.list_buckets()

        @blueprint.route('/<bucket>', methods=['PUT'])
        @handle_s3_errors()
        def create_bucket(bucket):
            return self.create_bucket(bucket)

        @blueprint.route('/<bucket>', methods=['DELETE'])
        @handle_s3_errors()
        def delete_bucket(bucket):
            return self.delete_bucket(bucket)

        @blueprint.route('/<bucket>', methods=['GET'])
        @handle_s3_errors()
        def list_objects(bucket):
            prefix = request.args.get('prefix', '')
            delimiter = request.args.get('delimiter', '/')
            max_keys = int(request.args.get('max-keys', '1000'))
            marker = request.args.get('marker', '')
            return self.list_objects(bucket, prefix, delimiter, max_keys, marker)

        @blueprint.route('/<bucket>/<path:key>', methods=['PUT'])
        @handle_s3_errors()
        def put_object(bucket, key):
            data = request.get_data()
            metadata = {
                'Content-Type': request.headers.get('Content-Type', 'application/octet-stream'),
                'Content-Length': len(data)
            }
            return self.put_object(bucket, key, data, metadata)

        @blueprint.route('/<bucket>/<path:key>', methods=['GET'])
        @handle_s3_errors()
        def get_object(bucket, key):
            return self.get_object(bucket, key)

        @blueprint.route('/<bucket>/<path:key>', methods=['DELETE'])
        @handle_s3_errors()
        def delete_object(bucket, key):
            return self.delete_object(bucket, key)
