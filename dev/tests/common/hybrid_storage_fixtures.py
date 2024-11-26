"""Fixtures for hybrid storage testing."""
import os
import pytest
import boto3
import docker
from moto import mock_s3
from contextlib import contextmanager

@pytest.fixture
def aws_credentials():
    """Mock AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

@pytest.fixture
def s3_client(aws_credentials):
    """Create mocked S3 client."""
    with mock_s3():
        s3 = boto3.client('s3')
        s3.create_bucket(Bucket='test-bucket')
        yield s3

@pytest.fixture
def hybrid_storage_manager(s3_client):
    """Create hybrid storage manager for testing."""
    from src.storage.hybrid_storage import HybridStorageManager
    return HybridStorageManager(
        s3_client=s3_client,
        local_storage_path='/tmp/hybrid_storage_test'
    )

@pytest.fixture
def haproxy_container():
    """Start HAProxy container for testing."""
    client = docker.from_env()
    container = client.containers.run(
        'haproxy:2.4',
        detach=True,
        ports={'80/tcp': 8080},
        volumes={
            '/Users/kevinklatman/Development/Code/DistributedFileSystem/dev/config/haproxy.cfg': {
                'bind': '/usr/local/etc/haproxy/haproxy.cfg',
                'mode': 'ro'
            }
        }
    )
    yield container
    container.stop()
    container.remove()

@contextmanager
def storage_protocol_context(protocol):
    """Context manager for testing different storage protocols."""
    original_protocol = os.environ.get('STORAGE_PROTOCOL')
    os.environ['STORAGE_PROTOCOL'] = protocol
    try:
        yield
    finally:
        if original_protocol:
            os.environ['STORAGE_PROTOCOL'] = original_protocol
        else:
            del os.environ['STORAGE_PROTOCOL']
