"""Simulation package for distributed metrics testing.

This package provides tools and utilities for simulating distributed system behavior,
including network latency, resource usage, and metrics collection.
"""

from .simulated_collector import SimulatedMetricsCollector
from .network_simulator import NetworkSimulator

__all__ = [
    'SimulatedMetricsCollector',
    'NetworkSimulator',
]

# Default configuration for simulation
DEFAULT_CONFIG = {
    'network': {
        'base_latency': 10,  # Base latency in ms
        'jitter_range': 5,   # Random jitter range in ms
        'edge_latency_multiplier': 2.0,  # Multiplier for edge node latency
        'cross_region_multiplier': 1.5,  # Multiplier for cross-region latency
    },
    'resources': {
        'cloud_cpu_range': (10, 50),    # CPU usage range for cloud nodes
        'cloud_memory_range': (20, 60),  # Memory usage range for cloud nodes
        'edge_cpu_range': (30, 80),      # CPU usage range for edge nodes
        'edge_memory_range': (40, 90),   # Memory usage range for edge nodes
    }
}
