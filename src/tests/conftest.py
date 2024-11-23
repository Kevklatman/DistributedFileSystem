"""Global test configuration and fixtures."""
import pytest
from pathlib import Path
import os
import asyncio
import logging
from datetime import datetime
import sys

from .common.test_helpers import TestDirectoryManager

# Add project root to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.models import Volume, NodeState, DataProtection, CloudTieringPolicy
from src.storage.infrastructure.active_node import ActiveNode
from src.storage.infrastructure.storage_efficiency import StorageEfficiencyManager

# Test environment configuration
os.environ.setdefault('STORAGE_ENV', 'test')
os.environ.setdefault('NODE_ID', 'test-node-1')
os.environ.setdefault('POD_IP', '127.0.0.1')

# Configure logging for tests
logging.basicConfig(level=logging.INFO)

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark as integration test")
    config.addinivalue_line("markers", "performance: mark as performance test")

@pytest.fixture(scope="session")
def test_storage():
    """Create a session-wide test storage directory."""
    with TestDirectoryManager() as storage_dir:
        os.environ['TEST_STORAGE_DIR'] = str(storage_dir)
        yield storage_dir

@pytest.fixture
def volume_dir(test_storage):
    """Get the volumes directory."""
    return test_storage / "volumes"

@pytest.fixture
def metadata_dir(test_storage):
    """Get the metadata directory."""
    return test_storage / "metadata"

@pytest.fixture
def cache_dir(test_storage):
    """Get the cache directory."""
    return test_storage / "cache"

@pytest.fixture
def mount_dir(test_storage):
    """Get the mounts directory."""
    return test_storage / "mounts"

@pytest.fixture
async def active_node():
    """Create an ActiveNode instance for testing."""
    node = ActiveNode(node_id="test-node-1")
    await node.initialize()
    yield node
    await node.shutdown()

@pytest.fixture
def test_volume():
    """Create a test volume with standard configuration."""
    return Volume(
        volume_id="test-vol-1",
        size_bytes=1024 * 1024 * 1024,  # 1GB
        used_bytes=0,
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        locations=[],
        tiering_policy=CloudTieringPolicy(
            volume_id="test-vol-1",
            cold_tier_after_days=30,
            archive_tier_after_days=90
        ),
        protection=DataProtection(
            volume_id="test-vol-1",
            local_snapshot_enabled=True,
            local_snapshot_schedule="0 0 * * *",
            local_snapshot_retention_days=7,
            cloud_backup_enabled=True,
            cloud_backup_schedule="0 0 * * 0",
            cloud_backup_retention_days=30,
            disaster_recovery_enabled=False
        )
    )

@pytest.fixture
def test_node_state():
    """Create a test node state."""
    return NodeState(
        node_id="test-node-1",
        status="active",
        last_heartbeat=datetime.now(),
        load=0.1,
        available_storage=1024 * 1024 * 1024 * 100,  # 100GB
        network_latency=10,  # 10ms
        volumes=[]
    )

@pytest.fixture
def storage_efficiency():
    """Create a StorageEfficiencyManager instance."""
    return StorageEfficiencyManager()

@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Cleanup test data after each test."""
    yield
    # Add cleanup logic here if needed{{ ... }}
