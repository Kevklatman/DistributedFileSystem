from flask import Flask, request, jsonify, Response
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
from storage_backend import get_storage_backend

class S3ApiHandler:
    def __init__(self, fs_manager):
        self.storage = get_storage_backend(fs_manager)

    def _generate_error_response(self, code, message):
        error = {
            'Error': {
                'Code': code,
                'Message': message,
                'RequestId': hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()
            }
        }
        return xmltodict.unparse(error, pretty=True), 400, {'Content-Type': 'application/xml'}

    def _success_response(self, body):
        return xmltodict.unparse(body, pretty=True), 200, {'Content-Type': 'application/xml'}

    def list_buckets(self):
        buckets = self.storage.list_buckets()
        if isinstance(buckets, tuple):
            buckets, error = buckets
            if error:
                return self._generate_error_response('InternalError', error)

        buckets_list = [{'Name': name, 'CreationDate': datetime.datetime.now(datetime.timezone.utc).isoformat()} 
                       for name in buckets]

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
        objects, error = self.storage.list_objects(bucket_name)
        if error:
            return self._generate_error_response('ListObjectsError', error)

        objects_list = [{
            'Key': key,
            'LastModified': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'Size': 0,  # Size information might not be available
            'StorageClass': 'STANDARD'
        } for key in objects]

        response = {
            'ListBucketResult': {
                'Name': bucket_name,
                'Contents': objects_list
            }
        }
        return self._success_response(response)

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
        return '', 204
