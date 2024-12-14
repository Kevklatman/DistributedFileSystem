"""Integration tests for S3-compatible API endpoints."""

import pytest
from flask import Flask
import os
import json
from pathlib import Path
from src.api.routes.aws_s3_api import aws_s3_api
from src.api.services.s3_service import S3Service
from src.api.services.fs_manager import FileSystemManager

@pytest.fixture
def app():
    """Create test Flask app with S3 API routes."""
    app = Flask(__name__)
    
    # Create test storage root
    test_storage_root = Path("/tmp/dfs_test")
    test_storage_root.mkdir(parents=True, exist_ok=True)
    
    # Initialize services
    fs_manager = FileSystemManager(storage_root=str(test_storage_root))
    s3_service = S3Service(storage_root=str(test_storage_root))
    
    # Register services with app
    app.config['s3_service'] = s3_service
    
    # Register blueprint
    import src.api.routes.aws_s3_api as s3_api_module
    s3_api_module.s3_service = s3_service
    app.register_blueprint(aws_s3_api)
    
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown test environment."""
    # Setup
    test_dir = Path("/tmp/dfs_test")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Teardown
    import shutil
    if test_dir.exists():
        shutil.rmtree(str(test_dir))

def test_list_buckets(client):
    """Test listing buckets."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Buckets" in response.json

def test_create_bucket(client):
    """Test bucket creation."""
    response = client.put("/test-bucket")
    assert response.status_code == 200
    
    # Verify bucket exists
    response = client.get("/")
    assert response.status_code == 200
    assert "test-bucket" in str(response.json)

def test_delete_bucket(client):
    """Test bucket deletion."""
    # Create bucket first
    client.put("/test-bucket")
    
    # Delete bucket
    response = client.delete("/test-bucket")
    assert response.status_code == 200
    
    # Verify bucket is gone
    response = client.get("/")
    assert response.status_code == 200
    assert "test-bucket" not in str(response.json)

def test_put_object(client):
    """Test putting an object."""
    # Create bucket first
    client.put("/test-bucket")
    
    # Put object
    response = client.put(
        "/test-bucket/test-object",
        data=b"test data",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200

def test_get_object(client):
    """Test getting an object."""
    # Create bucket and object first
    client.put("/test-bucket")
    client.put(
        "/test-bucket/test-object",
        data=b"test data",
        headers={"Content-Type": "application/octet-stream"},
    )
    
    # Get object
    response = client.get("/test-bucket/test-object")
    assert response.status_code == 200
    assert response.data == b"test data"

def test_delete_object(client):
    """Test deleting an object."""
    # Create bucket and object first
    client.put("/test-bucket")
    client.put(
        "/test-bucket/test-object",
        data=b"test data",
        headers={"Content-Type": "application/octet-stream"},
    )
    
    # Delete object
    response = client.delete("/test-bucket/test-object")
    assert response.status_code == 200
    
    # Verify object is gone
    response = client.get("/test-bucket/test-object")
    assert response.status_code == 404

def test_list_objects(client):
    """Test listing objects in a bucket."""
    # Create bucket and objects first
    client.put("/test-bucket")
    client.put(
        "/test-bucket/test-object1",
        data=b"test data 1",
        headers={"Content-Type": "application/octet-stream"},
    )
    client.put(
        "/test-bucket/test-object2",
        data=b"test data 2",
        headers={"Content-Type": "application/octet-stream"},
    )
    
    # List objects
    response = client.get("/test-bucket")
    assert response.status_code == 200
    assert "Contents" in response.json
    assert len(response.json["Contents"]) == 2

def test_error_handling(client):
    """Test error handling."""
    # Test getting nonexistent bucket
    response = client.get("/nonexistent-bucket")
    assert response.status_code == 404
    assert "error" in response.json
    
    # Test getting nonexistent object
    response = client.get("/test-bucket/nonexistent-object")
    assert response.status_code == 404
    assert "error" in response.json
    
    # Test invalid bucket name
    response = client.put("/Invalid.Bucket")
    assert response.status_code == 400
    assert "error" in response.json
    
    # Test deleting non-empty bucket
    client.put("/test-bucket")
    client.put(
        "/test-bucket/test-object",
        data=b"test data",
        headers={"Content-Type": "application/octet-stream"},
    )
    response = client.delete("/test-bucket")
    assert response.status_code == 409  # Conflict
    assert "error" in response.json
