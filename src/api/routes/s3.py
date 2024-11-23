"""S3-compatible API routes"""
from flask import request, jsonify, Response, make_response, Blueprint
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
import sys

# Add the src directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.core.storage_backend import get_storage_backend
from api.core.fs_manager import FileSystemManager

logger = logging.getLogger(__name__)

# Create Blueprint for S3 API routes
s3_api = Blueprint('s3_api', __name__)

class S3ApiHandler:
    def __init__(self, fs_manager):
        self.storage = get_storage_backend(fs_manager)
        self.register_routes()

    def register_routes(self):
        s3_api.add_url_rule('/buckets', 'list_buckets', self.list_buckets, methods=['GET'])
        s3_api.add_url_rule('/<bucket>/<key>', 'handle_multipart', self.handle_multipart, methods=['POST'])
        s3_api.add_url_rule('/<bucket>/<key>', 'handle_delete_object_or_upload', self.handle_delete_object_or_upload, methods=['DELETE'])
        s3_api.add_url_rule('/<bucket>/<key>', 'handle_put_object_or_complete_upload', self.handle_put_object_or_complete_upload, methods=['PUT'])
        s3_api.add_url_rule('/<bucket>', 'handle_list_objects_or_uploads', self.handle_list_objects_or_uploads, methods=['GET'])
        s3_api.add_url_rule('/<bucket>/versioning', 'handle_bucket_versioning', self.handle_bucket_versioning, methods=['GET', 'PUT'])
        s3_api.add_url_rule('/<bucket>/<key>', 'handle_get_object_or_version', self.handle_get_object_or_version, methods=['GET'])
        s3_api.add_url_rule('/<bucket>', 'handle_list_objects_or_versions', self.handle_list_objects_or_versions, methods=['GET'])
        s3_api.add_url_rule('/<bucket>/<key>', 'handle_delete_object_or_version', self.handle_delete_object_or_version, methods=['DELETE'])
        s3_api.add_url_rule('/<bucket>', 'list_all_buckets', self.list_all_buckets, methods=['GET'])
        s3_api.add_url_rule('/<bucket>/<key>', 'list_objects', self.list_objects, methods=['GET'])
        s3_api.add_url_rule('/<bucket>', 'create_bucket', self.create_bucket, methods=['PUT'])
        s3_api.add_url_rule('/<bucket>', 'delete_bucket', self.delete_bucket, methods=['DELETE'])
        s3_api.add_url_rule('/<bucket>/<key>', 'put_object', self.put_object, methods=['PUT'])
        s3_api.add_url_rule('/<bucket>/<key>', 'get_object', self.get_object, methods=['GET'])
        s3_api.add_url_rule('/<bucket>/<key>', 'delete_object', self.delete_object, methods=['DELETE'])
        s3_api.add_url_rule('/<bucket>/versioning', 'get_versioning_status', self.get_versioning_status, methods=['GET'])
        s3_api.add_url_rule('/<bucket>/versioning', 'enable_versioning', self.enable_versioning, methods=['PUT'])
        s3_api.add_url_rule('/<bucket>/versioning', 'disable_versioning', self.disable_versioning, methods=['DELETE'])
        s3_api.add_url_rule('/<bucket>', 'list_object_versions', self.list_object_versions, methods=['GET'])

    def _generate_error_response(self, code, message):
        error = {
            'Error': {
                'Code': code,
                'Message': message,
                'RequestId': hashlib.md5(datetime.datetime.now(datetime.timezone.utc).isoformat().encode()).hexdigest()
            }
        }

        accept = request.headers.get('Accept', '')
        if 'application/json' in accept:
            return jsonify({'error': message}), 400

        return xmltodict.unparse(error, pretty=True), 400, {'Content-Type': 'application/xml'}

    def list_buckets(self):
        """List all buckets in the distributed file system"""
        try:
            buckets, error = self.storage.list_buckets()

            if error:
                logger.error(f"Error listing buckets: {error}")
                return jsonify({'error': str(error)}), 400

            response = {'buckets': buckets if buckets else []}
            return jsonify(response), 200

        except Exception as e:
            logger.error(f"Unexpected error listing buckets: {str(e)}")
            return jsonify({'error': str(e)}), 500

    def handle_multipart(self, bucket, key):
        """Handle multipart upload operations"""
        storage = get_storage_backend()

        # Create multipart upload
        if request.args.get('uploads') is not None:
            upload_id, error = storage.create_multipart_upload(bucket, key)
            if error:
                return make_response({'error': error}, 400)
            return make_response({
                'bucket': bucket,
                'key': key,
                'upload_id': upload_id
            }, 200)

        # Upload part
        upload_id = request.args.get('uploadId')
        part_number = request.args.get('partNumber')
        if upload_id and part_number:
            try:
                part_number = int(part_number)
                if not (1 <= part_number <= 10000):
                    return make_response({'error': 'Part number must be between 1 and 10000'}, 400)
            except ValueError:
                return make_response({'error': 'Invalid part number'}, 400)

            etag, error = storage.upload_part(bucket, key, upload_id, part_number, request.data)
            if error:
                return make_response({'error': error}, 400)
            return make_response({'ETag': etag}, 200)

        return make_response({'error': 'Invalid multipart upload request'}, 400)

    def handle_delete_object_or_upload(self, bucket, key):
        """Handle object deletion or multipart upload abort"""
        storage = get_storage_backend()

        # Abort multipart upload
        upload_id = request.args.get('uploadId')
        if upload_id:
            success, error = storage.abort_multipart_upload(bucket, key, upload_id)
            if error:
                return make_response({'error': error}, 400)
            return make_response('', 204)

        # Delete object
        success, error = storage.delete_object(bucket, key)
        if error:
            return make_response({'error': error}, 400)
        return make_response('', 204)

    def handle_put_object_or_complete_upload(self, bucket, key):
        """Handle object upload or multipart upload completion"""
        storage = get_storage_backend()

        # Complete multipart upload
        upload_id = request.args.get('uploadId')
        if upload_id:
            try:
                completion_data = request.json
                if not completion_data or 'parts' not in completion_data:
                    return make_response({'error': 'Missing parts list'}, 400)

                success, error = storage.complete_multipart_upload(
                    bucket, key, upload_id, completion_data['parts']
                )
                if error:
                    return make_response({'error': error}, 400)
                return make_response('', 200)
            except Exception as e:
                return make_response({'error': str(e)}, 400)

        # Regular put object
        success, error = storage.put_object(bucket, key, request.data)
        if error:
            return make_response({'error': error}, 400)
        return make_response('', 200)

    def handle_list_objects_or_uploads(self, bucket):
        """Handle listing objects or multipart uploads in a bucket"""
        try:
            # Check if we're listing multipart uploads
            if request.args.get('uploads') is not None:
                uploads = self.storage.list_multipart_uploads(bucket)
                return jsonify({
                    'bucket': bucket,
                    'uploads': uploads
                }), 200

            # Otherwise, list objects
            objects = self.storage.list_objects(bucket)
            return jsonify({
                'bucket': bucket,
                'objects': objects
            }), 200

        except Exception as e:
            logger.error(f"Error listing objects or uploads for bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def handle_bucket_versioning(self, bucket):
        """Handle bucket versioning"""
        try:
            if request.method == 'GET':
                versioning_status = self.storage.get_versioning_status(bucket)
                return jsonify({
                    'bucket': bucket,
                    'versioning': versioning_status
                }), 200

            elif request.method == 'PUT':
                versioning_status = request.json.get('versioning')
                if versioning_status is None:
                    return self._generate_error_response('InvalidRequest', 'Missing versioning status')

                success, error = self.storage.enable_versioning(bucket, versioning_status)
                if error:
                    return self._generate_error_response('InternalError', error)

                return jsonify({
                    'bucket': bucket,
                    'versioning': versioning_status
                }), 200

        except Exception as e:
            logger.error(f"Error handling bucket versioning for bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def handle_get_object_or_version(self, bucket, key):
        """Handle getting an object or a specific version"""
        try:
            version_id = request.args.get('versionId')
            if version_id:
                object_data, error = self.storage.get_object(bucket, key, version_id)
                if error:
                    return self._generate_error_response('InternalError', error)

                return Response(object_data, mimetype='application/octet-stream'), 200

            object_data, error = self.storage.get_object(bucket, key)
            if error:
                return self._generate_error_response('InternalError', error)

            return Response(object_data, mimetype='application/octet-stream'), 200

        except Exception as e:
            logger.error(f"Error getting object or version for bucket {bucket} and key {key}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def handle_list_objects_or_versions(self, bucket):
        """Handle listing objects or versions in a bucket"""
        try:
            if request.args.get('versions') is not None:
                versions = self.storage.list_object_versions(bucket)
                return jsonify({
                    'bucket': bucket,
                    'versions': versions
                }), 200

            objects = self.storage.list_objects(bucket)
            return jsonify({
                'bucket': bucket,
                'objects': objects
            }), 200

        except Exception as e:
            logger.error(f"Error listing objects or versions for bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def handle_delete_object_or_version(self, bucket, key):
        """Handle deleting an object or a specific version"""
        try:
            version_id = request.args.get('versionId')
            if version_id:
                success, error = self.storage.delete_object(bucket, key, version_id)
                if error:
                    return self._generate_error_response('InternalError', error)

                return make_response('', 204)

            success, error = self.storage.delete_object(bucket, key)
            if error:
                return self._generate_error_response('InternalError', error)

            return make_response('', 204)

        except Exception as e:
            logger.error(f"Error deleting object or version for bucket {bucket} and key {key}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def list_all_buckets(self, bucket):
        """List all buckets in the distributed file system"""
        try:
            buckets, error = self.storage.list_buckets()

            if error:
                logger.error(f"Error listing buckets: {error}")
                return jsonify({'error': str(error)}), 400

            response = {'buckets': buckets if buckets else []}
            return jsonify(response), 200

        except Exception as e:
            logger.error(f"Unexpected error listing buckets: {str(e)}")
            return jsonify({'error': str(e)}), 500

    def list_objects(self, bucket, key):
        """List objects in a bucket"""
        try:
            objects = self.storage.list_objects(bucket)
            return jsonify({
                'bucket': bucket,
                'objects': objects
            }), 200

        except Exception as e:
            logger.error(f"Error listing objects for bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def create_bucket(self, bucket):
        """Create a new bucket"""
        try:
            success, error = self.storage.create_bucket(bucket)
            if error:
                return self._generate_error_response('InternalError', error)

            return make_response('', 201)

        except Exception as e:
            logger.error(f"Error creating bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def delete_bucket(self, bucket):
        """Delete a bucket"""
        try:
            success, error = self.storage.delete_bucket(bucket)
            if error:
                return self._generate_error_response('InternalError', error)

            return make_response('', 204)

        except Exception as e:
            logger.error(f"Error deleting bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def put_object(self, bucket, key):
        """Put an object in a bucket"""
        try:
            success, error = self.storage.put_object(bucket, key, request.data)
            if error:
                return self._generate_error_response('InternalError', error)

            return make_response('', 200)

        except Exception as e:
            logger.error(f"Error putting object in bucket {bucket} and key {key}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def get_object(self, bucket, key):
        """Get an object from a bucket"""
        try:
            object_data, error = self.storage.get_object(bucket, key)
            if error:
                return self._generate_error_response('InternalError', error)

            return Response(object_data, mimetype='application/octet-stream'), 200

        except Exception as e:
            logger.error(f"Error getting object from bucket {bucket} and key {key}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def delete_object(self, bucket, key):
        """Delete an object from a bucket"""
        try:
            success, error = self.storage.delete_object(bucket, key)
            if error:
                return self._generate_error_response('InternalError', error)

            return make_response('', 204)

        except Exception as e:
            logger.error(f"Error deleting object from bucket {bucket} and key {key}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def get_versioning_status(self, bucket):
        """Get the versioning status of a bucket"""
        try:
            versioning_status = self.storage.get_versioning_status(bucket)
            return jsonify({
                'bucket': bucket,
                'versioning': versioning_status
            }), 200

        except Exception as e:
            logger.error(f"Error getting versioning status for bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def enable_versioning(self, bucket):
        """Enable versioning for a bucket"""
        try:
            success, error = self.storage.enable_versioning(bucket)
            if error:
                return self._generate_error_response('InternalError', error)

            return jsonify({
                'bucket': bucket,
                'versioning': 'Enabled'
            }), 200

        except Exception as e:
            logger.error(f"Error enabling versioning for bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def disable_versioning(self, bucket):
        """Disable versioning for a bucket"""
        try:
            success, error = self.storage.disable_versioning(bucket)
            if error:
                return self._generate_error_response('InternalError', error)

            return jsonify({
                'bucket': bucket,
                'versioning': 'Disabled'
            }), 200

        except Exception as e:
            logger.error(f"Error disabling versioning for bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))

    def list_object_versions(self, bucket):
        """List object versions in a bucket"""
        try:
            versions = self.storage.list_object_versions(bucket)
            return jsonify({
                'bucket': bucket,
                'versions': versions
            }), 200

        except Exception as e:
            logger.error(f"Error listing object versions for bucket {bucket}: {str(e)}")
            return self._generate_error_response('InternalError', str(e))
