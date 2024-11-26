"""Unit tests for the cluster manager functionality."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import kubernetes
from kubernetes import client, config

from src.storage.infrastructure.cluster_manager import (
    StorageClusterManager,
    StorageNodeInfo,
)

# Set default fixture loop scope
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_k8s_api():
    """Mock Kubernetes API client."""
    mock_api = MagicMock()
    mock_api.create_namespaced_lease = AsyncMock()
    mock_api.get_namespaced_lease = AsyncMock()
    mock_api.patch_namespaced_lease = AsyncMock()
    return mock_api

@pytest.fixture
def cluster_manager(mock_k8s_api):
    """Create a cluster manager instance."""
    with patch("kubernetes.client.CoordinationV1Api", return_value=mock_k8s_api):
        manager = StorageClusterManager(
            node_id="test-node-1",
            namespace="storage-system",
        )
        return manager

class TestStorageClusterManager:
    async def test_initialization(self, cluster_manager):
        """Test cluster manager initialization."""
        assert cluster_manager.node_id == "test-node-1"
        assert cluster_manager.namespace == "storage-system"
        assert not cluster_manager.is_leader

    async def test_node_registration(self, cluster_manager):
        """Test node registration."""
        node_info = StorageNodeInfo(
            node_id="node-2",
            address="10.0.0.2",
            status="ready",
            capacity_gb=1000,
            available_gb=800,
        )
        await cluster_manager.register_node(node_info)
        assert "node-2" in cluster_manager.nodes

    async def test_leader_election(self, cluster_manager, mock_k8s_api):
        """Test leader election process."""
        lease_name = "storage-cluster-leader"
        
        # Mock the lease creation
        mock_lease = client.V1Lease(
            metadata=client.V1ObjectMeta(name=lease_name),
            spec=client.V1LeaseSpec(
                holder_identity=cluster_manager.node_id,
                lease_duration_seconds=15
            )
        )
        mock_k8s_api.create_namespaced_lease.return_value = mock_lease

        # Start leader election
        await cluster_manager._start_leader_election()
        
        # Verify leader election results
        assert cluster_manager.leader is True
        mock_k8s_api.create_namespaced_lease.assert_called_once()
        
        # Verify the lease creation arguments
        call_args = mock_k8s_api.create_namespaced_lease.call_args
        assert call_args[1]["namespace"] == cluster_manager.namespace
        created_lease = call_args[1]["body"]
        assert created_lease.metadata.name == lease_name
        assert created_lease.spec.holder_identity == cluster_manager.node_id
        assert created_lease.spec.lease_duration_seconds == 15

    async def test_leader_election_failure(self, cluster_manager, mock_k8s_api):
        """Test leader election when another node is leader."""
        # Mock existing lease with different leader
        mock_k8s_api.get_namespaced_lease.return_value = MagicMock(
            spec=client.V1Lease,
            metadata=MagicMock(name="storage-leader"),
            spec=MagicMock(holder_identity="other-node"),
        )

        await cluster_manager.start_leader_election()
        assert not cluster_manager.is_leader

    async def test_node_failure_handling(self, cluster_manager):
        """Test handling of node failures."""
        # Register a node
        node_info = StorageNodeInfo(
            node_id="node-2",
            address="10.0.0.2",
            status="ready",
            capacity_gb=1000,
            available_gb=800,
        )
        await cluster_manager.register_node(node_info)

        # Simulate node failure
        await cluster_manager.mark_node_failed("node-2")
        assert cluster_manager.nodes["node-2"].status == "failed"

    async def test_target_node_selection(self, cluster_manager):
        """Test selection of target nodes for data placement."""
        # Register multiple nodes
        nodes = [
            StorageNodeInfo(
                node_id=f"node-{i}",
                address=f"10.0.0.{i}",
                status="ready",
                capacity_gb=1000,
                available_gb=800 - i * 100,  # Different available space
            )
            for i in range(1, 4)
        ]
        for node in nodes:
            await cluster_manager.register_node(node)

        # Select target nodes
        target_nodes = await cluster_manager.select_target_nodes(
            size_gb=100,
            count=2,
        )
        assert len(target_nodes) == 2
        # Should select nodes with most available space
        assert target_nodes[0].node_id == "node-1"  # Most available space

    async def test_error_handling(self):
        """Test error handling in initialization."""
        # Test initialization without required parameters
        with pytest.raises(ValueError):
            StorageClusterManager()
