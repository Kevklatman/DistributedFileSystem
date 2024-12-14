"""Integration tests for distributed metrics collection."""

import pytest
import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import patch

# Add simulation directory to Python path
SIMULATION_PATH = Path(__file__).parent.parent.parent / "simulation"
sys.path.insert(0, str(SIMULATION_PATH))

# Mock prometheus metrics before importing any modules that use them
@pytest.fixture(autouse=True)
def mock_prometheus():
    """Mock prometheus metrics to prevent registration conflicts."""
    with patch('prometheus_client.Gauge', autospec=True) as mock_gauge, \
         patch('prometheus_client.Counter', autospec=True) as mock_counter, \
         patch('prometheus_client.Histogram', autospec=True) as mock_histogram:
        yield

from simulated_collector import SimulatedMetricsCollector, NodeLocation


@pytest.fixture
def test_nodes():
    """Create a test set of nodes in different regions."""
    return {
        "node1": NodeLocation("us-east", "us-east-1a", "aws", 5),
        "node2": NodeLocation("us-west", "us-west-1b", "aws", 5),
        "edge1": NodeLocation("us-east", "mobile-east", "edge", 20),
    }


@pytest.fixture
async def metrics_collector(test_nodes):
    """Create a metrics collector with test nodes."""
    collector = SimulatedMetricsCollector(test_nodes)
    yield collector
    await collector.cleanup()


@pytest.mark.asyncio
async def test_basic_operation_flow(metrics_collector):
    """Test basic operation flow between nodes."""
    # Simulate a write operation
    duration = await metrics_collector.simulate_operation(
        "node1", "node2", "write", 1024 * 1024
    )  # 1MB write
    assert duration > 0, "Operation duration should be positive"

    # Check source node metrics
    metrics = await metrics_collector.get_node_metrics("node1")
    assert metrics.network_out > 0, "Network out should be positive"

    # Check destination node metrics
    metrics = await metrics_collector.get_node_metrics("node2")
    assert metrics.network_in > 0, "Network in should be positive"


@pytest.mark.asyncio
async def test_network_latency(metrics_collector):
    """Test network latency calculations between nodes."""
    # Test latency between different regions
    latency = await metrics_collector.get_network_latency("node1", "node2")
    assert latency > 0, "Latency should be positive"

    # Test latency with edge node
    edge_latency = await metrics_collector.get_network_latency("node1", "edge1")
    assert edge_latency > latency, "Edge node latency should be higher"


@pytest.mark.asyncio
async def test_concurrent_operations(metrics_collector):
    """Test handling of concurrent operations."""
    # Create multiple concurrent operations
    ops = []
    for i in range(5):
        ops.append(
            metrics_collector.simulate_operation(
                "node1", "node2", "write", 1024 * 1024 * (i + 1)
            )
        )

    # Wait for all operations to complete
    durations = await asyncio.gather(*ops)

    # Verify all operations completed
    assert len(durations) == 5, "All operations should complete"
    assert all(d > 0 for d in durations), "All durations should be positive"

    # Check metrics reflect multiple operations
    metrics = await metrics_collector.get_node_metrics("node1")
    assert metrics.operation_count >= 5, "Operation count should reflect all operations"


@pytest.mark.asyncio
async def test_error_handling(metrics_collector):
    """Test error handling for invalid operations."""
    # Test invalid node IDs
    with pytest.raises(ValueError):
        await metrics_collector.simulate_operation(
            "invalid_node", "node2", "write", 1024
        )

    # Test negative data size
    with pytest.raises(ValueError):
        await metrics_collector.simulate_operation(
            "node1", "node2", "write", -1024
        )

    # Check error count in metrics
    metrics = await metrics_collector.get_node_metrics("node1")
    assert metrics.errors >= 0, "Error count should be tracked"


@pytest.mark.asyncio
async def test_metrics_consistency(metrics_collector):
    """Test consistency of metrics across operations."""
    # Perform a sequence of operations
    for i in range(3):
        await metrics_collector.simulate_operation(
            "node1", "node2", "write", 1024 * 1024
        )
        await metrics_collector.simulate_operation(
            "node2", "node1", "read", 512 * 1024
        )

    # Get metrics from all nodes
    all_metrics = await metrics_collector.get_all_metrics()

    # Verify metrics consistency
    assert len(all_metrics) == 3, "Should have metrics for all nodes"
    for node_id, metrics in all_metrics.items():
        assert metrics.operation_count > 0, f"Node {node_id} should have operations"
        assert metrics.network_in >= 0, f"Node {node_id} should have network metrics"
        assert metrics.network_out >= 0, f"Node {node_id} should have network metrics"
        assert metrics.cpu_usage >= 0, f"Node {node_id} should have CPU metrics"
        assert metrics.memory_usage >= 0, f"Node {node_id} should have memory metrics"
