from asyncio.log import logger
from flask import Flask, request, jsonify, Response, make_response
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
from storage_backend import get_storage_backend

app = Flask(__name__)

class S3ApiHandler:
    def __init__(self, fs_manager):
        self.storage = get_storage_backend(fs_manager)

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

    def _success_response(self, body):
        accept = request.headers.get('Accept', '')
        if 'application/json' in accept:
            return jsonify(body)

        xml_str = xmltodict.unparse(body, pretty=True)
        return Response(xml_str, mimetype='application/xml')

    def list_buckets(self):
        buckets = self.storage.list_buckets()
        if isinstance(buckets, tuple):
            buckets, error = buckets
            if error:
                return self._generate_error_response('InternalError', error)

        buckets_list = []
        for bucket_name in buckets:
            # Get bucket metadata from storage
            bucket_data = self.storage.buckets.get(bucket_name, {})
            creation_date = bucket_data.get('creation_date')
            if not creation_date:
                # Fallback to current time if no creation date is stored
                creation_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
            buckets_list.append({
                'Name': bucket_name,
                'CreationDate': creation_date
            })

        response = {
            'ListAllMyBucketsResult': {
                'Buckets': {'Bucket': buckets_list},
                'Owner': {
                    'ID': 'DFSOwner',
                    'DisplayName': 'DFS System'
                }
            }
        }

        # For JSON requests, return a simplified response
        accept = request.headers.get('Accept', '')
        if 'application/json' in accept:
            return jsonify({
                'buckets': buckets_list
            })

        return self._success_response(response)

    def create_bucket(self, bucket_name):
        success, error = self.storage.create_bucket(bucket_name)
        if not success:
            return self._generate_error_response('BucketCreationError', error)
        return '', 200

    def delete_bucket(self, bucket_name):
        success, error = self.storage.delete_bucket(bucket_name)
        if not success:
            return self._generate_error_response('BucketDeletionError', error)
        return '', 204

    def list_objects(self, bucket_name):
        try:
            objects = self.storage.list_objects(bucket_name)
            if isinstance(objects, tuple):
                objects, error = objects
                if error:
                    return self._generate_error_response('InternalError', error)

            if objects is None:
                objects = []

            # Format objects for response
            object_list = []
            for obj in objects:
                if isinstance(obj, dict):
                    # Normalize field names and skip null values
                    formatted_obj = {}
                    if obj.get('Key') or obj.get('key'):
                        formatted_obj['Key'] = obj.get('Key') or obj.get('key')
                    if obj.get('LastModified') or obj.get('last_modified'):
                        formatted_obj['LastModified'] = obj.get('LastModified') or obj.get('last_modified')
                    if obj.get('Size') or obj.get('size', 0):
                        formatted_obj['Size'] = obj.get('Size') or obj.get('size', 0)
                    if obj.get('StorageClass') or obj.get('storage_class'):
                        formatted_obj['StorageClass'] = obj.get('StorageClass') or obj.get('storage_class', 'STANDARD')
                    object_list.append(formatted_obj)
                else:
                    # Handle string or other basic types
                    object_list.append({
                        'Key': str(obj),
                        'LastModified': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'Size': 0,
                        'StorageClass': 'STANDARD'
                    })

            # For JSON requests, return a simplified response
            accept = request.headers.get('Accept', '')
            if 'application/json' in accept:
                return jsonify({
                    'objects': object_list
                })

            # For XML requests, use S3-compatible format
            response = {
                'ListBucketResult': {
                    'Name': bucket_name,
                    'Contents': object_list,
                    'IsTruncated': False
                }
            }
            return self._success_response(response)

        except Exception as e:
            logger.error(f"Error listing objects: {e}")
            return self._generate_error_response('InternalError', str(e))

    def put_object(self, bucket_name, object_key):
        content = request.get_data()
        success, error = self.storage.put_object(bucket_name, object_key, content)
        if not success:
            return self._generate_error_response('PutObjectError', error)

        etag = hashlib.md5(content).hexdigest()
        return '', 200, {'ETag': f'"{etag}"'}

    def get_object(self, bucket_name, object_key):
        content, error = self.storage.get_object(bucket_name, object_key)
        if error:
            return self._generate_error_response('GetObjectError', error)

        headers = {
            'Last-Modified': datetime.datetime.now(datetime.timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'Content-Length': str(len(content)),
            'ETag': f'"{hashlib.md5(content).hexdigest()}"'
        }

        return Response(content, headers=headers)

    def delete_object(self, bucket_name, object_key):
        success, error = self.storage.delete_object(bucket_name, object_key)
        if not success:
            return self._generate_error_response('DeleteObjectError', error)

        # Return empty response with 204 status code
        return '', 204, {'Content-Type': 'application/xml'}

    def get_versioning_status(self, bucket_name):
        """Get versioning status for a bucket"""
        try:
            status = self.storage.get_versioning_status(bucket_name)
            return jsonify({'VersioningEnabled': status})
        except Exception as e:
            return self._generate_error_response('GetVersioningError', str(e))

    def enable_versioning(self, bucket_name):
        """Enable versioning for a bucket"""
        try:
            success, error = self.storage.enable_versioning(bucket_name)
            if not success:
                return self._generate_error_response('EnableVersioningError', error)
            return '', 200
        except Exception as e:
            return self._generate_error_response('EnableVersioningError', str(e))

    def disable_versioning(self, bucket_name):
        """Disable versioning for a bucket"""
        try:
            success, error = self.storage.disable_versioning(bucket_name)
            if not success:
                return self._generate_error_response('DisableVersioningError', error)
            return '', 200
        except Exception as e:
            return self._generate_error_response('DisableVersioningError', str(e))

    def list_object_versions(self, bucket_name, prefix=None):
        """List all versions of objects in a bucket"""
        try:
            versions, error = self.storage.list_object_versions(bucket_name, prefix)
            if error:
                return self._generate_error_response('ListVersionsError', error)

            versions_list = []
            for key, version_list in versions.items():
                for version in version_list:
                    versions_list.append({
                        'Key': key,
                        'VersionId': version['version_id'],
                        'IsLatest': version == version_list[-1],
                        'LastModified': version['last_modified'].isoformat(),
                        'IsDeleteMarker': version.get('is_delete_marker', False)
                    })

            response = {
                'ListVersionsResult': {
                    'Name': bucket_name,
                    'Versions': versions_list
                }
            }
            return self._success_response(response)
        except Exception as e:
            return self._generate_error_response('ListVersionsError', str(e))

@app.route('/buckets', methods=['GET'])
def list_all_buckets():
    """List all buckets in the distributed file system"""
    try:
        storage = get_storage_backend()
        
        # Call list_buckets method
        buckets, error = storage.list_buckets()
        
        # Handle potential errors
        if error:
            logger.error(f"Error listing buckets: {error}")
            if isinstance(error, Response):
                return error
            return jsonify({'error': str(error)}), 400
        
        # Return the bucket list
        if isinstance(buckets, Response):
            return buckets
        
        response = {'buckets': buckets if buckets else []}
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Unexpected error listing buckets: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/<bucket>/<key>', methods=['POST'])
def handle_multipart(bucket, key):
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

@app.route('/<bucket>/<key>', methods=['DELETE'])
def handle_delete_object_or_upload(bucket, key):
    """Handle object deletion or multipart upload abort"""
    storage = get_storage_backend()

    # Abort multipart upload
    upload_id = request.args.get('uploadId')
    if upload_id:
        success, error = storage.abort_multipart_upload(bucket, key, upload_id)
        if error:
            return make_response({'error': error}, 400)
        return make_response('', 204)

    # Delete object (existing functionality)
    success, error = storage.delete_object(bucket, key)
    if error:
        return make_response({'error': error}, 400)
    return make_response('', 204)

@app.route('/<bucket>/<key>', methods=['PUT'])
def handle_put_object_or_complete_upload(bucket, key):
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

    # Regular put object (existing functionality)
    success, error = storage.put_object(bucket, key, request.data)
    if error:
        return make_response({'error': error}, 400)
    return make_response('', 200)

@app.route('/<bucket>', methods=['GET'])
def handle_list_objects_or_uploads(bucket):
    """Handle listing objects or multipart uploads"""
    storage = get_storage_backend()

    # List multipart uploads
    if request.args.get('uploads') is not None:
        uploads, error = storage.list_multipart_uploads(bucket)
        if error:
            return make_response({'error': error}, 400)
        return make_response({'uploads': uploads}, 200)

    # List objects (existing functionality)
    objects, error = storage.list_objects(bucket)
    if error:
        return make_response({'error': error}, 400)
    return make_response({'objects': objects}, 200)

@app.route('/<bucket>/versioning', methods=['GET', 'PUT'])
def handle_bucket_versioning(bucket):
    """Handle bucket versioning operations"""
    storage = get_storage_backend()

    if request.method == 'GET':
        # Get versioning status
        enabled, error = storage.get_versioning_status(bucket)
        if error:
            return make_response({'error': error}, 400)
        return make_response({
            'Status': 'Enabled' if enabled else 'Suspended'
        }, 200)

    elif request.method == 'PUT':
        # Set versioning status
        try:
            config = request.json
            if not config or 'Status' not in config:
                return make_response({'error': 'Missing Status in request'}, 400)

            if config['Status'] == 'Enabled':
                success, error = storage.enable_versioning(bucket)
            elif config['Status'] == 'Suspended':
                success, error = storage.disable_versioning(bucket)
            else:
                return make_response({'error': 'Invalid Status value'}, 400)

            if error:
                return make_response({'error': error}, 400)
            return make_response('', 200)
        except Exception as e:
            return make_response({'error': str(e)}, 400)

@app.route('/<bucket>/<key>', methods=['GET'])
def handle_get_object_or_version(bucket, key):
    """Handle object retrieval, optionally with version"""
    storage = get_storage_backend()

    version_id = request.args.get('versionId')
    if version_id:
        # Get specific version
        data, error = storage.get_object_version(bucket, key, version_id)
    else:
        # Get latest version
        data, error = storage.get_object(bucket, key)

    if error:
        return make_response({'error': error}, 400)
    return Response(data, mimetype='application/octet-stream')

@app.route('/<bucket>', methods=['GET'])
def handle_list_objects_or_versions(bucket):
    """Handle listing objects or versions"""
    storage = get_storage_backend()

    # List versions if versions parameter is present
    if request.args.get('versions') is not None:
        prefix = request.args.get('prefix')
        versions, error = storage.list_object_versions(bucket, prefix)
        if error:
            return make_response({'error': error}, 400)
        return make_response({
            'Versions': versions
        }, 200)

    # List objects (existing functionality)
    objects, error = storage.list_objects(bucket)
    if error:
        return make_response({'error': error}, 400)
    return make_response({'objects': objects}, 200)

@app.route('/<bucket>/<key>', methods=['DELETE'])
def handle_delete_object_or_version(bucket, key):
    """Handle object or version deletion"""
    storage = get_storage_backend()

    version_id = request.args.get('versionId')
    if version_id:
        # Delete specific version
        success, error = storage.delete_object_version(bucket, key, version_id)
    else:
        # Delete latest version (or add delete marker if versioning enabled)
        success, error = storage.delete_object(bucket, key)

    if error:
        return make_response({'error': error}, 400)
    return make_response('', 204)
