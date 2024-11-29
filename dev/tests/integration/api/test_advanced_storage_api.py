"""Integration tests for advanced storage API endpoints."""

import pytest
from flask import Flask
import os
import json
from pathlib import Path
from src.api.routes.advanced_storage import advanced_storage
from src.api.services.fs_manager import FileSystemManager
from src.infrastructure.manager import InfrastructureManager
from src.api.services.advanced_storage_service import AdvancedStorageService
from src.models.models import StoragePool

@pytest.fixture
def app():
    """Create test Flask app with advanced storage API routes."""
    app = Flask(__name__)
    
    # Create test storage root
    test_storage_root = Path("/tmp/dfs_test")
    test_storage_root.mkdir(parents=True, exist_ok=True)
    
    # Initialize managers and services
    infrastructure = InfrastructureManager()
    fs_manager = FileSystemManager(storage_root=str(test_storage_root))
    storage_service = AdvancedStorageService(str(test_storage_root))
    
    # Create test storage pool
    pool_path = test_storage_root / "pools" / "test-pool"
    pool_path.mkdir(parents=True, exist_ok=True)
    
    # Create test pool in storage service
    storage_service.create_pool(
        name="test-pool",
        location={"type": "on_prem", "path": str(pool_path)},
        capacity_gb=1000
    )
    
    # Register services with app
    app.config['storage_service'] = storage_service
    
    # Register blueprint
    import src.api.routes.advanced_storage as advanced_storage_module
    advanced_storage_module.storage_service = storage_service
    app.register_blueprint(advanced_storage)
    
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

def test_create_volume(client):
    """Test volume creation."""
    # Test successful volume creation
    response = client.post(
        "/volumes",
        json={
            "name": "test-volume",
            "size_gb": 100,
            "pool_id": "test-pool",
            "dedup": True,
            "compression": True,
        },
    )
    assert response.status_code == 201
    assert "volume_id" in response.json
    
    # Test missing required fields
    response = client.post(
        "/volumes",
        json={
            "name": "test-volume",
        },
    )
    assert response.status_code == 400
    assert "error" in response.json
    
    # Test invalid pool ID
    response = client.post(
        "/volumes",
        json={
            "name": "test-volume",
            "size_gb": 100,
            "pool_id": "nonexistent-pool",
        },
    )
    assert response.status_code == 404
    assert "error" in response.json

def create_test_volume(client):
    """Helper function to create a test volume."""
    response = client.post(
        "/volumes",
        json={
            "name": "test-volume",
            "size_gb": 100,
            "pool_id": "test-pool",
        },
    )
    assert response.status_code == 201
    assert "volume_id" in response.json
    return response.json["volume_id"]

def test_get_protection_status(client):
    """Test getting protection status."""
    volume_id = create_test_volume(client)
    
    # Test successful status retrieval
    response = client.get(f"/volumes/{volume_id}/protection")
    assert response.status_code == 200
    assert "snapshots" in response.json
    assert "backups" in response.json
    assert "policy" in response.json
    
    # Test nonexistent volume
    response = client.get("/volumes/nonexistent/protection")
    assert response.status_code == 404
    assert "error" in response.json

def test_get_efficiency_stats(client):
    """Test getting efficiency statistics."""
    volume_id = create_test_volume(client)
    
    # Test successful stats retrieval
    response = client.get(f"/volumes/{volume_id}/efficiency")
    assert response.status_code == 200
    assert "deduplication_ratio" in response.json
    assert "compression_ratio" in response.json
    assert "total_savings" in response.json
    
    # Test nonexistent volume
    response = client.get("/volumes/nonexistent/efficiency")
    assert response.status_code == 404
    assert "error" in response.json

def test_restore_snapshot(client):
    """Test snapshot restoration."""
    volume_id = create_test_volume(client)
    
    # Create snapshot
    snapshot_response = client.post(
        f"/volumes/{volume_id}/snapshots",
        json={"name": "test-snapshot"},
    )
    assert snapshot_response.status_code == 201
    assert "snapshot_id" in snapshot_response.json
    snapshot_id = snapshot_response.json["snapshot_id"]
    
    # Test successful restore
    response = client.post(f"/volumes/{volume_id}/snapshots/{snapshot_id}/restore")
    assert response.status_code == 200
    assert response.json["status"] == "success"
    
    # Test nonexistent volume
    response = client.post(f"/volumes/nonexistent/snapshots/{snapshot_id}/restore")
    assert response.status_code == 404
    assert "error" in response.json
    
    # Test nonexistent snapshot
    response = client.post(f"/volumes/{volume_id}/snapshots/nonexistent/restore")
    assert response.status_code == 404
    assert "error" in response.json

def test_restore_backup(client):
    """Test backup restoration."""
    volume_id = create_test_volume(client)
    
    # Create backup
    backup_response = client.post(
        f"/volumes/{volume_id}/backups",
        json={"target_location": "s3://test-bucket"},
    )
    assert backup_response.status_code == 201
    assert "backup_id" in backup_response.json
    backup_id = backup_response.json["backup_id"]
    
    # Test successful restore
    response = client.post(f"/volumes/{volume_id}/backups/{backup_id}/restore")
    assert response.status_code == 200
    assert response.json["status"] == "success"
    
    # Test nonexistent volume
    response = client.post(f"/volumes/nonexistent/backups/{backup_id}/restore")
    assert response.status_code == 404
    assert "error" in response.json
    
    # Test nonexistent backup
    response = client.post(f"/volumes/{volume_id}/backups/nonexistent/restore")
    assert response.status_code == 404
    assert "error" in response.json

def test_error_handling(client):
    """Test various error scenarios."""
    # Test invalid volume size
    response = client.post(
        "/volumes",
        json={
            "name": "test-volume",
            "size_gb": -100,  # Invalid size
            "pool_id": "test-pool",
        },
    )
    assert response.status_code == 400
    assert "error" in response.json
    
    # Test invalid volume name
    response = client.post(
        "/volumes",
        json={
            "name": "",  # Empty name
            "size_gb": 100,
            "pool_id": "test-pool",
        },
    )
    assert response.status_code == 400
    assert "error" in response.json
    
    # Test missing required fields
    response = client.post("/volumes", json={})
    assert response.status_code == 400
    assert "error" in response.json
    
    # Test invalid JSON
    response = client.post(
        "/volumes",
        data="invalid json",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "error" in response.json
