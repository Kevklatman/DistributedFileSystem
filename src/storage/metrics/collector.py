import time
import psutil
from typing import Dict, Any
import threading
from collections import defaultdict
import sys
import os
from dataclasses import dataclass, field
from datetime import datetime

# Add parent directory to Python path for imports
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)

from .unified_metrics import UnifiedMetricsCollector
import logging

logger = logging.getLogger(__name__)


@dataclass
class NetworkMetrics:
    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0
    start_time: float = field(default_factory=time.time)
    operation_type: str = ""
    file_size: int = 0

    @property
    def duration(self) -> float:
        return time.time() - self.start_time

    @property
    def upload_speed(self) -> float:
        """Calculate upload speed in MB/s"""
        if self.duration > 0:
            return (self.bytes_sent / 1024 / 1024) / self.duration
        return 0.0

    @property
    def download_speed(self) -> float:
        """Calculate download speed in MB/s"""
        if self.duration > 0:
            return (self.bytes_recv / 1024 / 1024) / self.duration
        return 0.0


class SystemMetricsCollector(UnifiedMetricsCollector):
    """System-wide metrics collector implementation."""

    def __init__(self, history_window: int = 300):
        """Initialize metrics collector.

        Args:
            history_window: Time window in seconds to keep metrics history
        """
        self._history_window = history_window
        self._metrics_history: Dict[float, Dict[str, float]] = {}
        self._operation_latencies = defaultdict(list)
        self._cache_stats = {"hits": 0, "misses": 0}
        self._lock = threading.Lock()
        self._network_metrics: Dict[str, NetworkMetrics] = {}
        self._last_network_counters = psutil.net_io_counters()
        self._current_operation: str = ""

        # Initialize baseline IO counters
        self._last_disk_io = psutil.disk_io_counters()
        self._last_net_io = psutil.net_io_counters()
        self._last_check_time = time.time()

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
        current_time = time.time()
        with self._lock:
            self._metrics_history[current_time] = {
                "cpu_usage": cpu,
                "memory_usage": memory,
                "disk_io": disk_io,
                "network_io": network_io,
            }

            # Clean up old metrics
            cutoff_time = current_time - self._history_window
            old_times = [t for t in self._metrics_history if t < cutoff_time]
            for t in old_times:
                del self._metrics_history[t]

    def record_cache_operation(self, operation: str, hit: bool) -> None:
        """Record cache operation (hit/miss)."""
        with self._lock:
            if hit:
                self._cache_stats["hits"] += 1
            else:
                self._cache_stats["misses"] += 1

    def start_network_operation(self, operation_name: str, file_size: int = 0) -> None:
        """Start tracking network metrics for an operation."""
        self._current_operation = operation_name
        self._network_metrics[operation_name] = NetworkMetrics(
            start_time=time.time(), operation_type=operation_name, file_size=file_size
        )
        # Get initial network counters
        self._last_network_counters = psutil.net_io_counters()

    def end_network_operation(self, operation_name: str) -> None:
        """End tracking network metrics for an operation."""
        if operation_name in self._network_metrics:
            # Get final network counters
            current_counters = psutil.net_io_counters()
            metrics = self._network_metrics[operation_name]

            # Calculate network usage for this operation
            metrics.bytes_sent = (
                current_counters.bytes_sent - self._last_network_counters.bytes_sent
            )
            metrics.bytes_recv = (
                current_counters.bytes_recv - self._last_network_counters.bytes_recv
            )
            metrics.packets_sent = (
                current_counters.packets_sent - self._last_network_counters.packets_sent
            )
            metrics.packets_recv = (
                current_counters.packets_recv - self._last_network_counters.packets_recv
            )

        self._current_operation = ""

    def get_network_metrics(self, operation_name: str) -> Dict[str, float]:
        """Get network metrics for a specific operation."""
        if operation_name in self._network_metrics:
            metrics = self._network_metrics[operation_name]
            return {
                "duration_seconds": metrics.duration,
                "bytes_sent_mb": metrics.bytes_sent / 1024 / 1024,
                "bytes_received_mb": metrics.bytes_recv / 1024 / 1024,
                "upload_speed_mbps": metrics.upload_speed,
                "download_speed_mbps": metrics.download_speed,
                "packets_sent": metrics.packets_sent,
                "packets_received": metrics.packets_recv,
            }
        return {}

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        current_time = time.time()

        # Get current resource usage
        cpu_usage = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()

        # Calculate IO rates
        current_disk_io = psutil.disk_io_counters()
        current_net_io = psutil.net_io_counters()
        time_diff = current_time - self._last_check_time

        if time_diff > 0:
            disk_io_rate = (
                (current_disk_io.read_bytes + current_disk_io.write_bytes)
                - (self._last_disk_io.read_bytes + self._last_disk_io.write_bytes)
            ) / time_diff

            network_io_rate = (
                (current_net_io.bytes_sent + current_net_io.bytes_recv)
                - (self._last_net_io.bytes_sent + self._last_net_io.bytes_recv)
            ) / time_diff
        else:
            disk_io_rate = 0
            network_io_rate = 0

        self._last_disk_io = current_disk_io
        self._last_net_io = current_net_io
        self._last_check_time = current_time

        # Calculate operation latencies
        operation_stats = {}
        with self._lock:
            for op, latencies in self._operation_latencies.items():
                if latencies:
                    operation_stats[op] = {
                        "avg_latency": sum(latencies) / len(latencies),
                        "min_latency": min(latencies),
                        "max_latency": max(latencies),
                        "samples": len(latencies),
                    }

            # Calculate cache hit rate
            total_cache_ops = self._cache_stats["hits"] + self._cache_stats["misses"]
            cache_hit_rate = (
                self._cache_stats["hits"] / total_cache_ops
                if total_cache_ops > 0
                else 0
            )

        return {
            "system": {
                "cpu_usage": cpu_usage,
                "memory_usage": memory.percent,
                "disk_io_rate": disk_io_rate,
                "network_io_rate": network_io_rate,
            },
            "operations": operation_stats,
            "cache": {
                "hit_rate": cache_hit_rate,
                "hits": self._cache_stats["hits"],
                "misses": self._cache_stats["misses"],
            },
            "network": {
                op: self.get_network_metrics(op) for op in self._network_metrics
            },
        }

    def reset_stats(self) -> None:
        """Reset all collected statistics."""
        with self._lock:
            self._metrics_history.clear()
            self._operation_latencies.clear()
            self._cache_stats = {"hits": 0, "misses": 0}
            self._last_check_time = time.time()
            self._last_disk_io = psutil.disk_io_counters()
            self._last_net_io = psutil.net_io_counters()
            self._network_metrics.clear()
