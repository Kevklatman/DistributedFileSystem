import psutil
import time
from dataclasses import dataclass
from typing import Dict, Optional
import logging

@dataclass
class LoadMetrics:
    cpu_usage: float
    memory_usage: float
    disk_io: float
    network_io: float
    request_rate: float
    timestamp: float

class LoadManager:
    def __init__(self, 
                 max_cpu_threshold: float = 80.0,
                 max_memory_threshold: float = 80.0,
                 max_requests_per_second: float = 1000.0):
        self.max_cpu_threshold = max_cpu_threshold
        self.max_memory_threshold = max_memory_threshold
        self.max_requests_per_second = max_requests_per_second
        
        self.request_timestamps = []
        self.metrics_history: Dict[float, LoadMetrics] = {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize counters
        self._last_disk_io = psutil.disk_io_counters()
        self._last_net_io = psutil.net_io_counters()
        self._last_check_time = time.time()

    def can_handle_request(self) -> bool:
        """Check if node can handle more requests"""
        metrics = self.get_current_metrics()
        
        # Clean old request timestamps
        current_time = time.time()
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if current_time - ts <= 1.0
        ]
        
        current_rps = len(self.request_timestamps)
        
        return (
            metrics.cpu_usage < self.max_cpu_threshold and
            metrics.memory_usage < self.max_memory_threshold and
            current_rps < self.max_requests_per_second
        )

    def record_request(self) -> None:
        """Record a new request"""
        self.request_timestamps.append(time.time())

    def get_current_load(self) -> float:
        """Get normalized load value between 0 and 1"""
        metrics = self.get_current_metrics()
        
        # Weight different metrics
        weights = {
            'cpu': 0.4,
            'memory': 0.3,
            'disk_io': 0.15,
            'network_io': 0.15
        }
        
        normalized_load = (
            (metrics.cpu_usage / 100.0) * weights['cpu'] +
            (metrics.memory_usage / 100.0) * weights['memory'] +
            (min(metrics.disk_io / 100.0, 1.0)) * weights['disk_io'] +
            (min(metrics.network_io / 100.0, 1.0)) * weights['network_io']
        )
        
        return normalized_load

    def get_capacity(self) -> float:
        """Get remaining capacity as a value between 0 and 1"""
        return 1.0 - self.get_current_load()

    def get_current_metrics(self) -> LoadMetrics:
        """Get current system metrics"""
        current_time = time.time()
        
        # Get CPU and memory usage
        cpu_usage = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        # Calculate disk I/O rate
        current_disk_io = psutil.disk_io_counters()
        disk_io_bytes = (
            (current_disk_io.read_bytes + current_disk_io.write_bytes) -
            (self._last_disk_io.read_bytes + self._last_disk_io.write_bytes)
        )
        self._last_disk_io = current_disk_io
        
        # Calculate network I/O rate
        current_net_io = psutil.net_io_counters()
        network_io_bytes = (
            (current_net_io.bytes_sent + current_net_io.bytes_recv) -
            (self._last_net_io.bytes_sent + self._last_net_io.bytes_recv)
        )
        self._last_net_io = current_net_io
        
        # Calculate time difference
        time_diff = current_time - self._last_check_time
        self._last_check_time = current_time
        
        # Calculate rates
        if time_diff > 0:
            disk_io_rate = disk_io_bytes / time_diff
            network_io_rate = network_io_bytes / time_diff
        else:
            disk_io_rate = 0
            network_io_rate = 0
        
        # Calculate request rate
        current_requests = len([
            ts for ts in self.request_timestamps 
            if current_time - ts <= 1.0
        ])
        
        metrics = LoadMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_io=disk_io_rate,
            network_io=network_io_rate,
            request_rate=float(current_requests),
            timestamp=current_time
        )
        
        # Store metrics history (keep last 5 minutes)
        self.metrics_history[current_time] = metrics
        old_timestamps = [
            ts for ts in self.metrics_history.keys() 
            if current_time - ts > 300
        ]
        for ts in old_timestamps:
            del self.metrics_history[ts]
        
        return metrics

    def predict_load_trend(self, window_seconds: float = 60.0) -> Optional[float]:
        """Predict load trend based on recent history"""
        current_time = time.time()
        recent_metrics = [
            metrics for ts, metrics in self.metrics_history.items()
            if current_time - ts <= window_seconds
        ]
        
        if len(recent_metrics) < 2:
            return None
        
        # Calculate load change rate
        loads = [self._calculate_load_from_metrics(m) for m in recent_metrics]
        time_points = [m.timestamp - recent_metrics[0].timestamp for m in recent_metrics]
        
        # Simple linear regression
        n = len(loads)
        sum_x = sum(time_points)
        sum_y = sum(loads)
        sum_xy = sum(x * y for x, y in zip(time_points, loads))
        sum_xx = sum(x * x for x in time_points)
        
        try:
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
            return slope
        except ZeroDivisionError:
            return None

    def _calculate_load_from_metrics(self, metrics: LoadMetrics) -> float:
        """Calculate normalized load value from metrics"""
        weights = {
            'cpu': 0.4,
            'memory': 0.3,
            'disk_io': 0.15,
            'network_io': 0.15
        }
        
        return (
            (metrics.cpu_usage / 100.0) * weights['cpu'] +
            (metrics.memory_usage / 100.0) * weights['memory'] +
            (min(metrics.disk_io / 100.0, 1.0)) * weights['disk_io'] +
            (min(metrics.network_io / 100.0, 1.0)) * weights['network_io']
        )

    def get_node_load(self, node_id: str) -> float:
        """Get the current load of a node."""
        return self.get_current_load()

    def get_node_capacity(self, node_id: str) -> float:
        """Get the current capacity of a node."""
        return self.get_capacity()
