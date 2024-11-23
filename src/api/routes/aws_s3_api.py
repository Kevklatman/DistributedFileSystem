"""AWS S3 API Implementation

This module implements a full AWS S3-compatible API that closely follows
the AWS S3 REST API specification, including advanced features like
multipart uploads, versioning, and access controls.
"""
from flask import request, Response, make_response, Blueprint
import datetime
import logging
from ..services.utils import (
    parse_xml_request,
    parse_multipart_complete,
    parse_versioning_config,
    format_error_response,
    handle_s3_errors
)
from .base import BaseS3Handler

logger = logging.getLogger(__name__)

# Create Blueprint for AWS S3 API routes
aws_s3_api = Blueprint('aws_s3_api', __name__)

class AWSS3ApiHandler(BaseS3Handler):
    """AWS S3 API Handler implementing advanced S3 features."""
    
    def __init__(self, fs_manager):
        """Initialize the handler with full AWS S3 functionality."""
        super().__init__(fs_manager, aws_style=True)
        self.register_routes()
    
    def register_routes(self):
        """Register all AWS S3 API routes"""
        # Register basic routes from base handler
        self.register_basic_routes(aws_s3_api)
        
        # Multipart upload operations
        aws_s3_api.add_url_rule(
            '/<bucket>/<key>',
            'create_multipart_upload',
            self.create_multipart_upload,
            methods=['POST'],
            defaults={'query_params': {'uploads': None}}
        )
        aws_s3_api.add_url_rule(
            '/<bucket>/<key>',
            'upload_part',
            self.upload_part,
            methods=['PUT']
        )
        aws_s3_api.add_url_rule(
            '/<bucket>/<key>',
            'complete_multipart_upload',
            self.complete_multipart_upload,
            methods=['POST']
        )
        aws_s3_api.add_url_rule(
            '/<bucket>/<key>',
            'abort_multipart_upload',
            self.abort_multipart_upload,
            methods=['DELETE']
        )
        aws_s3_api.add_url_rule(
            '/<bucket>',
            'list_multipart_uploads',
            self.list_multipart_uploads,
            methods=['GET'],
            defaults={'query_params': {'uploads': None}}
        )
        
        # Versioning operations
        aws_s3_api.add_url_rule(
            '/<bucket>/versioning',
            'get_bucket_versioning',
            self.get_bucket_versioning,
            methods=['GET']
        )
        aws_s3_api.add_url_rule(
            '/<bucket>/versioning',
            'put_bucket_versioning',
            self.put_bucket_versioning,
            methods=['PUT']
        )
        aws_s3_api.add_url_rule(
            '/<bucket>',
            'list_object_versions',
            self.list_object_versions,
            methods=['GET'],
            defaults={'query_params': {'versions': None}}
        )
        
        # Object operations with versions
        aws_s3_api.add_url_rule(
            '/<bucket>/<key>',
            'get_object_version',
            self.get_object_version,
            methods=['GET']
        )
        aws_s3_api.add_url_rule(
            '/<bucket>/<key>',
            'delete_object_version',
            self.delete_object_version,
            methods=['DELETE']
        )
    
    @handle_s3_errors(aws_style=True)
    def create_multipart_upload(self, bucket, key):
        """Initiate multipart upload (POST /<bucket>/<key>?uploads)"""
        upload = self.storage.create_multipart_upload(bucket, key)
        response = {
            'InitiateMultipartUploadResult': {
                'Bucket': bucket,
                'Key': key,
                'UploadId': upload['upload_id']
            }
        }
        return make_response(xmltodict.unparse(response), 200)
    
    @handle_s3_errors(aws_style=True)
    def upload_part(self, bucket, key):
        """Upload a part (PUT /<bucket>/<key>?partNumber=<number>&uploadId=<id>)"""
        upload_id = request.args.get('uploadId')
        part_number = int(request.args.get('partNumber'))
        
        if not upload_id or not part_number:
            return format_error_response('InvalidRequest', 'Missing uploadId or partNumber', True)
            
        if not (1 <= part_number <= 10000):
            return format_error_response('InvalidRequest', 'Part number must be between 1 and 10000', True)
            
        etag = self.storage.upload_part(bucket, key, upload_id, part_number, request.data)
        return make_response('', 200, {'ETag': f'"{etag}"'})
    
    @handle_s3_errors(aws_style=True)
    def complete_multipart_upload(self, bucket, key):
        """Complete multipart upload (POST /<bucket>/<key>?uploadId=<id>)"""
        upload_id = request.args.get('uploadId')
        if not upload_id:
            return format_error_response('InvalidRequest', 'Missing uploadId', True)
            
        data = parse_xml_request()
        parts = parse_multipart_complete(data)
        
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
    
    @handle_s3_errors(aws_style=True)
    def abort_multipart_upload(self, bucket, key):
        """Abort multipart upload (DELETE /<bucket>/<key>?uploadId=<id>)"""
        upload_id = request.args.get('uploadId')
        if not upload_id:
            return format_error_response('InvalidRequest', 'Missing uploadId', True)
            
        self.storage.abort_multipart_upload(bucket, key, upload_id)
        return make_response('', 204)
    
    @handle_s3_errors(aws_style=True)
    def list_multipart_uploads(self, bucket):
        """List multipart uploads (GET /<bucket>?uploads)"""
        uploads = self.storage.list_multipart_uploads(bucket)
        response = {
            'ListMultipartUploadsResult': {
                '@xmlns': 'http://s3.amazonaws.com/doc/2006-03-01/',
                'Bucket': bucket,
                'Upload': [
                    {
                        'Key': upload['key'],
                        'UploadId': upload['upload_id'],
                        'Initiated': upload.get('initiated', datetime.datetime.now(datetime.timezone.utc).isoformat())
                    } for upload in uploads
                ]
            }
        }
        return make_response(xmltodict.unparse(response), 200)
    
    @handle_s3_errors(aws_style=True)
    def get_bucket_versioning(self, bucket):
        """Get bucket versioning (GET /<bucket>?versioning)"""
        status = self.storage.get_bucket_versioning(bucket)
        response = {
            'VersioningConfiguration': {
                '@xmlns': 'http://s3.amazonaws.com/doc/2006-03-01/',
                'Status': status.upper() if status else 'Suspended'
            }
        }
        return make_response(xmltodict.unparse(response), 200)
    
    @handle_s3_errors(aws_style=True)
    def put_bucket_versioning(self, bucket):
        """Set bucket versioning (PUT /<bucket>?versioning)"""
        data = parse_xml_request()
        status = parse_versioning_config(data)
        self.storage.put_bucket_versioning(bucket, status == 'enabled')
        return make_response('', 200)
    
    @handle_s3_errors(aws_style=True)
    def list_object_versions(self, bucket):
        """List object versions (GET /<bucket>?versions)"""
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
    
    @handle_s3_errors(aws_style=True)
    def get_object_version(self, bucket, key):
        """Get a specific version of an object (GET /<bucket>/<key>?versionId=<id>)"""
        version_id = request.args.get('versionId')
        if not version_id:
            return format_error_response('InvalidRequest', 'Missing versionId', True)
            
        obj = self.storage.get_object_version(bucket, key, version_id)
        if not obj:
            return format_error_response('NoSuchKey', 'The specified key does not exist.', True)
            
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
    
    @handle_s3_errors(aws_style=True)
    def delete_object_version(self, bucket, key):
        """Delete a specific version of an object (DELETE /<bucket>/<key>?versionId=<id>)"""
        version_id = request.args.get('versionId')
        if not version_id:
            return format_error_response('InvalidRequest', 'Missing versionId', True)
            
        self.storage.delete_object_version(bucket, key, version_id)
        return make_response('', 204)
