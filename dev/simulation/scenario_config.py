from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random


@dataclass
class NetworkCondition:
    latency_base: float  # Base latency in ms
    latency_jitter: float  # Percentage of jitter (0-1)
    packet_loss: float  # Probability of packet loss (0-1)
    bandwidth: float  # MB/s
    bandwidth_variation: float  # Percentage of variation (0-1)
    congestion_probability: float  # Probability of network congestion (0-1)
    failure_probability: float  # Probability of complete failure (0-1)


@dataclass
class NodeConfig:
    cpu_cores: int
    memory_gb: float
    disk_gb: float
    disk_speed: float  # MB/s
    network_capacity: float  # MB/s
    failure_probability: float  # Probability of node failure (0-1)
    recovery_time: float  # Average time to recover in seconds


@dataclass
class RegionConfig:
    name: str
    zones: List[str]
    network_conditions: Dict[str, NetworkCondition]  # Target region -> conditions
    node_config: NodeConfig


@dataclass
class ScenarioConfig:
    """Configuration for a simulation scenario"""

    name: str
    description: str
    duration: int  # Duration in seconds
    regions: Dict[str, RegionConfig]
    workload_pattern: str  # 'random', 'burst', 'steady'
    data_size_range: tuple  # (min_bytes, max_bytes)
    replication_factor: int
    consistency_level: str  # 'strong', 'eventual', 'quorum'
    edge_enabled: bool
    cache_size_mb: int
    failure_injection: bool


class ScenarioGenerator:
    """Generates various test scenarios"""

    @staticmethod
    def create_base_network_condition(distance: str) -> NetworkCondition:
        """Create network conditions based on distance category"""
        if distance == "local":
            return NetworkCondition(
                latency_base=5,
                latency_jitter=0.1,
                packet_loss=0.001,
                bandwidth=1000,
                bandwidth_variation=0.1,
                congestion_probability=0.01,
                failure_probability=0.001,
            )
        elif distance == "regional":
            return NetworkCondition(
                latency_base=50,
                latency_jitter=0.2,
                packet_loss=0.005,
                bandwidth=500,
                bandwidth_variation=0.2,
                congestion_probability=0.05,
                failure_probability=0.005,
            )
        else:  # international
            return NetworkCondition(
                latency_base=200,
                latency_jitter=0.3,
                packet_loss=0.01,
                bandwidth=100,
                bandwidth_variation=0.3,
                congestion_probability=0.1,
                failure_probability=0.01,
            )

    @staticmethod
    def create_node_config(size: str) -> NodeConfig:
        """Create node configuration based on size category"""
        if size == "small":
            return NodeConfig(
                cpu_cores=2,
                memory_gb=4,
                disk_gb=100,
                disk_speed=100,
                network_capacity=100,
                failure_probability=0.01,
                recovery_time=30,
            )
        elif size == "medium":
            return NodeConfig(
                cpu_cores=4,
                memory_gb=8,
                disk_gb=500,
                disk_speed=200,
                network_capacity=500,
                failure_probability=0.005,
                recovery_time=20,
            )
        else:  # large
            return NodeConfig(
                cpu_cores=8,
                memory_gb=16,
                disk_gb=1000,
                disk_speed=500,
                network_capacity=1000,
                failure_probability=0.001,
                recovery_time=10,
            )

    @classmethod
    def generate_high_availability_scenario(cls) -> ScenarioConfig:
        """Generate a scenario focused on high availability"""
        config = ScenarioConfig(
            name="high_availability",
            description="High availability scenario with multi-region deployment",
            duration=3600,  # 1 hour
            regions={
                "us-east": RegionConfig(
                    name="us-east",
                    zones=["us-east-1a", "us-east-1b", "us-east-1c"],
                    network_conditions={
                        "us-west": cls.create_base_network_condition("regional"),
                        "eu-west": cls.create_base_network_condition("international"),
                    },
                    node_config=cls.create_node_config("large"),
                ),
                "us-west": RegionConfig(
                    name="us-west",
                    zones=["us-west-1a", "us-west-1b"],
                    network_conditions={
                        "us-east": cls.create_base_network_condition("regional"),
                        "eu-west": cls.create_base_network_condition("international"),
                    },
                    node_config=cls.create_node_config("large"),
                ),
                "eu-west": RegionConfig(
                    name="eu-west",
                    zones=["eu-west-1a", "eu-west-1b"],
                    network_conditions={
                        "us-east": cls.create_base_network_condition("international"),
                        "us-west": cls.create_base_network_condition("international"),
                    },
                    node_config=cls.create_node_config("large"),
                ),
            },
            workload_pattern="burst",
            data_size_range=(1024, 1024 * 1024 * 10),  # 1KB to 10MB
            replication_factor=3,
            consistency_level="quorum",
            edge_enabled=False,
            cache_size_mb=1024,
            failure_injection=True,
        )

        return config

    @classmethod
    def generate_edge_computing_scenario(cls) -> ScenarioConfig:
        """Generate a scenario focused on edge computing"""
        config = ScenarioConfig(
            name="edge_computing",
            description="Edge computing scenario with mobile nodes",
            duration=1800,  # 30 minutes
            regions={
                "cloud-central": RegionConfig(
                    name="cloud-central",
                    zones=["cloud-central-1a"],
                    network_conditions={
                        "edge-east": cls.create_base_network_condition("regional"),
                        "edge-west": cls.create_base_network_condition("regional"),
                    },
                    node_config=cls.create_node_config("large"),
                ),
                "edge-east": RegionConfig(
                    name="edge-east",
                    zones=["edge-east-1a", "edge-east-1b"],
                    network_conditions={
                        "cloud-central": cls.create_base_network_condition("regional"),
                        "edge-west": cls.create_base_network_condition("regional"),
                    },
                    node_config=cls.create_node_config("small"),
                ),
                "edge-west": RegionConfig(
                    name="edge-west",
                    zones=["edge-west-1a", "edge-west-1b"],
                    network_conditions={
                        "cloud-central": cls.create_base_network_condition("regional"),
                        "edge-east": cls.create_base_network_condition("regional"),
                    },
                    node_config=cls.create_node_config("small"),
                ),
            },
            workload_pattern="random",
            data_size_range=(1024, 1024 * 1024),  # 1KB to 1MB
            replication_factor=2,
            consistency_level="eventual",
            edge_enabled=True,
            cache_size_mb=512,
            failure_injection=True,
        )

        return config

    @classmethod
    def generate_hybrid_cloud_scenario(cls) -> ScenarioConfig:
        """Generate a scenario for hybrid cloud deployment"""
        config = ScenarioConfig(
            name="hybrid_cloud",
            description="Hybrid cloud scenario with on-prem and cloud nodes",
            duration=7200,  # 2 hours
            regions={
                "on-prem": RegionConfig(
                    name="on-prem",
                    zones=["on-prem-1a", "on-prem-1b"],
                    network_conditions={
                        "cloud-east": cls.create_base_network_condition("regional"),
                        "cloud-west": cls.create_base_network_condition("regional"),
                    },
                    node_config=cls.create_node_config("medium"),
                ),
                "cloud-east": RegionConfig(
                    name="cloud-east",
                    zones=["cloud-east-1a"],
                    network_conditions={
                        "on-prem": cls.create_base_network_condition("regional"),
                        "cloud-west": cls.create_base_network_condition("regional"),
                    },
                    node_config=cls.create_node_config("large"),
                ),
                "cloud-west": RegionConfig(
                    name="cloud-west",
                    zones=["cloud-west-1a"],
                    network_conditions={
                        "on-prem": cls.create_base_network_condition("regional"),
                        "cloud-east": cls.create_base_network_condition("regional"),
                    },
                    node_config=cls.create_node_config("large"),
                ),
            },
            workload_pattern="steady",
            data_size_range=(1024 * 1024, 1024 * 1024 * 100),  # 1MB to 100MB
            replication_factor=3,
            consistency_level="strong",
            edge_enabled=False,
            cache_size_mb=2048,
            failure_injection=True,
        )

        return config
