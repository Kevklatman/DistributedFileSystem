"""Common test fixtures for integration tests."""

import pytest
import sys
from pathlib import Path
import tempfile
import shutil
import os

# Set environment variables before any imports
os.environ["STORAGE_ENV"] = "local"
os.environ["NODE_ID"] = "test-node-1"
os.environ["POD_IP"] = "10.0.0.1"

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage.infrastructure.hybrid_storage import HybridStorageManager
from storage.infrastructure.active_node import ActiveNode
from storage.infrastructure.cluster_manager import StorageClusterManager


@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        data_path = Path(temp_dir)
        # Create standard test directories
        (data_path / "volumes").mkdir()
        (data_path / "metadata").mkdir()
        (data_path / "cache").mkdir()
        os.environ["LOCAL_STORAGE_DIR"] = str(data_path)
        yield data_path


@pytest.fixture
def hybrid_manager(test_data_dir):
    """Create a fresh HybridStorageManager for each test"""
    manager = HybridStorageManager(str(test_data_dir))
    return manager


@pytest.fixture
def active_node(test_data_dir):
    """Create a fresh ActiveNode for each test"""
    node = ActiveNode(storage_path=str(test_data_dir))
    return node


@pytest.fixture
def cluster_manager():
    """Create a fresh StorageClusterManager for each test"""
    return StorageClusterManager(namespace="test-namespace")
