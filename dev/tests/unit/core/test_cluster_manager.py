"""Unit tests for the cluster manager functionality."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import kubernetes
from kubernetes import client, config
import os
import asyncio
from datetime import datetime, timedelta

from src.storage.infrastructure.cluster_manager import (
    StorageClusterManager,
    StorageNodeInfo,
    LeaderElectionError,
    NodeRegistrationError,
    NodeNotFoundError,
    ClusterManagerError
)

# Set default fixture loop scope
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_k8s_api():
    """Mock Kubernetes API client."""
    mock_api = MagicMock()
    mock_api.create_namespaced_lease = AsyncMock()
    mock_api.read_namespaced_lease = AsyncMock()
    mock_api.patch_namespaced_lease = AsyncMock()
    mock_api.delete_namespaced_lease = AsyncMock()
    mock_api.create_namespaced_custom_object = AsyncMock()
    mock_api.patch_namespaced_custom_object = AsyncMock()
    return mock_api

@pytest.fixture
def mock_env():
    """Mock environment variables."""
    with patch.dict(os.environ, {
        "NODE_ID": "test-node-1",
        "POD_IP": "10.0.0.1",
        "HOSTNAME": "test-host",
        "STORAGE_NAMESPACE": "storage-system"
    }):
        yield

@pytest.fixture
async def cluster_manager(mock_k8s_api):
    """Create a cluster manager instance."""
    with patch("kubernetes.client.CoordinationV1Api", return_value=mock_k8s_api), \
         patch("kubernetes.client.CustomObjectsApi", return_value=mock_k8s_api), \
         patch("kubernetes.config.load_incluster_config"):
        manager = StorageClusterManager(namespace="storage-system")
        manager.start_time = datetime.now().timestamp()
        return manager

class TestStorageClusterManager:
    async def test_initialization(self, cluster_manager):
        """Test cluster manager initialization."""
        assert cluster_manager.node_id == os.environ.get("NODE_ID", "test-node-1")
        assert cluster_manager.namespace == "storage-system"
        assert not cluster_manager.leader
        assert cluster_manager.start_time is not None

    async def test_node_registration_success(self, cluster_manager, mock_k8s_api):
        """Test successful node registration."""
        node_info = StorageNodeInfo(
            node_id="node-2",
            hostname="host-2",
            pod_ip="10.0.0.2",
            capacity_bytes=1000,
            used_bytes=0,
            status="STARTING",
            last_heartbeat=datetime.now().timestamp(),
            pods=[],
            zone="default"
        )
        
        # Mock successful registration
        mock_k8s_api.create_namespaced_custom_object.return_value = {
            "metadata": {"name": node_info.node_id},
            "spec": {"nodeId": node_info.node_id}
        }
        
        await cluster_manager._register_node(node_info)
        assert node_info.node_id in cluster_manager.nodes
        assert cluster_manager.nodes[node_info.node_id].status == "STARTING"
        assert cluster_manager.nodes[node_info.node_id].pod_ip == "10.0.0.2"

    async def test_node_registration_duplicate(self, cluster_manager, mock_k8s_api):
        """Test duplicate node registration."""
        node_info = StorageNodeInfo(
            node_id="node-2",
            hostname="host-2",
            pod_ip="10.0.0.2",
            capacity_bytes=1000,
            used_bytes=0,
            status="STARTING",
            last_heartbeat=datetime.now().timestamp(),
            pods=[],
            zone="default"
        )
        
        # Mock API conflict
        mock_k8s_api.create_namespaced_custom_object.side_effect = kubernetes.client.rest.ApiException(status=409)
        
        with pytest.raises(NodeRegistrationError):
            await cluster_manager._register_node(node_info)

    async def test_leader_election_success(self, cluster_manager, mock_k8s_api):
        """Test successful leader election process."""
        lease_name = "storage-cluster-leader"
        lease_duration = 15
        
        # Mock successful lease creation
        mock_lease = client.V1Lease(
            metadata=client.V1ObjectMeta(name=lease_name),
            spec=client.V1LeaseSpec(
                holder_identity=cluster_manager.node_id,
                lease_duration_seconds=lease_duration,
                acquire_time=datetime.now().isoformat() + "Z",
                renew_time=datetime.now().isoformat() + "Z"
            )
        )
        mock_k8s_api.create_namespaced_lease.return_value = mock_lease
        mock_k8s_api.read_namespaced_lease.return_value = mock_lease

        # Start leader election
        await cluster_manager._acquire_leadership()
        
        # Verify leader election results
        assert cluster_manager.leader
        mock_k8s_api.create_namespaced_lease.assert_called_once()

    async def test_leader_election_failure(self, cluster_manager, mock_k8s_api):
        """Test leader election when another node is leader."""
        lease_name = "storage-cluster-leader"
        other_node = "other-node"
        
        # Mock lease exists with different leader
        mock_lease = client.V1Lease(
            metadata=client.V1ObjectMeta(name=lease_name),
            spec=client.V1LeaseSpec(
                holder_identity=other_node,
                lease_duration_seconds=15,
                acquire_time=datetime.now().isoformat() + "Z",
                renew_time=datetime.now().isoformat() + "Z"
            )
        )
        mock_k8s_api.create_namespaced_lease.side_effect = kubernetes.client.rest.ApiException(status=409)
        mock_k8s_api.read_namespaced_lease.return_value = mock_lease

        # Attempt leader election
        with pytest.raises(LeaderElectionError):
            await cluster_manager._acquire_leadership()
        assert not cluster_manager.leader
        assert cluster_manager.current_leader == other_node

    async def test_node_failure_detection(self, cluster_manager):
        """Test detection and handling of node failures."""
        # Register a node
        node_info = StorageNodeInfo(
            node_id="node-2",
            hostname="host-2",
            pod_ip="10.0.0.2",
            capacity_bytes=1000,
            used_bytes=0,
            status="READY",
            last_heartbeat=(datetime.now() - timedelta(minutes=5)).timestamp(),  # Old heartbeat
            pods=[],
            zone="default"
        )
        cluster_manager.nodes[node_info.node_id] = node_info
        
        # Run failure detection
        await cluster_manager._check_node_health()
        assert "node-2" not in cluster_manager.nodes  # Node should be removed

    async def test_node_selection(self, cluster_manager):
        """Test node selection for data placement."""
        # Add multiple nodes with different usage
        nodes = []
        for i in range(1, 4):
            node_info = StorageNodeInfo(
                node_id=f"node-{i}",
                hostname=f"host-{i}",
                pod_ip=f"10.0.0.{i}",
                capacity_bytes=1000,
                used_bytes=i * 100,  # Different used space
                status="READY",
                last_heartbeat=datetime.now().timestamp(),
                pods=[],
                zone="default"
            )
            nodes.append(node_info)
            cluster_manager.nodes[node_info.node_id] = node_info

        # Test node selection
        selected = cluster_manager._get_target_nodes(2)
        assert len(selected) == 2
        assert selected[0].node_id == "node-1"  # Should be least used
        assert selected[1].node_id == "node-2"  # Should be second least used

    async def test_graceful_shutdown(self, cluster_manager, mock_k8s_api):
        """Test graceful cluster manager shutdown."""
        # First become leader
        lease_name = "storage-cluster-leader"
        mock_lease = client.V1Lease(
            metadata=client.V1ObjectMeta(name=lease_name),
            spec=client.V1LeaseSpec(
                holder_identity=cluster_manager.node_id,
                lease_duration_seconds=15
            )
        )
        mock_k8s_api.create_namespaced_lease.return_value = mock_lease
        await cluster_manager._acquire_leadership()
        
        # Now shutdown
        await cluster_manager.shutdown()
        
        # Verify cleanup
        assert not cluster_manager.leader
        mock_k8s_api.delete_namespaced_lease.assert_called_once()
        assert len(cluster_manager.nodes) == 0

if __name__ == "__main__":
    pytest.main(["-v", __file__])
