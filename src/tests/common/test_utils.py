"""Test utilities for the distributed file system."""

import os
import random
import string
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

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


def generate_random_string(length: int = 10) -> str:
    """Generate a random string of fixed length."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def create_test_volume(
    volume_id: Optional[str] = None,
    size_bytes: int = 1024 * 1024 * 1024,  # 1GB
    used_bytes: int = 0,
    locations: Optional[List[str]] = None
) -> Volume:
    """Create a test volume with given parameters."""
    return Volume(
        volume_id=volume_id or f"test-volume-{generate_random_string(5)}",
        size_bytes=size_bytes,
        used_bytes=used_bytes,
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        locations=locations or ["node-1", "node-2"],
        deduplication_enabled=True,
        deduplication_state=DeduplicationState(),
        compression_state=CompressionState(),
        thin_provisioning_state=ThinProvisioningState(
            allocated_size=size_bytes,
            used_size=used_bytes
        ),
        tiering_policy=CloudTieringPolicy(
            volume_id=volume_id or f"test-volume-{generate_random_string(5)}",
            cold_tier_after_days=30,
            archive_tier_after_days=90
        ),
        protection=DataProtection(
            volume_id=volume_id or f"test-volume-{generate_random_string(5)}",
            local_snapshot_enabled=True,
            cloud_backup_enabled=False
        )
    )


def create_test_node_state(
    node_id: Optional[str] = None,
    status: str = "healthy",
    load: float = 20.0,
    available_storage: int = 1024 * 1024 * 1024 * 100,  # 100GB
    network_latency: float = 5.0,
    volumes: Optional[List[str]] = None
) -> NodeState:
    """Create a test node state with given parameters."""
    return NodeState(
        node_id=node_id or f"test-node-{generate_random_string(5)}",
        status=status,
        last_heartbeat=datetime.now(),
        load=load,
        available_storage=available_storage,
        network_latency=network_latency,
        volumes=volumes or []
    )


def create_test_storage_pool(
    pool_id: Optional[str] = None,
    name: Optional[str] = None,
    total_size_bytes: int = 1024 * 1024 * 1024 * 1024,  # 1TB
    used_size_bytes: int = 0
) -> StoragePool:
    """Create a test storage pool with given parameters."""
    return StoragePool(
        pool_id=pool_id or f"test-pool-{generate_random_string(5)}",
        name=name or f"Test Pool {generate_random_string(5)}",
        total_size_bytes=total_size_bytes,
        used_size_bytes=used_size_bytes,
        deduplication_enabled=True,
        compression_enabled=True,
        thin_provisioning_enabled=True
    )


def create_test_replication_policy(
    enabled: bool = True,
    min_copies: int = 2,
    max_copies: int = 3,
    sync_mode: str = "async",
    bandwidth_limit_mbps: Optional[int] = 100
) -> ReplicationPolicy:
    """Create a test replication policy with given parameters."""
    return ReplicationPolicy(
        enabled=enabled,
        min_copies=min_copies,
        max_copies=max_copies,
        sync_mode=sync_mode,
        bandwidth_limit_mbps=bandwidth_limit_mbps
    )


def generate_test_data(size_bytes: int) -> bytes:
    """Generate test data of specified size."""
    return os.urandom(size_bytes)


def create_stale_node_state(node_state: NodeState, hours_old: int = 1) -> NodeState:
    """Create a stale version of a node state for testing timeouts."""
    stale_state = NodeState(
        node_id=node_state.node_id,
        status=node_state.status,
        last_heartbeat=datetime.now() - timedelta(hours=hours_old),
        load=node_state.load,
        available_storage=node_state.available_storage,
        network_latency=node_state.network_latency,
        volumes=node_state.volumes
    )
    return stale_state


def simulate_network_latency(base_latency: float = 5.0, jitter: float = 2.0) -> float:
    """Simulate network latency with jitter for testing."""
    return max(0.0, base_latency + random.uniform(-jitter, jitter))
