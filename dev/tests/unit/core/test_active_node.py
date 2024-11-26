"""Unit tests for the active node functionality."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile
from pathlib import Path

from src.storage.infrastructure.active_node import (
    ActiveNode,
    ConsistencyLevel,
    WriteTimeoutError,
    ConsistencyError,
    InsufficientNodesError,
    WriteFailureError,
    NodeUnhealthyError,
)

@pytest.fixture
def test_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def mock_node(test_data_dir):
    """Create a mock active node."""
    node = ActiveNode(
        node_id="test-node-1",
        data_dir=str(test_data_dir),
        quorum_size=2
    )
    return node

def test_node_initialization(mock_node, test_data_dir):
    """Test that a node is initialized with correct default values."""
    assert mock_node.node_id == "test-node-1"
    assert mock_node.data_dir == str(test_data_dir)
    assert mock_node.quorum_size == 2
    assert mock_node.is_healthy()

@pytest.mark.asyncio
async def test_store_data_success(mock_node):
    """Test successful data storage operation."""
    data = b"test data"
    volume_id = "test-volume"
    block_id = "test-block-1"
    
    result = await mock_node.store_data(
        volume_id=volume_id,
        block_id=block_id,
        data=data,
        consistency_level=ConsistencyLevel.STRONG
    )
    
    assert result.success
    assert result.block_id == block_id
    
    # Verify data was stored
    stored_data = await mock_node.read_data(volume_id, block_id)
    assert stored_data == data

@pytest.mark.asyncio
async def test_store_data_with_replication(mock_node):
    """Test data storage with replication."""
    data = b"test data"
    volume_id = "test-volume"
    block_id = "test-block-2"
    
    # Mock replica nodes
    mock_replicas = [AsyncMock() for _ in range(2)]
    for replica in mock_replicas:
        replica.store_data.return_value = AsyncMock(success=True, block_id=block_id)
    
    with patch.object(mock_node, '_get_replica_nodes', return_value=mock_replicas):
        result = await mock_node.store_data(
            volume_id=volume_id,
            block_id=block_id,
            data=data,
            consistency_level=ConsistencyLevel.STRONG
        )
    
    assert result.success
    # Verify replication calls
    for replica in mock_replicas:
        replica.store_data.assert_called_once_with(
            volume_id=volume_id,
            block_id=block_id,
            data=data,
            consistency_level=ConsistencyLevel.STRONG
        )

@pytest.mark.asyncio
async def test_store_data_timeout():
    """Test handling of write timeout."""
    with tempfile.TemporaryDirectory() as tmpdir:
        node = ActiveNode(
            node_id="test-node-timeout",
            data_dir=tmpdir,
            quorum_size=2,
            write_timeout=0.1  # Very short timeout
        )
        
        # Mock slow replica
        mock_replica = AsyncMock()
        async def slow_store(*args, **kwargs):
            await asyncio.sleep(0.2)  # Longer than timeout
            return AsyncMock(success=True)
        mock_replica.store_data.side_effect = slow_store
        
        with patch.object(node, '_get_replica_nodes', return_value=[mock_replica]):
            with pytest.raises(WriteTimeoutError):
                await node.store_data(
                    volume_id="test-volume",
                    block_id="test-block",
                    data=b"test data",
                    consistency_level=ConsistencyLevel.STRONG
                )

@pytest.mark.asyncio
async def test_insufficient_nodes(mock_node):
    """Test handling of insufficient nodes."""
    data = b"test data"
    volume_id = "test-volume"
    block_id = "test-block-3"
    
    # Mock insufficient replica nodes
    with patch.object(mock_node, '_get_replica_nodes', return_value=[]):
        with pytest.raises(InsufficientNodesError):
            await mock_node.store_data(
                volume_id=volume_id,
                block_id=block_id,
                data=data,
                consistency_level=ConsistencyLevel.STRONG
            )

@pytest.mark.asyncio
async def test_node_health_check(mock_node):
    """Test node health check functionality."""
    assert mock_node.is_healthy()  # Should be healthy by default
    
    # Simulate node becoming unhealthy
    mock_node._mark_unhealthy()
    assert not mock_node.is_healthy()
    
    # Test write operation on unhealthy node
    with pytest.raises(NodeUnhealthyError):
        await mock_node.store_data(
            volume_id="test-volume",
            block_id="test-block",
            data=b"test data",
            consistency_level=ConsistencyLevel.STRONG
        )

if __name__ == "__main__":
    pytest.main(["-v", __file__])
