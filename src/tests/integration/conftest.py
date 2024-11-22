import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path

# Set environment variables before any imports
os.environ['STORAGE_ENV'] = 'local'
os.environ['NODE_ID'] = 'test-node-1'
os.environ['POD_IP'] = '10.0.0.1'

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.storage.core.hybrid_storage import HybridStorageManager
from src.storage.core.active_node import ActiveNode
from src.storage.core.cluster_manager import StorageClusterManager

@pytest.fixture(autouse=True)
def setup_test_storage():
    """Set up and clean up test storage directory"""
    test_storage_dir = tempfile.mkdtemp()
    os.environ['LOCAL_STORAGE_DIR'] = test_storage_dir
    
    yield test_storage_dir
    
    # Clean up test storage directory
    shutil.rmtree(test_storage_dir)

@pytest.fixture
def hybrid_manager(setup_test_storage):
    """Create a fresh HybridStorageManager for each test"""
    manager = HybridStorageManager(setup_test_storage)
    return manager

@pytest.fixture
def active_node(setup_test_storage):
    """Create a fresh ActiveNode for each test"""
    node = ActiveNode(storage_path=setup_test_storage)
    return node

@pytest.fixture
def cluster_manager():
    """Create a fresh StorageClusterManager for each test"""
    return StorageClusterManager(namespace="test-namespace")
