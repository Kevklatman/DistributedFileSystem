"""Integration tests for storage node functionality."""

import pytest
import requests
import os
from pathlib import Path
import signal
import subprocess
import time

from ...common.test_helpers import PROJECT_ROOT

STORAGE_NODE_BIN = PROJECT_ROOT / "src" / "storage-node" / "storage-node"


class StorageNodeTestServer:
    """Test server for storage node integration tests."""

    def __init__(self, port: int, data_dir: Path):
        self.port = port
        self.data_dir = Path(data_dir)
        self.process = None

    def start(self):
        """Start the storage node server."""
        cmd = [
            str(STORAGE_NODE_BIN),
            "-port",
            str(self.port),
            "-datadir",
            str(self.data_dir),
            "-nodeid",
            "test-node",
        ]
        self.process = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
        # Wait for server to start
        time.sleep(2)

    def stop(self):
        """Stop the storage node server."""
        if self.process:
            self.process.send_signal(signal.SIGTERM)
            self.process.wait()


@pytest.fixture
def storage_node(test_storage):
    """Create a storage node server for testing."""
    server = StorageNodeTestServer(port=8080, data_dir=test_storage)
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


def test_volume_lifecycle(storage_node, volume_dir):
    """Test volume creation and deletion."""
    # Create volume
    volume_id = "test-vol-1"
    response = requests.post(
        f"http://localhost:{storage_node.port}/volumes", params={"id": volume_id}
    )
    assert response.status_code == 201

    # Verify volume directory exists
    volume_path = volume_dir / volume_id
    assert volume_path.exists() and volume_path.is_dir()

    # Delete volume
    response = requests.delete(
        f"http://localhost:{storage_node.port}/volumes", params={"id": volume_id}
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
        f"http://localhost:{storage_node.port}/volumes", params={"id": "nonexistent"}
    )
    assert response.status_code == 200  # Idempotent deletion

    # Test invalid HTTP method
    response = requests.put(
        f"http://localhost:{storage_node.port}/volumes", params={"id": "test-vol"}
    )
    assert response.status_code == 405


def test_concurrent_volume_operations(storage_node):
    """Test concurrent volume operations"""
    import concurrent.futures

    def create_and_delete_volume(vol_id):
        # Create volume
        create_response = requests.post(
            f"http://localhost:{storage_node.port}/volumes", params={"id": vol_id}
        )
        assert create_response.status_code == 201

        # Delete volume
        delete_response = requests.delete(
            f"http://localhost:{storage_node.port}/volumes", params={"id": vol_id}
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


def test_volume_data_persistence(storage_node, volume_dir):
    """Test data persistence in volumes."""
    volume_id = "test-vol-2"

    # Create volume
    response = requests.post(
        f"http://localhost:{storage_node.port}/volumes", params={"id": volume_id}
    )
    assert response.status_code == 201

    # Write data to volume
    volume_path = volume_dir / volume_id
    test_file = volume_path / "test.txt"
    test_file.write_text("test data")

    # Verify data persists after server restart
    storage_node.stop()
    storage_node.start()

    assert test_file.exists()
    assert test_file.read_text() == "test data"
