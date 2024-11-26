import time
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging
from collections import defaultdict
from storage.metrics.collector import MetricsCollector, NetworkMetrics

logger = logging.getLogger(__name__)


# e
@dataclass
class NodeLocation:
    region: str
    zone: str
    provider: str  # 'aws', 'gcp', 'azure', 'edge'
    latency_base: float  # Base latency in ms for this location


@dataclass
class SimulatedNodeMetrics:
    node_id: str
    location: NodeLocation
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_in: float = 0.0
    network_out: float = 0.0
    operation_count: int = 0
    errors: int = 0
    last_update: float = field(default_factory=time.time)


class NetworkSimulator:
    """Simulates network conditions between different regions and cloud providers."""

    # Base latencies between regions (ms)
    REGION_LATENCIES = {
        ("us-east", "us-west"): 60,
        ("us-east", "eu-west"): 80,
        ("us-east", "ap-south"): 200,
        ("us-west", "eu-west"): 100,
        ("us-west", "ap-south"): 150,
        ("eu-west", "ap-south"): 120,
    }

    # Provider-specific latency adjustments (ms)
    PROVIDER_ADJUSTMENTS = {
        "aws": 1.0,  # baseline
        "gcp": 1.1,  # 10% slower
        "azure": 1.2,  # 20% slower
        "edge": 2.0,  # edge nodes have higher latency
    }

    @classmethod
    def get_latency(cls, source: NodeLocation, dest: NodeLocation) -> float:
        """Calculate simulated latency between two locations."""
        if source.region == dest.region:
            return random.uniform(1, 5)  # Local latency 1-5ms

        # Get base latency
        regions = tuple(sorted([source.region, dest.region]))
        base_latency = cls.REGION_LATENCIES.get(regions, 150)  # Default 150ms

        # Apply provider adjustments
        provider_factor = max(
            cls.PROVIDER_ADJUSTMENTS[source.provider],
            cls.PROVIDER_ADJUSTMENTS[dest.provider],
        )

        # Add jitter (±10%)
        jitter = random.uniform(-0.1, 0.1) * base_latency

        return (base_latency * provider_factor) + jitter


class SimulatedMetricsCollector(MetricsCollector):
    """Metrics collector that simulates a distributed system."""

    def __init__(self, nodes: Dict[str, NodeLocation]):
        """Initialize simulated metrics collector.

        Args:
            nodes: Dictionary mapping node IDs to their locations
        """
        self.nodes = nodes
        self.network_sim = NetworkSimulator()
        self._metrics: Dict[str, SimulatedNodeMetrics] = {
            node_id: SimulatedNodeMetrics(node_id=node_id, location=location)
            for node_id, location in nodes.items()
        }
        self._operation_latencies = defaultdict(list)
        self._lock = asyncio.Lock()
        self._start_simulation()

    def _start_simulation(self):
        """Start background simulation of metrics."""
        asyncio.create_task(self._simulate_metrics())

    async def _simulate_metrics(self):
        """Continuously simulate metrics for all nodes."""
        while True:
            for node_id, metrics in self._metrics.items():
                # Simulate CPU usage (fluctuating between 10-90%)
                metrics.cpu_usage = min(
                    90, max(10, metrics.cpu_usage + random.uniform(-5, 5))
                )

                # Simulate memory usage (more stable, 20-80%)
                metrics.memory_usage = min(
                    80, max(20, metrics.memory_usage + random.uniform(-2, 2))
                )

                # Simulate disk usage (slowly increasing)
                metrics.disk_usage = min(
                    95, metrics.disk_usage + random.uniform(0, 0.1)
                )

                # Simulate network I/O
                metrics.network_in = max(0, metrics.network_in + random.uniform(-1, 1))
                metrics.network_out = max(
                    0, metrics.network_out + random.uniform(-1, 1)
                )

                metrics.last_update = time.time()

            await asyncio.sleep(1)  # Update every second

    async def simulate_operation(
        self, source_node: str, dest_node: str, operation: str, data_size: int
    ) -> float:
        """Simulate a storage operation between nodes.

        Args:
            source_node: ID of source node
            dest_node: ID of destination node
            operation: Type of operation (e.g., 'read', 'write')
            data_size: Size of data in bytes

        Returns:
            Simulated operation duration in seconds
        """
        if source_node not in self._metrics or dest_node not in self._metrics:
            raise ValueError("Invalid node ID")

        # Calculate network latency
        latency = self.network_sim.get_latency(
            self.nodes[source_node], self.nodes[dest_node]
        )

        # Simulate network transfer time based on data size
        # Assume average speed of 100MB/s with variation
        transfer_speed = random.uniform(50, 150) * 1024 * 1024  # bytes/s
        transfer_time = data_size / transfer_speed

        # Total operation time
        total_time = (latency / 1000) + transfer_time  # Convert latency to seconds

        # Update metrics
        source_metrics = self._metrics[source_node]
        dest_metrics = self._metrics[dest_node]

        source_metrics.operation_count += 1
        dest_metrics.operation_count += 1

        if operation == "write":
            source_metrics.network_out += data_size
            dest_metrics.network_in += data_size
        else:  # read
            source_metrics.network_in += data_size
            dest_metrics.network_out += data_size

        # Simulate the operation time
        await asyncio.sleep(total_time)
        return total_time

    def record_operation_latency(self, operation: str, duration: float) -> None:
        """Record the latency of an operation."""
        with self._lock:
            self._operation_latencies[operation].append(duration)
            # Keep only last 1000 samples per operation
            if len(self._operation_latencies[operation]) > 1000:
                self._operation_latencies[operation] = self._operation_latencies[
                    operation
                ][-1000:]

    def record_resource_usage(
        self, cpu: float, memory: float, disk_io: float, network_io: float
    ) -> None:
        """Record system resource usage."""
        # In simulation mode, resource usage is handled by _simulate_metrics
        pass

    def record_volume_operation(
        self, volume_id: str, operation: str, size: int
    ) -> None:
        """Record a volume operation."""
        # In simulation mode, volume operations are handled by simulate_operation
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        metrics = {}
        for node_id, node_metrics in self._metrics.items():
            metrics[f"{node_id}_cpu"] = node_metrics.cpu_usage
            metrics[f"{node_id}_memory"] = node_metrics.memory_usage
            metrics[f"{node_id}_disk"] = node_metrics.disk_usage
            metrics[f"{node_id}_network_in"] = node_metrics.network_in
            metrics[f"{node_id}_network_out"] = node_metrics.network_out
            metrics[f"{node_id}_ops"] = node_metrics.operation_count
        return metrics

    def get_node_metrics(self, node_id: str) -> Optional[SimulatedNodeMetrics]:
        """Get current metrics for a specific node."""
        return self._metrics.get(node_id)

    def get_all_metrics(self) -> Dict[str, SimulatedNodeMetrics]:
        """Get current metrics for all nodes."""
        return self._metrics.copy()

    def get_network_latency(self, source_node: str, dest_node: str) -> float:
        """Get the current simulated network latency between two nodes."""
        if source_node not in self.nodes or dest_node not in self.nodes:
            raise ValueError("Invalid node ID")

        return self.network_sim.get_latency(
            self.nodes[source_node], self.nodes[dest_node]
        )
