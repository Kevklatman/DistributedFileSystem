import pytest
import requests
import os
import time
import subprocess
import signal
from pathlib import Path
import tempfile

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
STORAGE_NODE_DIR = PROJECT_ROOT / "src" / "storage-node"

class StorageNodeTestServer:
    def __init__(self, port, data_dir):
        self.port = port
        self.data_dir = Path(data_dir)
        self.process = None
        
    def start(self):
        cmd = [
            str(STORAGE_NODE_DIR / "storage-node"),
            "-port", str(self.port),
            "-datadir", str(self.data_dir),
            "-nodeid", "test-node"
        ]
        self.process = subprocess.Popen(
            cmd,
            cwd=str(STORAGE_NODE_DIR)
        )
        # Wait for server to start
        time.sleep(2)  # Give more time for server to start
        
    def stop(self):
        if self.process:
            self.process.send_signal(signal.SIGTERM)
            self.process.wait()

@pytest.fixture
def storage_node():
    # Create temporary directory for storage node data
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        server = StorageNodeTestServer(port=8080, data_dir=temp_path)
        server.start()
        yield server
        server.stop()

def test_health_check(storage_node):
    """Test health check endpoint"""
    response = requests.get(f"http://localhost:{storage_node.port}/health")
    assert response.status_code == 200

def test_readiness_check(storage_node):
    """Test readiness check endpoint"""
    response = requests.get(f"http://localhost:{storage_node.port}/ready")
    assert response.status_code == 200

def test_volume_lifecycle(storage_node):
    """Test volume creation and deletion"""
    # Create volume
    volume_id = "test-vol-1"
    response = requests.post(
        f"http://localhost:{storage_node.port}/volumes",
        params={"id": volume_id}
    )
    assert response.status_code == 201
    
    # Verify volume directory exists
    volume_path = storage_node.data_dir / volume_id
    assert volume_path.exists() and volume_path.is_dir()
    
    # Delete volume
    response = requests.delete(
        f"http://localhost:{storage_node.port}/volumes",
        params={"id": volume_id}
    )
    assert response.status_code == 200
    assert not volume_path.exists()

def test_invalid_volume_operations(storage_node):
    """Test error handling for invalid volume operations"""
    # Test creating volume without ID
    response = requests.post(f"http://localhost:{storage_node.port}/volumes")
    assert response.status_code == 400
    
    # Test deleting non-existent volume
    response = requests.delete(
        f"http://localhost:{storage_node.port}/volumes",
        params={"id": "nonexistent"}
    )
    assert response.status_code == 200  # Idempotent deletion
    
    # Test invalid HTTP method
    response = requests.put(
        f"http://localhost:{storage_node.port}/volumes",
        params={"id": "test-vol"}
    )
    assert response.status_code == 405

def test_concurrent_volume_operations(storage_node):
    """Test concurrent volume operations"""
    import concurrent.futures
    
    def create_and_delete_volume(vol_id):
        # Create volume
        create_response = requests.post(
            f"http://localhost:{storage_node.port}/volumes",
            params={"id": vol_id}
        )
        assert create_response.status_code == 201
        
        # Delete volume
        delete_response = requests.delete(
            f"http://localhost:{storage_node.port}/volumes",
            params={"id": vol_id}
        )
        assert delete_response.status_code == 200
    
    # Run 10 concurrent volume operations
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(create_and_delete_volume, f"test-vol-{i}")
            for i in range(10)
        ]
        concurrent.futures.wait(futures)
        
        # Verify all operations completed successfully
        for future in futures:
            assert not future.exception()
