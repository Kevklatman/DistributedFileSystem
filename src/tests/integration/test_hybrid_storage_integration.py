"""Integration tests for hybrid storage system interactions."""
import pytest
import asyncio
import os
from pathlib import Path
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from storage.infrastructure.hybrid_storage import HybridStorageManager
from storage.infrastructure.active_node import ActiveNode
from storage.infrastructure.cluster_manager import StorageClusterManager
from storage.infrastructure.providers import get_cloud_provider
from src.models.models import (
    StorageLocation,
    StoragePool,
    Volume,
    CloudTieringPolicy,
    DataProtection,
    HybridStorageSystem,
    DataTemperature
)

@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def hybrid_manager(temp_storage_dir):
    """Create a HybridStorageManager instance."""
    return HybridStorageManager(temp_storage_dir)

@pytest.fixture
def active_node(temp_storage_dir):
    """Create an ActiveNode instance."""
    with patch.dict(os.environ, {
        'NODE_ID': 'test-node-1',
        'POD_IP': '10.0.0.1'
    }):
        node = ActiveNode(storage_path=temp_storage_dir)
        return node

@pytest.fixture
def cluster_manager():
    """Create a StorageClusterManager instance."""
    with patch.dict(os.environ, {
        'NODE_ID': 'test-node-1',
        'POD_IP': '10.0.0.1'
    }):
        return StorageClusterManager(namespace="test-namespace")

class TestHybridStorageIntegration:
    @pytest.mark.asyncio
    async def test_data_write_and_tiering(self, hybrid_manager, active_node, cluster_manager):
        """Test writing data and automatic tiering between storage layers."""
        # Setup test data
        test_data = b"Test data content"
        volume_id = "test-volume-1"
        
        # Configure tiering policy
        policy = CloudTieringPolicy(
            cold_tier_after_days=1,
            archive_tier_after_days=7,
            delete_after_days=30
        )
        
        # Create volume with policy
        volume = await active_node.create_volume(
            volume_id=volume_id,
            size_bytes=len(test_data),
            tiering_policy=policy
        )
        
        # Write data
        await active_node.write_data(
            volume_id=volume_id,
            offset=0,
            data=test_data
        )
        
        # Verify data is written to local storage
        local_data = await active_node.read_data(
            volume_id=volume_id,
            offset=0,
            length=len(test_data)
        )
        assert local_data == test_data
        
        # Simulate time passing for tiering
        volume.last_accessed_at = datetime.now() - timedelta(days=2)
        await hybrid_manager.check_tiering_policies()
        
        # Verify data is moved to cold storage
        assert hybrid_manager.get_data_temperature(volume_id) == DataTemperature.COLD

    @pytest.mark.asyncio
    async def test_data_replication_and_consistency(self, hybrid_manager, active_node, cluster_manager):
        """Test data replication across nodes and consistency maintenance."""
        test_data = b"Replicated data content"
        volume_id = "test-volume-2"
        
        # Configure protection policy
        protection = DataProtection(
            replica_count=2,
            consistency_level="strong"
        )
        
        # Create volume with protection
        volume = await active_node.create_volume(
            volume_id=volume_id,
            size_bytes=len(test_data),
            protection=protection
        )
        
        # Write data with strong consistency
        await active_node.write_data(
            volume_id=volume_id,
            offset=0,
            data=test_data,
            consistency="strong"
        )
        
        # Verify replicas are created
        replicas = await active_node.get_volume_replicas(volume_id)
        assert len(replicas) == protection.replica_count
        
        # Verify data consistency across replicas
        for replica in replicas:
            replica_data = await active_node.read_data(
                volume_id=volume_id,
                offset=0,
                length=len(test_data),
                replica_id=replica.replica_id
            )
            assert replica_data == test_data

    @pytest.mark.asyncio
    async def test_node_failure_recovery(self, hybrid_manager, active_node, cluster_manager):
        """Test data recovery and redistribution after node failure."""
        test_data = b"Data to recover"
        volume_id = "test-volume-3"
        
        # Create volume with redundancy
        volume = await active_node.create_volume(
            volume_id=volume_id,
            size_bytes=len(test_data),
            protection=DataProtection(replica_count=3)
        )
        
        # Write data
        await active_node.write_data(
            volume_id=volume_id,
            offset=0,
            data=test_data
        )
        
        # Simulate node failure
        failed_node_id = "node-1"
        cluster_manager._handle_node_failure(failed_node_id)
        
        # Verify data is still accessible
        recovered_data = await active_node.read_data(
            volume_id=volume_id,
            offset=0,
            length=len(test_data)
        )
        assert recovered_data == test_data
        
        # Verify replicas are rebalanced
        replicas = await active_node.get_volume_replicas(volume_id)
        assert len(replicas) == 3  # Should maintain desired replica count

    @pytest.mark.asyncio
    async def test_cache_behavior(self, hybrid_manager, active_node):
        """Test caching behavior for frequently accessed data."""
        test_data = b"Cached data content"
        volume_id = "test-volume-4"
        
        # Create volume
        volume = await active_node.create_volume(
            volume_id=volume_id,
            size_bytes=len(test_data)
        )
        
        # Write data
        await active_node.write_data(
            volume_id=volume_id,
            offset=0,
            data=test_data
        )
        
        # Access data multiple times to trigger caching
        for _ in range(5):
            await active_node.read_data(
                volume_id=volume_id,
                offset=0,
                length=len(test_data)
            )
        
        # Verify data is cached
        cache_info = await active_node.get_cache_info(volume_id)
        assert cache_info.is_cached
        assert cache_info.hit_count >= 5

if __name__ == "__main__":
    pytest.main([__file__])
