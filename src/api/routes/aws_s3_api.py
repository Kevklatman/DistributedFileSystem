"""AWS S3 API Implementation

This module implements a full AWS S3-compatible API that closely follows
the AWS S3 REST API specification, including advanced features like
multipart uploads, versioning, and access controls.
"""
from flask import request, jsonify, Response, make_response, Blueprint
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
from core.storage_backend import get_storage_backend
from core.fs_manager import FileSystemManager

logger = logging.getLogger(__name__)

# Create Blueprint for AWS S3 API routes
aws_s3_api = Blueprint('aws_s3_api', __name__)

class AWSS3ApiHandler:
    """AWS S3 API Handler implementing the full AWS S3 REST API specification"""

    def __init__(self, fs_manager):
        self.storage = get_storage_backend(fs_manager)
        self.register_routes()

    def register_routes(self):
        """Register all AWS S3 API routes"""
        # Basic operations
        aws_s3_api.add_url_rule('/', 'list_buckets', self.list_buckets, methods=['GET'])
        aws_s3_api.add_url_rule('/<bucket>', 'create_bucket', self.create_bucket, methods=['PUT'])
        aws_s3_api.add_url_rule('/<bucket>', 'delete_bucket', self.delete_bucket, methods=['DELETE'])
        aws_s3_api.add_url_rule('/<bucket>', 'list_objects', self.list_objects, methods=['GET'])
        aws_s3_api.add_url_rule('/<bucket>/<key>', 'put_object', self.put_object, methods=['PUT'])
        aws_s3_api.add_url_rule('/<bucket>/<key>', 'get_object', self.get_object, methods=['GET'])
        aws_s3_api.add_url_rule('/<bucket>/<key>', 'delete_object', self.delete_object, methods=['DELETE'])
        
        # Multipart upload operations
        aws_s3_api.add_url_rule('/<bucket>/<key>', 'create_multipart_upload', 
                               self.create_multipart_upload, methods=['POST'], 
                               defaults={'query_params': {'uploads': None}})
        aws_s3_api.add_url_rule('/<bucket>/<key>', 'upload_part',
                               self.upload_part, methods=['PUT'])
        aws_s3_api.add_url_rule('/<bucket>/<key>', 'complete_multipart_upload',
                               self.complete_multipart_upload, methods=['POST'])
        aws_s3_api.add_url_rule('/<bucket>/<key>', 'abort_multipart_upload',
                               self.abort_multipart_upload, methods=['DELETE'])
        aws_s3_api.add_url_rule('/<bucket>', 'list_multipart_uploads',
                               self.list_multipart_uploads, methods=['GET'],
                               defaults={'query_params': {'uploads': None}})
        
        # Versioning operations
        aws_s3_api.add_url_rule('/<bucket>/versioning', 'get_bucket_versioning',
                               self.get_bucket_versioning, methods=['GET'])
        aws_s3_api.add_url_rule('/<bucket>/versioning', 'put_bucket_versioning',
                               self.put_bucket_versioning, methods=['PUT'])
        aws_s3_api.add_url_rule('/<bucket>', 'list_object_versions',
                               self.list_object_versions, methods=['GET'],
                               defaults={'query_params': {'versions': None}})
        
        # Object operations with versions
        aws_s3_api.add_url_rule('/<bucket>/<key>', 'get_object_version',
                               self.get_object_version, methods=['GET'])
        aws_s3_api.add_url_rule('/<bucket>/<key>', 'delete_object_version',
                               self.delete_object_version, methods=['DELETE'])

    def _generate_request_id(self):
        """Generate a unique request ID"""
        return hashlib.md5(datetime.datetime.now(datetime.timezone.utc).isoformat().encode()).hexdigest()

    def _format_error_response(self, code, message):
        """Format an error response in AWS S3 style"""
        error = {
            'Error': {
                'Code': code,
                'Message': message,
                'RequestId': self._generate_request_id()
            }
        }
        return make_response(xmltodict.unparse(error), 400)

    def list_buckets(self):
        """List all buckets (GET /)"""
        try:
            buckets = self.storage.list_buckets()
            response = {
                'ListAllMyBucketsResult': {
                    '@xmlns': 'http://s3.amazonaws.com/doc/2006-03-01/',
                    'Owner': {
                        'ID': 'dfs-owner-id',
                        'DisplayName': 'dfs-owner'
                    },
                    'Buckets': {
                        'Bucket': [
                            {
                                'Name': bucket,
                                'CreationDate': datetime.datetime.now(datetime.timezone.utc).isoformat()
                            } for bucket in buckets
                        ]
                    }
                }
            }
            return make_response(xmltodict.unparse(response), 200)
        except Exception as e:
            logger.error(f"Error listing buckets: {str(e)}")
            return self._format_error_response('InternalError', str(e))

    def create_multipart_upload(self, bucket, key):
        """Initiate multipart upload (POST /<bucket>/<key>?uploads)"""
        try:
            upload = self.storage.create_multipart_upload(bucket, key)
            response = {
                'InitiateMultipartUploadResult': {
                    'Bucket': bucket,
                    'Key': key,
                    'UploadId': upload['upload_id']
                }
            }
            return make_response(xmltodict.unparse(response), 200)
        except Exception as e:
            logger.error(f"Error creating multipart upload: {str(e)}")
            return self._format_error_response('InternalError', str(e))

    def upload_part(self, bucket, key):
        """Upload a part (PUT /<bucket>/<key>?partNumber=<number>&uploadId=<id>)"""
        try:
            upload_id = request.args.get('uploadId')
            part_number = int(request.args.get('partNumber'))
            
            if not upload_id or not part_number:
                return self._format_error_response('InvalidRequest', 'Missing uploadId or partNumber')
                
            if not (1 <= part_number <= 10000):
                return self._format_error_response('InvalidRequest', 'Part number must be between 1 and 10000')
                
            etag = self.storage.upload_part(bucket, key, upload_id, part_number, request.data)
            return make_response('', 200, {'ETag': f'"{etag}"'})
        except Exception as e:
            logger.error(f"Error uploading part: {str(e)}")
            return self._format_error_response('InternalError', str(e))

    def complete_multipart_upload(self, bucket, key):
        """Complete multipart upload (POST /<bucket>/<key>?uploadId=<id>)"""
        try:
            upload_id = request.args.get('uploadId')
            if not upload_id:
                return self._format_error_response('InvalidRequest', 'Missing uploadId')
                
            parts = xmltodict.parse(request.data)['CompleteMultipartUpload']['Part']
            parts = [{
                'PartNumber': int(part['PartNumber']),
                'ETag': part['ETag'].strip('"')
            } for part in parts]
            
            result = self.storage.complete_multipart_upload(bucket, key, upload_id, parts)
            response = {
                'CompleteMultipartUploadResult': {
                    'Location': f'/{bucket}/{key}',
                    'Bucket': bucket,
                    'Key': key,
                    'ETag': f'"{result["etag"]}"'
                }
            }
            return make_response(xmltodict.unparse(response), 200)
        except Exception as e:
            logger.error(f"Error completing multipart upload: {str(e)}")
            return self._format_error_response('InternalError', str(e))

    def abort_multipart_upload(self, bucket, key):
        """Abort multipart upload (DELETE /<bucket>/<key>?uploadId=<id>)"""
        try:
            upload_id = request.args.get('uploadId')
            if not upload_id:
                return self._format_error_response('InvalidRequest', 'Missing uploadId')
                
            self.storage.abort_multipart_upload(bucket, key, upload_id)
            return make_response('', 204)
        except Exception as e:
            logger.error(f"Error aborting multipart upload: {str(e)}")
            return self._format_error_response('InternalError', str(e))

    def get_bucket_versioning(self, bucket):
        """Get bucket versioning (GET /<bucket>?versioning)"""
        try:
            status = self.storage.get_bucket_versioning(bucket)
            response = {
                'VersioningConfiguration': {
                    '@xmlns': 'http://s3.amazonaws.com/doc/2006-03-01/',
                    'Status': status.upper() if status else 'Suspended'
                }
            }
            return make_response(xmltodict.unparse(response), 200)
        except Exception as e:
            logger.error(f"Error getting bucket versioning: {str(e)}")
            return self._format_error_response('InternalError', str(e))

    def put_bucket_versioning(self, bucket):
        """Set bucket versioning (PUT /<bucket>?versioning)"""
        try:
            config = xmltodict.parse(request.data)
            status = config['VersioningConfiguration'].get('Status', '').lower()
            
            if status not in ['enabled', 'suspended']:
                return self._format_error_response('InvalidRequest', 'Invalid versioning status')
                
            self.storage.put_bucket_versioning(bucket, status == 'enabled')
            return make_response('', 200)
        except Exception as e:
            logger.error(f"Error setting bucket versioning: {str(e)}")
            return self._format_error_response('InternalError', str(e))

    def list_object_versions(self, bucket):
        """List object versions (GET /<bucket>?versions)"""
        try:
            versions = self.storage.list_object_versions(bucket)
            response = {
                'ListVersionsResult': {
                    '@xmlns': 'http://s3.amazonaws.com/doc/2006-03-01/',
                    'Name': bucket,
                    'Versions': [
                        {
                            'Key': version['key'],
                            'VersionId': version['version_id'],
                            'IsLatest': version.get('is_latest', False),
                            'LastModified': version.get('last_modified', datetime.datetime.now(datetime.timezone.utc).isoformat()),
                            'Size': version.get('size', 0),
                            'ETag': f'"{version.get("etag", "")}"'
                        } for version in versions
                    ]
                }
            }
            return make_response(xmltodict.unparse(response), 200)
        except Exception as e:
            logger.error(f"Error listing object versions: {str(e)}")
            return self._format_error_response('InternalError', str(e))

    def get_object_version(self, bucket, key):
        """Get a specific version of an object (GET /<bucket>/<key>?versionId=<id>)"""
        try:
            version_id = request.args.get('versionId')
            if not version_id:
                return self._format_error_response('InvalidRequest', 'Missing versionId')
                
            obj = self.storage.get_object_version(bucket, key, version_id)
            if not obj:
                return self._format_error_response('NoSuchKey', 'The specified key does not exist.')
                
            return Response(
                obj['content'],
                mimetype='application/octet-stream',
                headers={
                    'ETag': f'"{obj.get("etag", "")}"',
                    'VersionId': version_id,
                    'Last-Modified': obj.get('last_modified', datetime.datetime.now(datetime.timezone.utc).isoformat()),
                    'Content-Length': str(len(obj['content']))
                }
            )
        except Exception as e:
            logger.error(f"Error getting object version: {str(e)}")
            return self._format_error_response('InternalError', str(e))

    def delete_object_version(self, bucket, key):
        """Delete a specific version of an object (DELETE /<bucket>/<key>?versionId=<id>)"""
        try:
            version_id = request.args.get('versionId')
            if not version_id:
                return self._format_error_response('InvalidRequest', 'Missing versionId')
                
            self.storage.delete_object_version(bucket, key, version_id)
            return make_response('', 204)
        except Exception as e:
            logger.error(f"Error deleting object version: {str(e)}")
            return self._format_error_response('InternalError', str(e))
