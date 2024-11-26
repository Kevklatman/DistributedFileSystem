"""S3-compatible API routes

This module implements a simplified S3-compatible API that provides basic object storage
functionality without the full complexity of AWS S3.
"""
from flask import request, Response, Blueprint
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

    def handle_storage_operation(self, operation: str, **kwargs) -> Union[Dict[str, Any], bool]:
        """Handle storage operation using infrastructure manager."""
        return self.infrastructure.handle_storage_operation(operation, **kwargs)

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

    def register_basic_routes(self, blueprint: Blueprint):
        """Register basic S3-compatible routes."""
        
        @blueprint.route('/', methods=['GET'])
        @handle_s3_errors
        def list_buckets():
            """List all buckets."""
            try:
                buckets = self.fs_manager.list_buckets()
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
                return Response(
                    xmltodict.unparse(response),
                    content_type='application/xml'
                )
            except Exception as e:
                logger.error(f"Error listing buckets: {str(e)}")
                return self.create_error_response('InternalError', str(e))

        @blueprint.route('/<bucket>', methods=['PUT'])
        @handle_s3_errors
        def create_bucket(bucket):
            """Create a new bucket."""
            try:
                self.fs_manager.create_bucket(bucket)
                return Response('', status=200)
            except Exception as e:
                logger.error(f"Error creating bucket {bucket}: {str(e)}")
                return self.create_error_response('InternalError', str(e))

        @blueprint.route('/<bucket>', methods=['DELETE'])
        @handle_s3_errors
        def delete_bucket(bucket):
            """Delete a bucket."""
            try:
                self.fs_manager.delete_bucket(bucket)
                return Response('', status=204)
            except Exception as e:
                logger.error(f"Error deleting bucket {bucket}: {str(e)}")
                return self.create_error_response('InternalError', str(e))

        @blueprint.route('/<bucket>/<path:key>', methods=['PUT'])
        @handle_s3_errors
        def put_object(bucket, key):
            """Upload an object to a bucket."""
            try:
                content = request.get_data()
                metadata = {
                    'Content-Type': request.headers.get('Content-Type', 'application/octet-stream'),
                    'Content-Length': len(content)
                }
                self.fs_manager.put_object(bucket, key, content, metadata)
                return Response('', status=200)
            except Exception as e:
                logger.error(f"Error uploading object {key} to bucket {bucket}: {str(e)}")
                return self.create_error_response('InternalError', str(e))

        @blueprint.route('/<bucket>/<path:key>', methods=['GET'])
        @handle_s3_errors
        def get_object(bucket, key):
            """Download an object from a bucket."""
            try:
                obj = self.fs_manager.get_object(bucket, key)
                return Response(
                    obj.content,
                    headers=obj.metadata,
                    content_type=obj.metadata.get('Content-Type', 'application/octet-stream')
                )
            except Exception as e:
                logger.error(f"Error downloading object {key} from bucket {bucket}: {str(e)}")
                return self.create_error_response('InternalError', str(e))

        @blueprint.route('/<bucket>/<path:key>', methods=['DELETE'])
        @handle_s3_errors
        def delete_object(bucket, key):
            """Delete an object from a bucket."""
            try:
                self.fs_manager.delete_object(bucket, key)
                return Response('', status=204)
            except Exception as e:
                logger.error(f"Error deleting object {key} from bucket {bucket}: {str(e)}")
                return self.create_error_response('InternalError', str(e))

        @blueprint.route('/<bucket>', methods=['GET'])
        @handle_s3_errors
        def list_objects(bucket):
            """List objects in a bucket."""
            try:
                prefix = request.args.get('prefix', '')
                delimiter = request.args.get('delimiter', '')
                max_keys = int(request.args.get('max-keys', 1000))
                
                objects = self.fs_manager.list_objects(bucket, prefix, delimiter, max_keys)
                response = {
                    'ListBucketResult': {
                        'Name': bucket,
                        'Prefix': prefix,
                        'Delimiter': delimiter,
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
                return Response(
                    xmltodict.unparse(response),
                    content_type='application/xml'
                )
            except Exception as e:
                logger.error(f"Error listing objects in bucket {bucket}: {str(e)}")
                return self.create_error_response('InternalError', str(e))
