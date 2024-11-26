import asyncio
import random
import math
from dataclasses import dataclass
from typing import Tuple


@dataclass
class NetworkConditions:
    """Network conditions for simulation"""

    latency_base: float  # Base latency in milliseconds
    latency_jitter: float  # Jitter in milliseconds
    packet_loss: float  # Probability of packet loss (0-1)
    bandwidth_mbps: float  # Bandwidth in Mbps


class NetworkSimulator:
    """Simulates network conditions between nodes"""

    def __init__(self, conditions: NetworkConditions):
        self.conditions = conditions

    async def simulate_transfer(
        self, source: str, dest: str, size: int
    ) -> Tuple[bool, float]:
        """
        Simulate a network transfer between two nodes

        Args:
            source: Source node ID
            dest: Destination node ID
            size: Size of data to transfer in bytes

        Returns:
            Tuple of (success: bool, duration: float)
        """
        # Simulate packet loss
        if random.random() < self.conditions.packet_loss:
            return False, 0.0

        # Calculate base transfer time based on bandwidth
        bandwidth_bytes_per_sec = self.conditions.bandwidth_mbps * 1024 * 1024 / 8
        transfer_time = size / bandwidth_bytes_per_sec

        # Add latency with jitter
        latency = self.conditions.latency_base + random.uniform(
            -self.conditions.latency_jitter, self.conditions.latency_jitter
        )
        total_time = (latency / 1000.0) + transfer_time  # Convert latency to seconds

        # Simulate the transfer time
        await asyncio.sleep(total_time)

        return True, total_time

    def get_expected_latency(self, source: str, dest: str) -> float:
        """Get expected latency between two nodes"""
        return self.conditions.latency_base / 1000.0  # Convert to seconds

    def get_expected_bandwidth(self) -> float:
        """Get expected bandwidth in bytes per second"""
        return self.conditions.bandwidth_mbps * 1024 * 1024 / 8
