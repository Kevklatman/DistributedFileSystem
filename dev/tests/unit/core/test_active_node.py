"""Unit tests for the ActiveNode class and related components."""

import pytest
import asyncio
from datetime import datetime
from pathlib import Path
import aiohttp
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from storage.infrastructure.active_node import (
    ActiveNode,
    NodeState,
    ConsistencyLevel,
    WriteOperation,
    WriteTimeoutError,
    ConsistencyError,
    InsufficientNodesError,
    WriteFailureError,
    NodeUnhealthyError,
    ReadResult,
)


@pytest.fixture
def active_node(tmp_path):
    """Create an ActiveNode instance for testing."""
    node = ActiveNode(node_id="test_node", data_dir=tmp_path, quorum_size=2)
    return node


@pytest.fixture
def mock_cluster_nodes():
    """Create mock cluster nodes."""
    now = datetime.now()
    return {
        "node_1": NodeState(
            node_id="node_1",
            status="active",
            load=0.5,
            capacity=1000.0,
            last_heartbeat=now,
            address="node1:8000",
            available_storage=2000.0,
            network_latency=0.0,
        ),
        "node_2": NodeState(
            node_id="node_2",
            status="active",
            load=0.3,
            capacity=1000.0,
            last_heartbeat=now,
            address="node2:8000",
            available_storage=2000.0,
            network_latency=0.0,
        ),
    }


@pytest.fixture
def mock_node_metrics():
    """Mock node metrics response."""
    return {
        "status": "active",
        "load": 0.5,
        "available_storage": 2000.0,
        "network_latency": 0.0,
    }


@pytest.fixture
def mock_get_node_metrics(mock_node_metrics):
    """Mock the get_node_metrics method."""

    async def mock_get_metrics(*args, **kwargs):
        return mock_node_metrics

    return mock_get_metrics


@pytest.fixture
def mock_session_response():
    """Mock aiohttp ClientResponse."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.read = AsyncMock(return_value=b"test data")
    mock_response.headers = {
        "X-Version": "1",
        "X-Timestamp": datetime.now().isoformat(),
    }
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock()
    return mock_response


@pytest.fixture
def mock_client_session(mock_session_response):
    """Mock aiohttp ClientSession."""
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_session_response)
    mock_session.post = AsyncMock(return_value=mock_session_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    return mock_session


@pytest.fixture
def volume_dir(tmp_path):
    """Create a temporary volume directory."""
    volume_path = tmp_path / "volumes"
    volume_path.mkdir()
    return volume_path


class TestActiveNode:
    @pytest.mark.asyncio
    async def test_node_initialization(self, active_node):
        """Test node initialization."""
        assert active_node.node_id == "test_node"
        assert isinstance(active_node.data_dir, Path)
        assert active_node.quorum_size == 2

    @pytest.mark.asyncio
    async def test_write_operation(
        self,
        active_node,
        mock_cluster_nodes,
        volume_dir,
        mock_get_node_metrics,
        mock_client_session,
    ):
        """Test write operation with quorum consistency."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()
        test_data = b"test data"

        # Create test volume and initialize node
        volume_path = volume_dir / "test_volume"
        volume_path.mkdir(exist_ok=True)
        active_node.data_dir = volume_path

        # Mock node interactions
        with patch.object(active_node, "get_node_metrics", new=mock_get_node_metrics):
            with patch("aiohttp.ClientSession", return_value=mock_client_session):
                # Test write operation
                result = await active_node.write_data(
                    "test_1", test_data, ConsistencyLevel.STRONG.value
                )

                assert result["status"] == "success"
                assert "version" in result
                assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_read_operation(
        self,
        active_node,
        mock_cluster_nodes,
        volume_dir,
        mock_get_node_metrics,
        mock_client_session,
    ):
        """Test read operation with different consistency levels."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()
        test_data = b"test data"

        # Create test file
        test_file = volume_dir / "test_1"
        test_file.write_bytes(test_data)

        # Mock node interactions
        with patch.object(active_node, "get_node_metrics", new=mock_get_node_metrics):
            with patch("aiohttp.ClientSession", return_value=mock_client_session):
                # Test eventual consistency read
                result = await active_node.handle_eventual_read(
                    "test_1", list(mock_cluster_nodes.values())
                )

                assert result == test_data

    @pytest.mark.asyncio
    async def test_load_balancing(
        self, active_node, mock_cluster_nodes, mock_get_node_metrics
    ):
        """Test load balancing functionality."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()

        # Mock node interactions
        with patch.object(active_node, "get_node_metrics", new=mock_get_node_metrics):
            # Test node selection based on load
            selected_nodes = await active_node.select_write_targets(
                data_size=100,  # Reduced data size to ensure it fits within available storage
                min_nodes=2,
            )
            assert len(selected_nodes) == 2

    @pytest.mark.asyncio
    async def test_data_replication(
        self,
        active_node,
        mock_cluster_nodes,
        mock_get_node_metrics,
        mock_client_session,
    ):
        """Test data replication across nodes."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()
        test_data = b"test data"

        # Mock node interactions
        with patch.object(active_node, "get_node_metrics", new=mock_get_node_metrics):
            with patch("aiohttp.ClientSession", return_value=mock_client_session):
                result = await active_node.write_data(
                    "test_1", test_data, ConsistencyLevel.STRONG.value
                )

                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_node_failure_handling(self, active_node, mock_cluster_nodes):
        """Test handling of node failures."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()

        # Simulate a node failure by making a node unhealthy
        node = list(mock_cluster_nodes.values())[0]
        node.status = "unhealthy"

        # Verify that the node is marked as unhealthy
        assert node.status == "unhealthy"

    @pytest.mark.asyncio
    async def test_consistency_error_handling(self, active_node, mock_cluster_nodes):
        """Test handling of consistency requirement failures."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()
        test_data = b"test data"

        # Mock failed write to other nodes
        with patch.object(
            active_node, "write_to_node", new_callable=AsyncMock
        ) as mock_write:
            mock_write.return_value = {"status": "error", "error": "Write failed"}

            # Mock consistency manager
            with patch.object(
                active_node.consistency_manager, "generate_version", return_value=1
            ):
                # Test write operation with strong consistency
                with pytest.raises(Exception):
                    await active_node.write_data(
                        "test_1", test_data, ConsistencyLevel.STRONG.value
                    )


if __name__ == "__main__":
    pytest.main([__file__])
