from flask_restx import Resource
from flask import request, make_response
import datetime

class BucketList(Resource):
    def __init__(self, api, *args, **kwargs):
        super().__init__(api, *args, **kwargs)
        self.api = api

    @api.doc('list_buckets')
    @api.marshal_list_with(api.models['bucket_model'])
    def get(self):
        """List all buckets"""
        try:
            buckets = fs_manager.list_buckets()
            return buckets
        except Exception as e:
            api.abort(500, str(e))

class BucketOperations(Resource):
    def __init__(self, api, *args, **kwargs):
        super().__init__(api, *args, **kwargs)
        self.api = api

    @api.doc('create_bucket')
    @api.response(201, 'Bucket created')
    def put(self, bucket_name):
        """Create a new bucket"""
        try:
            fs_manager.create_bucket(bucket_name)
            return '', 201
        except Exception as e:
            api.abort(500, str(e))

    @api.doc('delete_bucket')
    @api.response(204, 'Bucket deleted')
    def delete(self, bucket_name):
        """Delete a bucket"""
        try:
            fs_manager.delete_bucket(bucket_name)
            return '', 204
        except Exception as e:
            api.abort(500, str(e))

    @api.doc('list_objects')
    @api.marshal_list_with(api.models['object_model'])
    def get(self, bucket_name):
        """List objects in bucket"""
        try:
            objects = fs_manager.list_objects(bucket_name)
            return objects
        except Exception as e:
            api.abort(500, str(e))

class ObjectOperations(Resource):
    def __init__(self, api, *args, **kwargs):
        super().__init__(api, *args, **kwargs)
        self.api = api

    @api.doc('get_object')
    @api.produces(['application/octet-stream'])
    def get(self, bucket_name, object_key):
        """Download an object"""
        try:
            data = fs_manager.get_object(bucket_name, object_key)
            response = make_response(data)
            response.headers['Content-Type'] = 'application/octet-stream'
            return response
        except Exception as e:
            api.abort(500, str(e))

    @api.doc('put_object')
    @api.response(201, 'Object created')
    @api.expect(api.parser().add_argument('file', location='files', type='file', required=True))
    def put(self, bucket_name, object_key):
        """Upload an object"""
        try:
            file = request.files['file']
            fs_manager.put_object(bucket_name, object_key, file.read())
            return '', 201
        except Exception as e:
            api.abort(500, str(e))

    @api.doc('delete_object')
    @api.response(204, 'Object deleted')
    def delete(self, bucket_name, object_key):
        """Delete an object"""
        try:
            fs_manager.delete_object(bucket_name, object_key)
            return '', 204
        except Exception as e:
            api.abort(500, str(e))

    @api.doc('head_object')
    @api.response(200, 'Object metadata')
    def head(self, bucket_name, object_key):
        """Get object metadata"""
        try:
            metadata = fs_manager.get_object_metadata(bucket_name, object_key)
            response = make_response('')
            response.headers.update(metadata)
            return response
        except Exception as e:
            api.abort(500, str(e))