from flask import Flask, request, jsonify, Response
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os

class S3ApiHandler:
    def __init__(self, fs_manager):
        self.fs_manager = fs_manager
        self.buckets = {}  # In-memory bucket storage for demo. Should be persistent in production.

    def _generate_error_response(self, code, message):
        error = {
            'Error': {
                'Code': code,
                'Message': message,
                'RequestId': hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()
            }
        }
        return xmltodict.unparse(error), 400

    def _success_response(self, body):
        return xmltodict.unparse(body), 200, {'Content-Type': 'application/xml'}

    def list_buckets(self):
        buckets_list = []
        for bucket_name in self.buckets:
            buckets_list.append({
                'Name': bucket_name,
                'CreationDate': self.buckets[bucket_name]['creation_date'].isoformat()
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
        return self._success_response(response)

    def create_bucket(self, bucket_name):
        if bucket_name in self.buckets:
            return self._generate_error_response('BucketAlreadyExists',
                                              f'Bucket {bucket_name} already exists')

        self.buckets[bucket_name] = {
            'creation_date': datetime.datetime.now(datetime.timezone.utc),
            'objects': {}
        }

        # Create directory structure in DFS
        self.fs_manager.createDirectory(f'/{bucket_name}')

        return '', 200

    def delete_bucket(self, bucket_name):
        if bucket_name not in self.buckets:
            return self._generate_error_response('NoSuchBucket',
                                              f'Bucket {bucket_name} does not exist')

        if self.buckets[bucket_name]['objects']:
            return self._generate_error_response('BucketNotEmpty',
                                              'Cannot delete non-empty bucket')

        del self.buckets[bucket_name]
        self.fs_manager.deleteDirectory(f'/{bucket_name}')
        return '', 204

    def list_objects(self, bucket_name):
        if bucket_name not in self.buckets:
            return self._generate_error_response('NoSuchBucket',
                                              f'Bucket {bucket_name} does not exist')

        objects_list = []
        for obj_key, obj_data in self.buckets[bucket_name]['objects'].items():
            objects_list.append({
                'Key': obj_key,
                'LastModified': obj_data['last_modified'].isoformat(),
                'Size': obj_data['size'],
                'StorageClass': 'STANDARD'
            })

        response = {
            'ListBucketResult': {
                'Name': bucket_name,
                'Contents': objects_list
            }
        }
        return self._success_response(response)

    def put_object(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return self._generate_error_response('NoSuchBucket',
                                              f'Bucket {bucket_name} does not exist')

        content = request.get_data()
        size = len(content)

        # Store in DFS
        success = self.fs_manager.writeFile(f'/{bucket_name}/{object_key}', content)
        if not success:
            return self._generate_error_response('InternalError',
                                              'Failed to store object')

        # Update metadata
        self.buckets[bucket_name]['objects'][object_key] = {
            'last_modified': datetime.datetime.now(datetime.timezone.utc),
            'size': size
        }

        etag = hashlib.md5(content).hexdigest()
        return '', 200, {'ETag': f'"{etag}"'}

    def get_object(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return self._generate_error_response('NoSuchBucket',
                                              f'Bucket {bucket_name} does not exist')

        if object_key not in self.buckets[bucket_name]['objects']:
            return self._generate_error_response('NoSuchKey',
                                              f'Object {object_key} does not exist')

        content = self.fs_manager.readFile(f'/{bucket_name}/{object_key}')
        if not content:
            return self._generate_error_response('InternalError',
                                              'Failed to retrieve object')

        obj_data = self.buckets[bucket_name]['objects'][object_key]
        headers = {
            'Last-Modified': obj_data['last_modified'].strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'Content-Length': str(obj_data['size']),
            'ETag': f'"{hashlib.md5(content).hexdigest()}"'
        }

        return Response(content, headers=headers)

    def delete_object(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return self._generate_error_response('NoSuchBucket',
                                              f'Bucket {bucket_name} does not exist')

        if object_key not in self.buckets[bucket_name]['objects']:
            return self._generate_error_response('NoSuchKey',
                                              f'Object {object_key} does not exist')

        success = self.fs_manager.deleteFile(f'/{bucket_name}/{object_key}')
        if not success:
            return self._generate_error_response('InternalError',
                                              'Failed to delete object')

        del self.buckets[bucket_name]['objects'][object_key]
        return '', 204
