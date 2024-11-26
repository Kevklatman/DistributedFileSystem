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
def metrics_collector(test_nodes):
    """Create a metrics collector with test nodes."""
    return SimulatedMetricsCollector(test_nodes)


@pytest.mark.asyncio
async def test_basic_operation_flow(metrics_collector):
    """Test basic operation flow between nodes."""
    # Simulate a write operation
    duration = await metrics_collector.simulate_operation(
        "node1", "node2", "write", 1024 * 1024
    )  # 1MB write
    assert duration > 0, "Operation duration should be positive"

    # Check source node metrics
    source_metrics = metrics_collector.get_node_metrics("node1")
    assert source_metrics.network_out >= 1024 * 1024, "Source should show outbound traffic"
    assert source_metrics.operation_count > 0, "Operation count should be incremented"

    # Check destination node metrics
    dest_metrics = metrics_collector.get_node_metrics("node2")
    assert dest_metrics.network_in >= 1024 * 1024, "Destination should show inbound traffic"
    assert dest_metrics.operation_count > 0, "Operation count should be incremented"


@pytest.mark.asyncio
async def test_network_latency(metrics_collector):
    """Test network latency calculations between nodes."""
    # Get latency between nodes in different regions
    latency = metrics_collector.get_network_latency("node1", "node2")
    assert latency > 0, "Latency between different regions should be positive"

    # Get latency between nodes in same region
    latency = metrics_collector.get_network_latency("node1", "edge1")
    assert latency >= 0, "Latency in same region should be non-negative"


@pytest.mark.asyncio
async def test_concurrent_operations(metrics_collector):
    """Test handling of concurrent operations."""
    # Define multiple operations
    operations = [
        ("node1", "node2", "write", 512 * 1024),  # 512KB write
        ("node2", "edge1", "read", 256 * 1024),   # 256KB read
        ("edge1", "node1", "write", 1024 * 1024), # 1MB write
    ]

    # Run operations concurrently
    tasks = [
        metrics_collector.simulate_operation(src, dst, op, size)
        for src, dst, op, size in operations
    ]
    durations = await asyncio.gather(*tasks)

    # Verify all operations completed
    assert all(d > 0 for d in durations), "All operations should complete successfully"

    # Check system-wide metrics
    all_metrics = metrics_collector.get_all_metrics()
    assert len(all_metrics) == 3, "Should have metrics for all nodes"

    # Verify operation counts
    total_ops = sum(m.operation_count for m in all_metrics.values())
    assert total_ops >= len(operations), "Total operations should match or exceed test operations"


@pytest.mark.asyncio
async def test_error_handling(metrics_collector):
    """Test error handling for invalid operations."""
    # Test invalid node
    with pytest.raises(KeyError):
        await metrics_collector.simulate_operation(
            "nonexistent_node", "node1", "write", 1024
        )

    # Test invalid operation type
    with pytest.raises(ValueError):
        await metrics_collector.simulate_operation(
            "node1", "node2", "invalid_op", 1024
        )

    # Test negative size
    with pytest.raises(ValueError):
        await metrics_collector.simulate_operation(
            "node1", "node2", "write", -1024
        )


@pytest.mark.asyncio
async def test_metrics_consistency(metrics_collector):
    """Test consistency of metrics across operations."""
    # Initial metrics
    initial_metrics = metrics_collector.get_all_metrics()
    
    # Perform a sequence of operations
    ops = [
        ("node1", "node2", "write", 1024 * 1024),
        ("node2", "node1", "read", 512 * 1024),
    ]
    
    for src, dst, op, size in ops:
        await metrics_collector.simulate_operation(src, dst, op, size)
    
    # Final metrics
    final_metrics = metrics_collector.get_all_metrics()
    
    # Verify metrics changes
    for node in initial_metrics:
        initial = initial_metrics[node]
        final = final_metrics[node]
        
        # Operation count should increase
        assert final.operation_count > initial.operation_count, \
            f"Operation count should increase for {node}"
        
        # Network traffic should increase
        assert final.network_in + final.network_out > \
               initial.network_in + initial.network_out, \
            f"Network traffic should increase for {node}"
        
        # Resource usage should be within bounds
        assert 0 <= final.cpu_usage <= 100, "CPU usage should be between 0 and 100"
        assert 0 <= final.memory_usage <= 100, "Memory usage should be between 0 and 100"
        assert 0 <= final.disk_usage <= 100, "Disk usage should be between 0 and 100"
