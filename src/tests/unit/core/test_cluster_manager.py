"""Unit tests for the StorageClusterManager class."""
import pytest
import asyncio
from datetime import datetime
import time
import kubernetes
from kubernetes import client, config
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import os

from src.storage.core.cluster_manager import StorageClusterManager, StorageNodeInfo

# Set default fixture loop scope
pytest.asyncio_default_fixture_loop_scope = "function"

@pytest.fixture
def mock_k8s_api():
    """Create a mock Kubernetes API client."""
    mock_api = MagicMock()
    mock_api.list_namespaced_pod.return_value = client.V1PodList(items=[])
    return mock_api

@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables."""
    with patch.dict(os.environ, {
        'NODE_ID': 'test-node-1',
        'POD_IP': '10.0.0.1'
    }):
        yield

@pytest.fixture
def cluster_manager(mock_env_vars, mock_k8s_api):
    """Create a StorageClusterManager instance for testing."""
    with patch('kubernetes.client.CoreV1Api', return_value=mock_k8s_api):
        with patch('kubernetes.client.CustomObjectsApi'):
            with patch('kubernetes.client.CoordinationV1Api'):
                manager = StorageClusterManager(namespace="test-namespace")
                return manager

@pytest.fixture
def mock_storage_nodes():
    """Create mock storage nodes."""
    return {
        "node-1": StorageNodeInfo(
            node_id="node-1",
            hostname="host-1",
            pod_ip="10.0.0.1",
            capacity_bytes=1000000,
            used_bytes=500000,
            status="READY",
            last_heartbeat=time.time(),
            pods=["pod-1"],
            zone="zone-1"
        ),
        "node-2": StorageNodeInfo(
            node_id="node-2",
            hostname="host-2",
            pod_ip="10.0.0.2",
            capacity_bytes=1000000,
            used_bytes=300000,
            status="READY",
            last_heartbeat=time.time(),
            pods=["pod-2"],
            zone="zone-1"
        )
    }

class TestStorageClusterManager:
    def test_initialization(self, cluster_manager):
        """Test proper initialization of StorageClusterManager."""
        assert cluster_manager.namespace == "test-namespace"
        assert cluster_manager.node_id == "test-node-1"
        assert cluster_manager.pod_ip == "10.0.0.1"
        assert isinstance(cluster_manager.nodes, dict)
        assert cluster_manager.leader is False
        assert cluster_manager.current_leader is None

    @pytest.mark.asyncio
    async def test_node_registration(self, cluster_manager):
        """Test node registration process."""
        with patch.object(cluster_manager, '_get_hostname', return_value='test-host'):
            with patch.object(cluster_manager, '_get_capacity', return_value=1000000):
                with patch.object(cluster_manager, '_get_zone', return_value='test-zone'):
                    cluster_manager._register_node()
                    assert cluster_manager.node_id in cluster_manager.nodes
                    node = cluster_manager.nodes[cluster_manager.node_id]
                    assert node.status == "READY"
                    assert node.hostname == "test-host"
                    assert node.capacity_bytes == 1000000

    @pytest.mark.asyncio
    async def test_leader_election(self, cluster_manager, mock_storage_nodes):
        """Test leader election process."""
        cluster_manager.nodes = mock_storage_nodes.copy()
        
        # Mock lease creation success
        mock_lease = MagicMock()
        mock_lease.spec.holder_identity = cluster_manager.node_id
        
        with patch.object(cluster_manager.coordination_api, 'create_namespaced_lease') as mock_create_lease:
            mock_create_lease.return_value = mock_lease
            
            await cluster_manager._start_leader_election()
            assert cluster_manager.leader is True

    @pytest.mark.asyncio
    async def test_leader_election_failure(self, cluster_manager):
        """Test leader election when lease already exists."""
        # Mock lease creation failure (409 Conflict)
        api_exception = kubernetes.client.rest.ApiException(status=409)
        
        with patch.object(cluster_manager.coordination_api, 'create_namespaced_lease') as mock_create:
            mock_create.side_effect = api_exception
            
            with patch.object(cluster_manager.coordination_api, 'read_namespaced_lease') as mock_read:
                mock_lease = MagicMock()
                mock_lease.spec.holder_identity = "other-node"
                mock_read.return_value = mock_lease
                
                await cluster_manager._start_leader_election()
                assert cluster_manager.leader is False
                assert cluster_manager.current_leader == "other-node"

    @pytest.mark.asyncio
    async def test_node_failure_handling(self, cluster_manager, mock_storage_nodes):
        """Test handling of node failures."""
        cluster_manager.nodes = mock_storage_nodes.copy()
        cluster_manager.leader = True
        
        # Mock the data redistribution methods
        with patch.object(cluster_manager, '_redistribute_data') as mock_redistribute:
            # Simulate node failure
            cluster_manager._handle_node_failure("node-1")
            
            # Verify node was removed
            assert "node-1" not in cluster_manager.nodes
            
            # Verify redistribution was called
            mock_redistribute.assert_called_once()
            failed_node = mock_redistribute.call_args[0][0]
            assert failed_node.node_id == "node-1"

    def test_target_node_selection(self, cluster_manager, mock_storage_nodes):
        """Test node selection for data placement."""
        cluster_manager.nodes = mock_storage_nodes.copy()
        healthy_nodes = list(mock_storage_nodes.values())
        
        # Test selection based on used capacity ratio
        selected_node = cluster_manager._select_target_node(healthy_nodes)
        assert selected_node.node_id == "node-2"  # Should select node with less used space

    def test_error_handling(self):
        """Test error handling for missing environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                StorageClusterManager()

if __name__ == "__main__":
    pytest.main([__file__])
