"""Tests for simulation configuration and initialization."""

import pytest
import asyncio
from dev.simulation import SimulatedMetricsCollector, DEFAULT_CONFIG

@pytest.fixture
async def metrics_collector():
    """Create a metrics collector instance for testing."""
    collector = SimulatedMetricsCollector()
    yield collector
    # Cleanup
    await collector.close()

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

async def test_custom_config():
    """Test that custom configuration can be applied."""
    custom_config = {
        'network': {
            'base_latency': 20,
            'jitter_range': 10,
            'edge_latency_multiplier': 3.0,
            'cross_region_multiplier': 2.0,
        },
        'resources': {
            'cloud_cpu_range': (5, 40),
            'cloud_memory_range': (10, 50),
            'edge_cpu_range': (20, 70),
            'edge_memory_range': (30, 80),
        }
    }
    
    collector = SimulatedMetricsCollector(config=custom_config)
    
    # Test that custom config affects latency
    cloud_latency = await metrics_collector.get_network_latency("node1", "node2")
    assert cloud_latency >= custom_config['network']['base_latency'], \
        f"Base latency ({cloud_latency}ms) should respect custom config ({custom_config['network']['base_latency']}ms)"
    
    # Cleanup
    await collector.close()

if __name__ == '__main__':
    asyncio.run(pytest.main([__file__]))
