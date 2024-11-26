"""Integration tests for distributed metrics collection."""

import pytest
import asyncio
from typing import Dict, Any
from simulation import NodeLocation, SimulatedMetricsCollector

pytestmark = pytest.mark.asyncio

async def test_basic_operation_flow(metrics_collector: SimulatedMetricsCollector):
    """Test basic metrics collection flow."""
    # Simulate some operations
    await metrics_collector.simulate_operation("node1", "node2", "write", 1024 * 1024)
    await metrics_collector.simulate_operation("node2", "node3", "read", 512 * 1024)

    # Get metrics and verify
    metrics = await metrics_collector.get_metrics()
    assert metrics is not None
    assert "node1_cpu" in metrics
    assert "node2_memory" in metrics
    assert "node3_network_in" in metrics

async def test_network_latency(metrics_collector: SimulatedMetricsCollector):
    """Test network latency calculations between nodes."""
    # Test latency between nodes in different regions
    samples = 10
    same_region_latencies = []
    diff_region_latencies = []

    # Collect multiple samples
    for _ in range(samples):
        # Same region (edge to AWS in us-east)
        same_region_latencies.append(
            await metrics_collector.get_network_latency("node1", "edge1")
        )
        # Different regions (us-east to us-west)
        diff_region_latencies.append(
            await metrics_collector.get_network_latency("node1", "node2")
        )

    # Calculate average latencies
    avg_same_region = sum(same_region_latencies) / samples
    avg_diff_region = sum(diff_region_latencies) / samples

    # Cross-region latency should be higher on average
    assert avg_diff_region > avg_same_region, \
        f"Cross-region latency ({avg_diff_region:.2f}ms) should be higher than same-region ({avg_same_region:.2f}ms)"

    # Verify latency affects operation time
    start_time = asyncio.get_event_loop().time()
    await metrics_collector.simulate_operation("node1", "node2", "write", 1024)
    end_time = asyncio.get_event_loop().time()

    operation_time = end_time - start_time
    assert operation_time >= (min(diff_region_latencies) / 1000), \
        "Operation time should reflect network latency"

async def test_concurrent_operations(metrics_collector: SimulatedMetricsCollector):
    """Test handling of concurrent operations."""
    nodes = ["node1", "node2", "edge1"]
    
    # Get initial operation counts
    initial_counts = {}
    for node in nodes:
        metrics = await metrics_collector.get_node_metrics(node)
        assert metrics is not None, f"No initial metrics for {node}"
        initial_counts[node] = metrics.operation_count

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
    await asyncio.gather(*tasks)

    # Wait briefly for metrics to update
    await asyncio.sleep(0.1)

    # Verify operation counts increased
    for node in nodes:
        metrics = await metrics_collector.get_node_metrics(node)
        assert metrics is not None, f"No metrics found for {node}"
        assert metrics.operation_count > initial_counts[node], \
            f"Operation count did not increase for {node} (was {initial_counts[node]}, now {metrics.operation_count})"

    # Verify network metrics
    for node in nodes:
        metrics = await metrics_collector.get_node_metrics(node)
        assert metrics is not None
        assert metrics.network_in > 0 or metrics.network_out > 0, \
            f"Node {node} should have some network activity"

async def test_error_handling(metrics_collector: SimulatedMetricsCollector):
    """Test error handling for invalid operations."""
    # Test invalid node
    with pytest.raises(ValueError, match="Invalid node ID"):
        await metrics_collector.simulate_operation(
            "nonexistent_node", "node1", "write", 1024
        )

    # Test invalid operation size
    with pytest.raises(ValueError, match="Data size must be non-negative"):
        await metrics_collector.simulate_operation(
            "node1", "node2", "write", -1024
        )

async def test_metrics_consistency(metrics_collector: SimulatedMetricsCollector):
    """Test consistency of metrics across operations."""
    # Get initial metrics
    initial = await metrics_collector.get_node_metrics("node1")
    assert initial is not None, "Failed to get initial metrics"
    initial_count = initial.operation_count
    initial_network_out = initial.network_out

    # Perform multiple operations with different sizes
    operations = [
        ("write", 1024 * 1024),      # 1MB
        ("write", 512 * 1024),       # 512KB
        ("read", 2 * 1024 * 1024),   # 2MB
    ]

    expected_network_out = initial_network_out
    for op, size in operations:
        await metrics_collector.simulate_operation("node1", "node2", op, size)
        if op == "write":
            expected_network_out += size
        await asyncio.sleep(0.1)  # Wait for metrics to update

    # Get final metrics
    final = await metrics_collector.get_node_metrics("node1")
    assert final is not None, "Failed to get final metrics"
    
    # Verify operation count increased by the number of operations
    assert final.operation_count == initial_count + len(operations), \
        f"Operation count should increase by {len(operations)} (was {initial_count}, now {final.operation_count})"

    # Verify network metrics are consistent
    assert abs(final.network_out - expected_network_out) < 1024, \
        f"Network out should match expected (expected {expected_network_out}, got {final.network_out})"

    # Verify resource usage metrics are within bounds
    assert 0 <= final.cpu_usage <= 100, f"CPU usage out of bounds: {final.cpu_usage}"
    assert 0 <= final.memory_usage <= 100, f"Memory usage out of bounds: {final.memory_usage}"
    assert 0 <= final.disk_usage <= 100, f"Disk usage out of bounds: {final.disk_usage}"

async def test_provider_specific_behavior(metrics_collector: SimulatedMetricsCollector):
    """Test provider-specific behavior in metrics."""
    # Test multiple samples to ensure consistent behavior
    samples = 10

    # Test latency between different providers
    aws_latencies = []
    gcp_latencies = []
    edge_latencies = []

    for _ in range(samples):
        # AWS to AWS (same region)
        aws_latencies.append(
            await metrics_collector.get_network_latency("node1", "node2")
        )
        # GCP to GCP (same region)
        gcp_latencies.append(
            await metrics_collector.get_network_latency("node3", "node4")
        )
        # Edge to nearest cloud
        edge_latencies.append(
            await metrics_collector.get_network_latency("edge1", "node1")
        )

    # Calculate average latencies
    avg_aws = sum(aws_latencies) / samples
    avg_gcp = sum(gcp_latencies) / samples
    avg_edge = sum(edge_latencies) / samples

    # Edge latency should be higher due to last-mile network
    assert avg_edge > avg_aws and avg_edge > avg_gcp, \
        f"Edge latency ({avg_edge:.2f}ms) should be higher than cloud latencies (AWS: {avg_aws:.2f}ms, GCP: {avg_gcp:.2f}ms)"

    # Test operation performance
    size = 1024 * 1024  # 1MB
    
    # Measure AWS operation time
    start = asyncio.get_event_loop().time()
    await metrics_collector.simulate_operation("node1", "node2", "write", size)
    aws_time = asyncio.get_event_loop().time() - start

    # Measure edge operation time
    start = asyncio.get_event_loop().time()
    await metrics_collector.simulate_operation("edge1", "node1", "write", size)
    edge_time = asyncio.get_event_loop().time() - start

    # Edge operations should take longer
    assert edge_time > aws_time, \
        f"Edge operations ({edge_time:.3f}s) should be slower than cloud operations ({aws_time:.3f}s)"

    # Verify resource metrics are provider-appropriate
    aws_metrics = await metrics_collector.get_node_metrics("node1")
    edge_metrics = await metrics_collector.get_node_metrics("edge1")

    assert aws_metrics is not None and edge_metrics is not None, "Failed to get metrics"

    # Edge nodes should have lower resource availability
    assert edge_metrics.cpu_usage > aws_metrics.cpu_usage, \
        "Edge nodes should show higher CPU usage"
    assert edge_metrics.memory_usage > aws_metrics.memory_usage, \
        "Edge nodes should show higher memory usage"

async def test_basic_operation_flow(metrics_collector: SimulatedMetricsCollector):
    """Test basic operation flow between nodes."""
    # Simulate a write operation
    await metrics_collector.simulate_operation("node1", "node2", "write", 1024 * 1024)  # 1MB write

    # Check source node metrics
    source_metrics = await metrics_collector.get_node_metrics("node1")
    assert source_metrics.network_out >= 1024 * 1024, "Source should show outbound traffic"
    assert source_metrics.operation_count > 0, "Operation count should be incremented"

    # Check destination node metrics
    dest_metrics = await metrics_collector.get_node_metrics("node2")
    assert dest_metrics.network_in >= 1024 * 1024, "Destination should show inbound traffic"
    assert dest_metrics.operation_count > 0, "Operation count should be incremented"

async def test_network_latency(metrics_collector: SimulatedMetricsCollector, test_nodes):
    """Test network latency calculations between nodes."""
    # Get latency between nodes in different regions
    latency = await metrics_collector.get_network_latency("node1", "node2")
    assert latency > 0, "Latency between different regions should be positive"

    # Get latency between nodes in same region
    latency = await metrics_collector.get_network_latency("node1", "edge1")
    assert latency >= 0, "Latency in same region should be non-negative"

    # Verify latency is higher for nodes in different regions
    same_region_latency = await metrics_collector.get_network_latency("node1", "edge1")
    diff_region_latency = await metrics_collector.get_network_latency("node1", "node2")
    assert diff_region_latency > same_region_latency, "Cross-region latency should be higher"

async def test_concurrent_operations(metrics_collector: SimulatedMetricsCollector):
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
    await asyncio.gather(*tasks)

    # Verify all operations completed
    assert all(await metrics_collector.get_node_metrics(node).operation_count > 0 for node in ["node1", "node2", "edge1"]), "All operations should complete successfully"

    # Check system-wide metrics
    all_metrics = await metrics_collector.get_all_metrics()
    assert len(all_metrics) == 3, "Should have metrics for all nodes"

    # Verify operation counts
    total_ops = sum(await metrics_collector.get_node_metrics(node).operation_count for node in ["node1", "node2", "edge1"])
    assert total_ops >= len(operations), "Total operations should match or exceed test operations"

async def test_error_handling(metrics_collector: SimulatedMetricsCollector):
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

async def test_metrics_consistency(metrics_collector: SimulatedMetricsCollector):
    """Test consistency of metrics across operations."""
    # Initial metrics
    initial_metrics = await metrics_collector.get_all_metrics()
    
    # Perform a sequence of operations
    ops = [
        ("node1", "node2", "write", 1024 * 1024),
        ("node2", "node1", "read", 512 * 1024),
    ]
    
    for src, dst, op, size in ops:
        await metrics_collector.simulate_operation(src, dst, op, size)
    
    # Final metrics
    final_metrics = await metrics_collector.get_all_metrics()
    
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

async def test_provider_specific_behavior(metrics_collector: SimulatedMetricsCollector, test_nodes):
    """Test provider-specific behavior and metrics."""
    # Test AWS node latency characteristics
    aws_latency = await metrics_collector.get_network_latency("node1", "node2")  # AWS to AWS
    assert 5 <= aws_latency <= 100, "AWS inter-region latency should be reasonable"

    # Test edge node characteristics
    edge_metrics = await metrics_collector.get_node_metrics("edge1")
    assert edge_metrics is not None, "Edge node metrics should be available"
    
    # Edge nodes typically have higher latency
    edge_latency = await metrics_collector.get_network_latency("edge1", "node1")  # Edge to AWS
    assert edge_latency > aws_latency, "Edge to cloud latency should be higher than cloud-to-cloud"

    # Test large file transfer to edge node
    await metrics_collector.simulate_operation(
        "node1", "edge1", "write", 10 * 1024 * 1024  # 10MB write
    )
    
    # Verify edge node metrics after operation
    edge_metrics_after = await metrics_collector.get_node_metrics("edge1")
    assert edge_metrics_after.network_in > edge_metrics.network_in, \
        "Edge node should show increased network usage"
