import asyncio
import random
import time
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
from dataclasses import dataclass
from collections import defaultdict

from .scenario_config import ScenarioConfig, NetworkCondition, NodeConfig, RegionConfig
from .network_simulator import NetworkSimulator, NetworkConditions
from .data_store import DataStore  # Import DataStore

logger = logging.getLogger(__name__)


@dataclass
class OperationResult:
    success: bool
    duration: float
    source: str
    destination: str
    operation_type: str
    data_size: int
    error: Optional[str] = None


class NodeSimulator:
    def __init__(self, node_id: str, config: NodeConfig):
        self.node_id = node_id
        self.config = config
        self.cpu_usage = 0.0
        self.memory_usage = 0.0
        self.disk_usage = 0.0
        self.network_in = 0.0
        self.network_out = 0.0
        self.is_failed = False
        self.operations_count = 0
        self.errors_count = 0

    async def simulate_failure(self):
        """Simulate node failure if probability threshold is met"""
        if random.random() < self.config.failure_probability:
            self.is_failed = True
            logger.warning(f"Node {self.node_id} has failed")
            await asyncio.sleep(self.config.recovery_time)
            self.is_failed = False
            logger.info(f"Node {self.node_id} has recovered")
            return True
        return False

    def update_metrics(self, operation_size: int, is_source: bool):
        """Update node metrics based on operation"""
        if is_source:
            self.network_out += operation_size
        else:
            self.network_in += operation_size

        # Simulate CPU usage (operation processing)
        self.cpu_usage = min(100, self.cpu_usage + random.uniform(5, 15))

        # Simulate memory usage
        self.memory_usage = min(100, self.memory_usage + random.uniform(1, 5))

        # Simulate disk usage
        self.disk_usage = min(
            100,
            self.disk_usage
            + (operation_size / (self.config.disk_gb * 1024 * 1024 * 1024)) * 100,
        )

        self.operations_count += 1


class NetworkSimulator:
    """Simulates network conditions between nodes"""

    def __init__(self, conditions: Dict[str, NetworkCondition]):
        self.conditions = conditions

    async def simulate_transfer(
        self, source: str, dest: str, size: int
    ) -> Tuple[bool, float]:
        """
        Simulate a network transfer between nodes

        Args:
            source: Source node ID
            dest: Destination node ID
            size: Size of data in bytes

        Returns:
            Tuple of (success: bool, duration: float)
        """
        # Simulate packet loss
        if random.random() < 0.001:  # 0.1% packet loss
            return False, 0.0

        # Calculate base transfer time based on bandwidth (1 Gbps)
        bandwidth_bytes_per_sec = 1000 * 1024 * 1024 / 8  # 1 Gbps in bytes/sec
        transfer_time = size / bandwidth_bytes_per_sec

        # Add latency with jitter (20ms base, 5ms jitter)
        latency = 20 + random.uniform(-5, 5)  # milliseconds
        total_time = (latency / 1000.0) + transfer_time  # Convert latency to seconds

        # Simulate the transfer time
        await asyncio.sleep(total_time)

        return True, total_time


class ScenarioSimulator:
    def __init__(self, config: ScenarioConfig):
        """Initialize the simulator with a scenario configuration"""
        self.config = config
        self.nodes = {}
        self.network_simulators = {}
        self.metrics_history = {}
        self.results = []

        # Initialize data store
        self.data_store = DataStore(base_dir="simulated_data")

        # Initialize nodes and network simulators for each region
        for region_name, region_config in config.regions.items():
            # Create nodes for each zone in the region
            for zone in region_config.zones:
                node_id = f"{region_name}-{zone}"
                self.nodes[node_id] = NodeSimulator(node_id, region_config.node_config)
                self.metrics_history[node_id] = []

            # Create network simulator for the region
            self.network_simulators[region_name] = NetworkSimulator(
                NetworkConditions(
                    latency_base=20,  # 20ms base latency
                    latency_jitter=5,  # 5ms jitter
                    packet_loss=0.001,  # 0.1% packet loss
                    bandwidth_mbps=1000,  # 1Gbps bandwidth
                )
            )

    def _generate_operation(self) -> Tuple[str, str, str, int]:
        """Generate a random operation based on workload pattern"""
        # Select source and destination regions
        source_region = random.choice(list(self.config.regions.keys()))
        dest_region = random.choice(list(self.config.regions.keys()))

        # Select source and destination nodes
        source_nodes = [
            node_id for node_id in self.nodes if node_id.startswith(source_region)
        ]
        dest_nodes = [
            node_id for node_id in self.nodes if node_id.startswith(dest_region)
        ]

        source = random.choice(source_nodes)
        dest = random.choice(dest_nodes)

        # Select operation type
        op_type = random.choice(["read", "write"])

        # Generate data size based on pattern
        if self.config.workload_pattern == "burst":
            # Burst pattern: 80% small, 20% large
            if random.random() < 0.8:
                size = random.randint(
                    self.config.data_size_range[0], self.config.data_size_range[0] * 10
                )
            else:
                size = random.randint(
                    self.config.data_size_range[1] // 2, self.config.data_size_range[1]
                )
        else:  # random or steady
            size = random.randint(
                self.config.data_size_range[0], self.config.data_size_range[1]
            )

        return op_type, source_region, dest_region, size

    async def _simulate_operation(self) -> OperationResult:
        """Simulate a single operation with network conditions and node behavior"""
        # Generate operation details
        op_type, source_region, dest_region, data_size = self._generate_operation()

        # Get network simulators for the regions
        network_sim = self.network_simulators[source_region]

        # Select source and destination nodes
        source_nodes = [
            node_id for node_id in self.nodes if node_id.startswith(source_region)
        ]
        dest_nodes = [
            node_id for node_id in self.nodes if node_id.startswith(dest_region)
        ]

        source = random.choice(source_nodes)
        dest = random.choice(dest_nodes)

        # Get nodes
        source_node = self.nodes[source]
        dest_node = self.nodes[dest]

        # Check for node failures
        if source_node.is_failed or dest_node.is_failed:
            return OperationResult(
                success=False,
                duration=0,
                source=source,
                destination=dest,
                operation_type=op_type,
                data_size=data_size,
                error="Node failure",
            )

        # Simulate network transfer
        success, duration = await network_sim.simulate_transfer(source, dest, data_size)

        if not success:
            return OperationResult(
                success=False,
                duration=duration,
                source=source,
                destination=dest,
                operation_type=op_type,
                data_size=data_size,
                error="Network failure",
            )

        # Handle data operation
        if op_type == "write":
            # Write data block with replication
            replicas = [dest]
            # Add additional replicas based on replication factor
            available_nodes = [
                n for n in self.nodes if n != dest and not self.nodes[n].is_failed
            ]
            additional_replicas = random.sample(
                available_nodes,
                min(self.config.replication_factor - 1, len(available_nodes)),
            )
            replicas.extend(additional_replicas)

            # Write the block
            block = self.data_store.write_block(data_size, replicas)

            # Update node metrics for all replicas
            for replica in replicas:
                self.nodes[replica].update_metrics(data_size, False)
        else:  # read operation
            # Get random block from source node
            blocks = self.data_store.get_node_blocks(source)
            if not blocks:
                return OperationResult(
                    success=False,
                    duration=duration,
                    source=source,
                    destination=dest,
                    operation_type=op_type,
                    data_size=data_size,
                    error="No data available",
                )

            # Read random block
            block = random.choice(blocks)
            read_block = self.data_store.read_block(block.block_id, source)
            if not read_block:
                return OperationResult(
                    success=False,
                    duration=duration,
                    source=source,
                    destination=dest,
                    operation_type=op_type,
                    data_size=data_size,
                    error="Read failure",
                )

            # Update node metrics
            source_node.update_metrics(block.data_size, True)

        return OperationResult(
            success=True,
            duration=duration,
            source=source,
            destination=dest,
            operation_type=op_type,
            data_size=data_size,
        )

    def _record_metrics(self):
        """Record current metrics for all nodes"""
        timestamp = time.time()
        for node_id, node in self.nodes.items():
            self.metrics_history[node_id].append(
                {
                    "timestamp": timestamp,
                    "cpu_usage": node.cpu_usage,
                    "memory_usage": node.memory_usage,
                    "disk_usage": node.disk_usage,
                    "network_in": node.network_in,
                    "network_out": node.network_out,
                    "operations_count": node.operations_count,
                    "errors_count": node.errors_count,
                }
            )

    async def run(self):
        """Run the simulation scenario"""
        start_time = time.time()
        operations_task = asyncio.create_task(self._run_operations())
        metrics_task = asyncio.create_task(self._record_metrics_loop())

        await asyncio.gather(operations_task, metrics_task)

        return {
            "duration": time.time() - start_time,
            "results": self.results,
            "metrics_history": self.metrics_history,
        }

    async def _run_operations(self):
        """Run operations for the configured duration"""
        end_time = time.time() + self.config.duration

        while time.time() < end_time:
            result = await self._simulate_operation()
            self.results.append(result)

            # Simulate node failures if enabled
            if self.config.failure_injection:
                for node in self.nodes.values():
                    await node.simulate_failure()

            # Add some randomness to operation timing
            await asyncio.sleep(random.uniform(0.1, 1.0))

    async def _record_metrics_loop(self):
        """Continuously record metrics"""
        end_time = time.time() + self.config.duration

        while time.time() < end_time:
            self._record_metrics()
            await asyncio.sleep(1)  # Record metrics every second
