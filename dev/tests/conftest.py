"""Global test configuration and fixtures."""

import pytest
from pathlib import Path
import os
import asyncio
import logging
from datetime import datetime
import sys

# Add project root to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from .common.test_helpers import TestDirectoryManager
from src.models.models import Volume, NodeState, DataProtection, CloudTieringPolicy
from src.storage.infrastructure.active_node import ActiveNode
from src.storage.infrastructure.storage_efficiency import StorageEfficiencyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "performance: mark test as performance test")


@pytest.fixture(scope="session")
def test_storage(tmp_path_factory):
    """Create a session-wide test storage directory."""
    test_dir = tmp_path_factory.mktemp("storage")
    return test_dir


@pytest.fixture
def volume_dir(test_storage):
    """Get the volumes directory."""
    volume_path = test_storage / "volumes"
    volume_path.mkdir(exist_ok=True)
    return volume_path


@pytest.fixture
def metadata_dir(test_storage):
    """Get the metadata directory."""
    metadata_path = test_storage / "metadata"
    metadata_path.mkdir(exist_ok=True)
    return metadata_path


@pytest.fixture
def cache_dir(test_storage):
    """Get the cache directory."""
    cache_path = test_storage / "cache"
    cache_path.mkdir(exist_ok=True)
    return cache_path


@pytest.fixture
def mount_dir(test_storage):
    """Get the mounts directory."""
    mount_path = test_storage / "mounts"
    mount_path.mkdir(exist_ok=True)
    return mount_path


@pytest.fixture
async def active_node(volume_dir, metadata_dir, cache_dir, mount_dir):
    """Create an ActiveNode instance for testing."""
    node = ActiveNode(
        volume_dir=volume_dir,
        metadata_dir=metadata_dir,
        cache_dir=cache_dir,
        mount_dir=mount_dir
    )
    await node.initialize()
    return node


@pytest.fixture
def test_volume():
    """Create a test volume with standard configuration."""
    return Volume(
        name="test_volume",
        size_gb=100,
        data_protection=DataProtection(
            replicas=2,
            encryption=True,
            backup_schedule="daily",
        ),
        cloud_tiering=CloudTieringPolicy(
            enabled=True,
            temperature="cold",
            archive_after_days=30,
        ),
    )


@pytest.fixture
def test_node_state():
    """Create a test node state."""
    return NodeState(
        node_id="test-node-1",
        status="active",
        last_heartbeat=datetime.now(),
        storage_capacity_gb=1000,
        storage_used_gb=100
    )


@pytest.fixture
def storage_efficiency():
    """Create a StorageEfficiencyManager instance."""
    return StorageEfficiencyManager()
