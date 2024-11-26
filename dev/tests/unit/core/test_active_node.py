"""Unit tests for the active node functionality."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

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
def mock_node():
    """Create a mock active node."""
    node = ActiveNode(
        node_id="test-node-1",
        data_dir="/tmp/test-data",
        quorum_size=2
    )
    return node

def test_node_initialization(mock_node):
    """Test that a node is initialized with correct default values."""
    assert mock_node.node_id == "test-node-1"
    assert mock_node.data_dir == "/tmp/test-data"
    assert mock_node.quorum_size == 2

@pytest.mark.asyncio
async def test_write_operation(mock_node):
    """Test that write operations work correctly."""
    data = b"test data"
    volume_id = "test-volume"
    
    # Mock the internal write methods
    mock_node._write_to_disk = AsyncMock(return_value=True)
    mock_node._replicate_to_nodes = AsyncMock(return_value=True)
    
    await mock_node.store_data(volume_id, data, ConsistencyLevel.STRONG)
    
    mock_node._write_to_disk.assert_called_once()
    mock_node._replicate_to_nodes.assert_called_once()

@pytest.mark.asyncio
async def test_write_timeout(mock_node):
    """Test that write timeouts are handled correctly."""
    data = b"test data"
    volume_id = "test-volume"
    
    # Mock write to timeout
    mock_node._write_to_disk = AsyncMock(side_effect=asyncio.TimeoutError)
    
    with pytest.raises(WriteTimeoutError):
        await mock_node.store_data(volume_id, data, ConsistencyLevel.STRONG)

@pytest.mark.asyncio
async def test_insufficient_nodes(mock_node):
    """Test handling of insufficient nodes."""
    data = b"test data"
    volume_id = "test-volume"
    
    # Mock no available nodes
    mock_node._get_healthy_nodes = MagicMock(return_value=[])
    
    with pytest.raises(InsufficientNodesError):
        await mock_node.store_data(volume_id, data, ConsistencyLevel.QUORUM)

if __name__ == "__main__":
    pytest.main([__file__])
