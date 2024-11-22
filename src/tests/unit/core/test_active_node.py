"""Unit tests for the ActiveNode class and related components."""
import pytest
import asyncio
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, AsyncMock
import aiohttp

from src.storage.core.active_node import (
    ActiveNode, NodeState, ConsistencyLevel, WriteOperation,
    WriteTimeoutError, ConsistencyError, InsufficientNodesError,
    WriteFailureError, NodeUnhealthyError, ReadResult
)

@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        data_path = Path(temp_dir)
        # Create standard subdirectories
        (data_path / "volumes").mkdir()
        (data_path / "metadata").mkdir()
        yield data_path

@pytest.fixture
def active_node(temp_data_dir):
    """Create an ActiveNode instance for testing."""
    node = ActiveNode("test_node_1", data_dir=temp_data_dir)
    yield node
    # Cleanup is handled by temp_data_dir fixture

@pytest.fixture
def mock_cluster_nodes():
    """Create mock cluster nodes."""
    return {
        "node_1": NodeState(
            node_id="node_1",
            status="healthy",
            load=0.5,
            capacity=1000.0,
            last_heartbeat=datetime.now()
        ),
        "node_2": NodeState(
            node_id="node_2",
            status="healthy",
            load=0.3,
            capacity=1000.0,
            last_heartbeat=datetime.now()
        )
    }

class TestActiveNode:
    @pytest.mark.asyncio
    async def test_node_initialization(self, active_node):
        """Test proper initialization of ActiveNode."""
        assert active_node.node_id == "test_node_1"
        assert isinstance(active_node.data_dir, Path)
        assert active_node.quorum_size == 2
        assert isinstance(active_node.cluster_nodes, dict)
        assert active_node.cluster_nodes == {}

    @pytest.mark.asyncio
    async def test_node_health_check(self, active_node, mock_cluster_nodes):
        """Test node health monitoring."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()

        # Mock the health check response
        with patch('aiohttp.ClientSession.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value.__aenter__.return_value.json = AsyncMock(
                return_value={"status": "healthy", "load": 0.5}
            )

            await active_node.check_node_health()
            assert all(node.status == "healthy" for node in active_node.cluster_nodes.values())

    @pytest.mark.asyncio
    async def test_write_operation(self, active_node, mock_cluster_nodes):
        """Test write operation with quorum consistency."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()
        test_data = b"test data"

        # Mock successful write to other nodes
        with patch.object(active_node, 'replicate_write', new_callable=AsyncMock) as mock_replicate:
            mock_replicate.return_value = True

            # Perform write operation
            write_op = WriteOperation(
                data_id="test_1",
                content=test_data,
                version=1,
                checksum="test_checksum",
                timestamp=datetime.now(),
                consistency_level=ConsistencyLevel.QUORUM.value
            )

            result = await active_node.write(write_op)
            assert result is True

    @pytest.mark.asyncio
    async def test_read_operation(self, active_node, mock_cluster_nodes):
        """Test read operation with different consistency levels."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()
        test_data = b"test data"

        # Mock read from other nodes
        with patch.object(active_node, 'read_from_node', new_callable=AsyncMock) as mock_read:
            mock_read.return_value = ReadResult(
                content=test_data,
                version=1,
                timestamp=datetime.now()
            )

            # Test eventual consistency read
            result = await active_node.read(
                "test_1",
                ConsistencyLevel.EVENTUAL.value
            )
            assert result.content == test_data

            # Test quorum consistency read
            result = await active_node.read(
                "test_1",
                ConsistencyLevel.QUORUM.value
            )
            assert result.content == test_data

    @pytest.mark.asyncio
    async def test_node_failure_handling(self, active_node, mock_cluster_nodes):
        """Test handling of node failures."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()

        # Simulate a node failure
        with patch('aiohttp.ClientSession.get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = aiohttp.ClientError

            await active_node.check_node_health()
            # Verify nodes are marked as unhealthy
            assert any(node.status == "unhealthy" for node in active_node.cluster_nodes.values())

    @pytest.mark.asyncio
    async def test_consistency_error_handling(self, active_node, mock_cluster_nodes):
        """Test handling of consistency requirement failures."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()
        test_data = b"test data"

        # Mock failed write to other nodes
        with patch.object(active_node, 'replicate_write', new_callable=AsyncMock) as mock_replicate:
            mock_replicate.return_value = False

            write_op = WriteOperation(
                data_id="test_1",
                content=test_data,
                version=1,
                checksum="test_checksum",
                timestamp=datetime.now(),
                consistency_level=ConsistencyLevel.QUORUM.value
            )

            with pytest.raises(ConsistencyError):
                await active_node.write(write_op)

    @pytest.mark.asyncio
    async def test_load_balancing(self, active_node, mock_cluster_nodes):
        """Test load balancing functionality."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()

        # Test node selection based on load
        selected_node = active_node.load_manager.select_node(active_node.cluster_nodes)
        assert selected_node.node_id == "node_2"  # Should select node with lower load

    @pytest.mark.asyncio
    async def test_data_replication(self, active_node, mock_cluster_nodes):
        """Test data replication across nodes."""
        active_node.cluster_nodes = mock_cluster_nodes.copy()
        test_data = b"test data"

        write_op = WriteOperation(
            data_id="test_1",
            content=test_data,
            version=1,
            checksum="test_checksum",
            timestamp=datetime.now(),
            consistency_level=ConsistencyLevel.STRONG.value
        )

        # Mock successful replication
        with patch.object(active_node.replication_manager, 'replicate', new_callable=AsyncMock) as mock_replicate:
            mock_replicate.return_value = True
            result = await active_node.replicate_write(write_op, ["node_1", "node_2"])
            assert result is True

if __name__ == "__main__":
    pytest.main([__file__])
