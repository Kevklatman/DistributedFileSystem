"""Tests for simulation configuration and initialization."""

import pytest
import asyncio
from dev.simulation import SimulatedMetricsCollector, DEFAULT_CONFIG
from dev.simulation.simulated_collector import NodeLocation

# Test node configuration
TEST_NODES = {
    "node1": NodeLocation(region="us-east-1", zone="a", provider="aws", latency_base=10),
    "node2": NodeLocation(region="us-east-1", zone="b", provider="aws", latency_base=10),
    "node3": NodeLocation(region="us-west1", zone="a", provider="gcp", latency_base=15),
    "node4": NodeLocation(region="us-west1", zone="b", provider="gcp", latency_base=15),
    "edge1": NodeLocation(region="us-east-1", zone="edge", provider="edge", latency_base=25),
}

@pytest.fixture
async def metrics_collector():
    """Create a metrics collector instance for testing."""
    collector = SimulatedMetricsCollector(nodes=TEST_NODES)
    yield collector
    # Cleanup
    await collector.cleanup()

async def test_default_config_values():
    """Test that default configuration values are properly set."""
    # Verify network config
    assert 'network' in DEFAULT_CONFIG
    network_config = DEFAULT_CONFIG['network']
    assert network_config['base_latency'] > 0
    assert network_config['jitter_range'] > 0
    assert network_config['edge_latency_multiplier'] > 1.0
    assert network_config['cross_region_multiplier'] > 1.0

    # Verify resource config
    assert 'resources' in DEFAULT_CONFIG
    resource_config = DEFAULT_CONFIG['resources']
    
    # Check CPU ranges
    assert len(resource_config['cloud_cpu_range']) == 2
    assert resource_config['cloud_cpu_range'][0] < resource_config['cloud_cpu_range'][1]
    assert len(resource_config['edge_cpu_range']) == 2
    assert resource_config['edge_cpu_range'][0] < resource_config['edge_cpu_range'][1]
    
    # Check memory ranges
    assert len(resource_config['cloud_memory_range']) == 2
    assert resource_config['cloud_memory_range'][0] < resource_config['cloud_memory_range'][1]
    assert len(resource_config['edge_memory_range']) == 2
    assert resource_config['edge_memory_range'][0] < resource_config['edge_memory_range'][1]

async def test_config_affects_behavior(metrics_collector: SimulatedMetricsCollector):
    """Test that configuration values affect system behavior."""
    # Test edge node latency
    cloud_latency = await metrics_collector.get_network_latency("node1", "node2")
    edge_latency = await metrics_collector.get_network_latency("edge1", "node1")
    
    edge_multiplier = DEFAULT_CONFIG['network']['edge_latency_multiplier']
    assert edge_latency >= cloud_latency * edge_multiplier * 0.9, \
        f"Edge latency ({edge_latency}ms) should be ~{edge_multiplier}x cloud latency ({cloud_latency}ms)"

    # Test cross-region latency
    same_region = await metrics_collector.get_network_latency("node1", "node2")  # same region
    cross_region = await metrics_collector.get_network_latency("node1", "node3") # different regions
    
    region_multiplier = DEFAULT_CONFIG['network']['cross_region_multiplier']
    assert cross_region >= same_region * region_multiplier * 0.9, \
        f"Cross-region latency ({cross_region}ms) should be ~{region_multiplier}x same-region latency ({same_region}ms)"

async def test_resource_ranges(metrics_collector: SimulatedMetricsCollector):
    """Test that resource usage stays within configured ranges."""
    # Simulate some operations to generate metrics
    await metrics_collector.simulate_operation("node1", "node2", "write", 1024 * 1024)
    await metrics_collector.simulate_operation("edge1", "node1", "write", 1024 * 1024)
    await asyncio.sleep(0.1)  # Wait for metrics to update

    # Test cloud node resources
    cloud_metrics = await metrics_collector.get_node_metrics("node1")
    assert cloud_metrics is not None
    
    cloud_cpu_range = DEFAULT_CONFIG['resources']['cloud_cpu_range']
    cloud_memory_range = DEFAULT_CONFIG['resources']['cloud_memory_range']
    
    assert cloud_cpu_range[0] <= cloud_metrics.cpu_usage <= cloud_cpu_range[1], \
        f"Cloud CPU usage ({cloud_metrics.cpu_usage}) outside range {cloud_cpu_range}"
    assert cloud_memory_range[0] <= cloud_metrics.memory_usage <= cloud_memory_range[1], \
        f"Cloud memory usage ({cloud_metrics.memory_usage}) outside range {cloud_memory_range}"

    # Test edge node resources
    edge_metrics = await metrics_collector.get_node_metrics("edge1")
    assert edge_metrics is not None
    
    edge_cpu_range = DEFAULT_CONFIG['resources']['edge_cpu_range']
    edge_memory_range = DEFAULT_CONFIG['resources']['edge_memory_range']
    
    assert edge_cpu_range[0] <= edge_metrics.cpu_usage <= edge_cpu_range[1], \
        f"Edge CPU usage ({edge_metrics.cpu_usage}) outside range {edge_cpu_range}"
    assert edge_memory_range[0] <= edge_metrics.memory_usage <= edge_memory_range[1], \
        f"Edge memory usage ({edge_metrics.memory_usage}) outside range {edge_memory_range}"

async def test_node_configuration():
    """Test that node configuration is properly applied."""
    # Create collector with custom node config
    custom_nodes = {
        "test_node1": NodeLocation(region="eu-west-1", zone="a", provider="aws", latency_base=20),
        "test_edge1": NodeLocation(region="eu-west-1", zone="edge", provider="edge", latency_base=40),
    }
    
    collector = SimulatedMetricsCollector(nodes=custom_nodes)
    try:
        # Test that nodes are properly configured
        metrics1 = await collector.get_node_metrics("test_node1")
        assert metrics1 is not None, "Should get metrics for custom cloud node"
        
        metrics2 = await collector.get_node_metrics("test_edge1")
        assert metrics2 is not None, "Should get metrics for custom edge node"
        
        # Test that non-existent nodes return None
        metrics3 = await collector.get_node_metrics("nonexistent_node")
        assert metrics3 is None, "Should return None for non-existent node"
        
        # Test latency between custom nodes
        latency = await collector.get_network_latency("test_node1", "test_edge1")
        assert latency > 0, "Should calculate latency between custom nodes"
        
    finally:
        # Cleanup
        await collector.cleanup()

if __name__ == '__main__':
    asyncio.run(pytest.main([__file__]))
