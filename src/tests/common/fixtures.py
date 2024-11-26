"""Common test fixtures for the distributed file system."""

import pytest
import tempfile
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from src.storage.infrastructure.load_manager import LoadManager
from src.storage.infrastructure.data.consistency_manager import ConsistencyManager
from src.storage.infrastructure.data.replication_manager import ReplicationManager
from src.models.models import (
    Volume,
    NodeState,
    StoragePool,
    ThinProvisioningState,
    DeduplicationState,
    CompressionState,
    DataProtection,
    CloudTieringPolicy,
    ReplicationPolicy
)


@pytest.fixture
def test_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_load_manager():
    """Create a mock load manager with default healthy metrics."""
    load_manager = MagicMock(spec=LoadManager)
    load_manager.can_handle_request.return_value = True
    load_manager.get_current_metrics.return_value = {
        'cpu_usage': 20.0,
        'memory_usage': 30.0,
        'disk_io': 10.0,
        'network_io': 5.0,
        'request_rate': 100.0
    }
    return load_manager


@pytest.fixture
def mock_consistency_manager():
    """Create a mock consistency manager."""
    consistency_manager = MagicMock(spec=ConsistencyManager)
    consistency_manager.verify_write_consistency.return_value = True
    consistency_manager.verify_read_consistency.return_value = True
    return consistency_manager


@pytest.fixture
def mock_replication_manager():
    """Create a mock replication manager."""
    replication_manager = MagicMock(spec=ReplicationManager)
    replication_manager.replicate_data = AsyncMock(return_value=True)
    replication_manager.verify_replication = AsyncMock(return_value=True)
    return replication_manager


@pytest.fixture
def mock_volume():
    """Create a mock volume with default settings."""
    return Volume(
        volume_id="test-volume-1",
        size_bytes=1024 * 1024 * 1024,  # 1GB
        used_bytes=0,
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        locations=["node-1", "node-2"],
        deduplication_enabled=True,
        deduplication_state=DeduplicationState(),
        compression_state=CompressionState(),
        thin_provisioning_state=ThinProvisioningState(
            allocated_size=1024 * 1024 * 1024,
            used_size=0
        ),
        tiering_policy=CloudTieringPolicy(
            volume_id="test-volume-1",
            cold_tier_after_days=30,
            archive_tier_after_days=90
        ),
        protection=DataProtection(
            volume_id="test-volume-1",
            local_snapshot_enabled=True,
            cloud_backup_enabled=False
        )
    )


@pytest.fixture
def mock_node_state():
    """Create a mock node state with default healthy metrics."""
    return NodeState(
        node_id="test-node-1",
        status="healthy",
        last_heartbeat=datetime.now(),
        load=20.0,
        available_storage=1024 * 1024 * 1024 * 100,  # 100GB
        network_latency=5.0,
        volumes=[]
    )


@pytest.fixture
def mock_storage_pool():
    """Create a mock storage pool with default settings."""
    return StoragePool(
        pool_id="test-pool-1",
        name="Test Pool",
        total_size_bytes=1024 * 1024 * 1024 * 1024,  # 1TB
        used_size_bytes=0,
        deduplication_enabled=True,
        compression_enabled=True,
        thin_provisioning_enabled=True
    )


@pytest.fixture
def mock_replication_policy():
    """Create a mock replication policy with default settings."""
    return ReplicationPolicy(
        enabled=True,
        min_copies=2,
        max_copies=3,
        sync_mode="async",
        bandwidth_limit_mbps=100
    )
