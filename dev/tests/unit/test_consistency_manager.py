"""Unit tests for the consistency manager."""

import pytest
import asyncio
import logging
from datetime import datetime
from src.storage.infrastructure.data.consistency_manager import (
    ConsistencyManager,
    VersionedData,
    WriteOperation,
)

# Configure logging
logging.basicConfig(level=logging.INFO)


@pytest.fixture
def consistency_manager():
    """Create a consistency manager for testing."""
    return ConsistencyManager(quorum_size=2)


@pytest.mark.asyncio
async def test_get_next_version(consistency_manager):
    """Test getting next version number."""
    # First version should be 1
    assert await consistency_manager.get_next_version("test_data") == 1

    # Add a version and check next
    version_data = VersionedData(
        content=b"test", version=1, timestamp=datetime.now(), checksum="abc123"
    )
    await consistency_manager.update_node_version("node1", "test_data", version_data)
    assert await consistency_manager.get_next_version("test_data") == 2


@pytest.mark.asyncio
async def test_update_node_version(consistency_manager):
    """Test updating node version information."""
    version_data = VersionedData(
        content=b"test", version=1, timestamp=datetime.now(), checksum="abc123"
    )

    await consistency_manager.update_node_version("node1", "test_data", version_data)
    node_data = consistency_manager.get_node_data("node1")

    assert "test_data" in node_data
    assert node_data["test_data"].content == b"test"
    assert node_data["test_data"].version == 1


@pytest.mark.asyncio
async def test_write_operation_strong_consistency(consistency_manager):
    """Test write operation with strong consistency."""
    # Add some nodes first
    version_data = VersionedData(
        content=b"old", version=0, timestamp=datetime.now(), checksum="old123"
    )
    await consistency_manager.update_node_version("node1", "test_data", version_data)
    await consistency_manager.update_node_version("node2", "test_data", version_data)

    # Create write operation
    write_op = WriteOperation(
        data_id="test_data",
        content=b"test",
        version=1,
        checksum="abc123",
        timestamp=datetime.now(),
        consistency_level="strong",
    )

    # Start write
    await consistency_manager.start_write(write_op)

    # Complete write with only one node - should fail
    success = await consistency_manager.complete_write("test_data", {"node1"})
    assert not success

    # Complete write with all nodes - should succeed
    success = await consistency_manager.complete_write("test_data", {"node1", "node2"})
    assert success


@pytest.mark.asyncio
async def test_write_operation_quorum_consistency(consistency_manager):
    """Test write operation with quorum consistency."""
    # Add three nodes first
    version_data = VersionedData(
        content=b"old", version=0, timestamp=datetime.now(), checksum="old123"
    )
    await consistency_manager.update_node_version("node1", "test_data", version_data)
    await consistency_manager.update_node_version("node2", "test_data", version_data)
    await consistency_manager.update_node_version("node3", "test_data", version_data)

    # Create write operation
    write_op = WriteOperation(
        data_id="test_data",
        content=b"test",
        version=1,
        checksum="abc123",
        timestamp=datetime.now(),
        consistency_level="quorum",
    )

    # Start write
    await consistency_manager.start_write(write_op)

    # Complete write with less than quorum - should fail
    success = await consistency_manager.complete_write("test_data", {"node1"})
    assert not success

    # Complete write with quorum - should succeed
    success = await consistency_manager.complete_write("test_data", {"node1", "node2"})
    assert success


@pytest.mark.asyncio
async def test_get_latest_version(consistency_manager):
    """Test getting latest version of data."""
    # Add two versions of data
    version1 = VersionedData(
        content=b"test1", version=1, timestamp=datetime.now(), checksum="abc123"
    )
    version2 = VersionedData(
        content=b"test2", version=2, timestamp=datetime.now(), checksum="def456"
    )

    await consistency_manager.update_node_version("node1", "test_data", version1)
    await consistency_manager.update_node_version("node2", "test_data", version2)

    # With eventual consistency, should get latest version
    latest = await consistency_manager.get_latest_version("test_data", "eventual")
    assert latest.version == 2
    assert latest.content == b"test2"

    # With strong consistency and different versions, should return None
    latest = await consistency_manager.get_latest_version("test_data", "strong")
    assert latest is None


@pytest.mark.asyncio
async def test_complete_write_no_pending_operation(consistency_manager):
    """Test completing a write with no pending operation."""
    # Try to complete a write that was never started
    success = await consistency_manager.complete_write("nonexistent_data", {"node1"})
    assert not success


@pytest.mark.asyncio
async def test_write_operation_empty_nodes(consistency_manager):
    """Test write operation with no active nodes."""
    write_op = WriteOperation(
        data_id="test_data",
        content=b"test",
        version=1,
        checksum="abc123",
        timestamp=datetime.now(),
        consistency_level="strong",
    )

    await consistency_manager.start_write(write_op)
    success = await consistency_manager.complete_write("test_data", set())
    assert not success


@pytest.mark.asyncio
async def test_get_latest_version_nonexistent_data(consistency_manager):
    """Test getting latest version of nonexistent data."""
    latest = await consistency_manager.get_latest_version("nonexistent_data")
    assert latest is None


@pytest.mark.asyncio
async def test_get_node_data_nonexistent_node(consistency_manager):
    """Test getting data for a nonexistent node."""
    version_data = VersionedData(
        content=b"test", version=1, timestamp=datetime.now(), checksum="abc123"
    )
    await consistency_manager.update_node_version("node1", "test_data", version_data)
    node_data = consistency_manager.get_node_data("nonexistent_node")
    assert len(node_data) == 0


@pytest.mark.asyncio
async def test_write_operation_concurrent_updates(consistency_manager):
    """Test concurrent write operations."""
    # Add initial version
    version_data = VersionedData(
        content=b"initial", version=0, timestamp=datetime.now(), checksum="initial123"
    )
    await consistency_manager.update_node_version("node1", "test_data", version_data)
    await consistency_manager.update_node_version("node2", "test_data", version_data)

    # First write operation
    write_op1 = WriteOperation(
        data_id="test_data",
        content=b"test1",
        version=1,
        checksum="abc123",
        timestamp=datetime.now(),
        consistency_level="strong",
    )
    await consistency_manager.start_write(write_op1)
    success1 = await consistency_manager.complete_write("test_data", {"node1", "node2"})
    assert success1

    # Second write operation
    write_op2 = WriteOperation(
        data_id="test_data",
        content=b"test2",
        version=2,
        checksum="def456",
        timestamp=datetime.now(),
        consistency_level="strong",
    )
    await consistency_manager.start_write(write_op2)
    success2 = await consistency_manager.complete_write("test_data", {"node1", "node2"})
    assert success2

    # Verify final state
    latest = await consistency_manager.get_latest_version("test_data", "strong")
    assert latest is not None
    assert latest.version == 2
    assert latest.content == b"test2"
