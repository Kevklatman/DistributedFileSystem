from abc import ABC, abstractmethod
import boto3
from botocore.client import Config
from config import current_config, STORAGE_ENV

class StorageBackend(ABC):
    @abstractmethod
    def create_bucket(self, bucket_name):
        pass

    @abstractmethod
    def delete_bucket(self, bucket_name):
        pass

    @abstractmethod
    def list_buckets(self):
        pass

    @abstractmethod
    def put_object(self, bucket_name, object_key, data):
        pass

    @abstractmethod
    def get_object(self, bucket_name, object_key):
        pass

    @abstractmethod
    def delete_object(self, bucket_name, object_key):
        pass

    @abstractmethod
    def list_objects(self, bucket_name):
        pass

class LocalStorageBackend(StorageBackend):
    def __init__(self, fs_manager):
        self.fs_manager = fs_manager
        self.buckets = {}  # In-memory bucket storage

    def create_bucket(self, bucket_name):
        if bucket_name in self.buckets:
            return False, "Bucket already exists"

        self.buckets[bucket_name] = {
            'objects': {}
        }
        self.fs_manager.createDirectory(f'/{bucket_name}')
        return True, None

    def delete_bucket(self, bucket_name):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        if self.buckets[bucket_name]['objects']:
            return False, "Bucket not empty"

        del self.buckets[bucket_name]
        self.fs_manager.deleteDirectory(f'/{bucket_name}')
        return True, None

    def list_buckets(self):
        return list(self.buckets.keys())

    def put_object(self, bucket_name, object_key, data):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"

        success = self.fs_manager.writeFile(f'/{bucket_name}/{object_key}', data)
        if success:
            self.buckets[bucket_name]['objects'][object_key] = len(data)
        return success, None

    def get_object(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"
        if object_key not in self.buckets[bucket_name]['objects']:
            return None, "Object does not exist"

        return self.fs_manager.readFile(f'/{bucket_name}/{object_key}'), None

    def delete_object(self, bucket_name, object_key):
        if bucket_name not in self.buckets:
            return False, "Bucket does not exist"
        if object_key not in self.buckets[bucket_name]['objects']:
            return False, "Object does not exist"

        success = self.fs_manager.deleteFile(f'/{bucket_name}/{object_key}')
        if success:
            del self.buckets[bucket_name]['objects'][object_key]
        return success, None

    def list_objects(self, bucket_name):
        if bucket_name not in self.buckets:
            return None, "Bucket does not exist"
        return list(self.buckets[bucket_name]['objects'].keys()), None

class AWSStorageBackend(StorageBackend):
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            endpoint_url=current_config['endpoint'],
            aws_access_key_id=current_config['access_key'],
            aws_secret_access_key=current_config['secret_key'],
            region_name=current_config.get('region'),
            config=Config(signature_version='s3v4')
        )

    def create_bucket(self, bucket_name):
        try:
            self.s3.create_bucket(Bucket=bucket_name)
            return True, None
        except Exception as e:
            return False, str(e)

    def delete_bucket(self, bucket_name):
        try:
            self.s3.delete_bucket(Bucket=bucket_name)
            return True, None
        except Exception as e:
            return False, str(e)

    def list_buckets(self):
        try:
            response = self.s3.list_buckets()
            return [bucket['Name'] for bucket in response['Buckets']], None
        except Exception as e:
            return None, str(e)

    def put_object(self, bucket_name, object_key, data):
        try:
            self.s3.put_object(Bucket=bucket_name, Key=object_key, Body=data)
            return True, None
        except Exception as e:
            return False, str(e)

    def get_object(self, bucket_name, object_key):
        try:
            response = self.s3.get_object(Bucket=bucket_name, Key=object_key)
            return response['Body'].read(), None
        except Exception as e:
            return None, str(e)

    def delete_object(self, bucket_name, object_key):
        try:
            self.s3.delete_object(Bucket=bucket_name, Key=object_key)
            return True, None
        except Exception as e:
            return False, str(e)

    def list_objects(self, bucket_name):
        try:
            response = self.s3.list_objects_v2(Bucket=bucket_name)
            return [obj['Key'] for obj in response.get('Contents', [])], None
        except Exception as e:
            return None, str(e)

def get_storage_backend(fs_manager=None):
    """Factory function to get the appropriate storage backend"""
    if STORAGE_ENV == 'local':
        if fs_manager is None:
            raise ValueError("fs_manager is required for local storage")
        return LocalStorageBackend(fs_manager)
    else:
        return AWSStorageBackend()
