"""
Unified metrics system for the distributed file system.
Consolidates all metrics collection, monitoring, and reporting.
"""
from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest, CONTENT_TYPE_LATEST
from dataclasses import dataclass
from datetime import datetime
import threading
import psutil
import time
import logging

logger = logging.getLogger(__name__)

class UnifiedMetricsCollector:
    """Unified metrics collector for the distributed file system"""

    def __init__(self, instance_id: str, node_id: str = None):
        self.instance_id = instance_id
        self.node_id = node_id or instance_id
        self._init_metrics()
        self._lock = threading.Lock()

    def _init_metrics(self):
        """Initialize all Prometheus metrics"""
        # System Metrics
        self.system_cpu = Gauge(
            'dfs_system_cpu_percent',
            'CPU usage percentage',
            ['instance', 'node_id']
        )
        self.system_memory = Gauge(
            'dfs_system_memory_percent',
            'Memory usage percentage',
            ['instance', 'node_id', 'type']  # type: used, available, cached
        )
        self.system_uptime = Gauge(
            'dfs_system_uptime_seconds',
            'System uptime in seconds',
            ['instance', 'node_id']
        )
        self.system_load = Gauge(
            'dfs_system_load_average',
            'System load average',
            ['instance', 'node_id', 'interval']  # interval: 1m, 5m, 15m
        )

        # Storage Metrics
        self.storage_capacity = Gauge(
            'dfs_storage_capacity_bytes',
            'Total storage capacity in bytes',
            ['instance', 'node_id', 'mount_point']
        )
        self.storage_used = Gauge(
            'dfs_storage_used_bytes',
            'Used storage in bytes',
            ['instance', 'node_id', 'mount_point']
        )
        self.storage_iops = Counter(
            'dfs_storage_iops_total',
            'Storage IOPS',
            ['instance', 'node_id', 'operation']  # operation: read, write
        )
        self.storage_throughput = Counter(
            'dfs_storage_throughput_bytes_total',
            'Storage throughput in bytes',
            ['instance', 'node_id', 'operation']  # operation: read, write
        )

        # Network Metrics
        self.network_received = Counter(
            'dfs_network_received_bytes_total',
            'Total bytes received',
            ['instance', 'node_id', 'interface']
        )
        self.network_transmitted = Counter(
            'dfs_network_transmitted_bytes_total',
            'Total bytes transmitted',
            ['instance', 'node_id', 'interface']
        )
        self.network_errors = Counter(
            'dfs_network_errors_total',
            'Total network errors',
            ['instance', 'node_id', 'interface', 'direction']  # direction: in, out
        )

        # Request Metrics
        self.requests_total = Counter(
            'dfs_requests_total',
            'Total number of requests',
            ['instance', 'node_id', 'endpoint', 'method']
        )
        self.requests_failed = Counter(
            'dfs_requests_failed_total',
            'Total number of failed requests',
            ['instance', 'node_id', 'endpoint', 'method', 'error_type']
        )
        self.request_duration = Histogram(
            'dfs_request_duration_seconds',
            'Request duration in seconds',
            ['instance', 'node_id', 'endpoint', 'method'],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0)
        )
        self.request_queue_length = Gauge(
            'dfs_request_queue_length',
            'Number of requests in queue',
            ['instance', 'node_id']
        )

        # Cache Metrics
        self.cache_hits = Counter(
            'dfs_cache_hits_total',
            'Number of cache hits',
            ['instance', 'node_id', 'cache_type']  # cache_type: memory, disk
        )
        self.cache_misses = Counter(
            'dfs_cache_misses_total',
            'Number of cache misses',
            ['instance', 'node_id', 'cache_type']
        )
        self.cache_size = Gauge(
            'dfs_cache_size_bytes',
            'Current cache size in bytes',
            ['instance', 'node_id', 'cache_type']
        )

        # File Operation Metrics
        self.file_ops = Counter(
            'dfs_file_operations_total',
            'Number of file operations',
            ['instance', 'node_id', 'operation']  # operation: create, read, write, delete
        )
        self.file_op_errors = Counter(
            'dfs_file_operation_errors_total',
            'Number of file operation errors',
            ['instance', 'node_id', 'operation', 'error_type']
        )
        self.file_op_duration = Histogram(
            'dfs_file_operation_duration_seconds',
            'File operation duration in seconds',
            ['instance', 'node_id', 'operation'],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0)
        )

        # Replication Metrics
        self.replication_lag = Gauge(
            'dfs_replication_lag_seconds',
            'Replication lag in seconds',
            ['instance', 'node_id', 'target_node']
        )
        self.replication_queue = Gauge(
            'dfs_replication_queue_length',
            'Number of pending replication operations',
            ['instance', 'node_id']
        )
        self.replication_errors = Counter(
            'dfs_replication_errors_total',
            'Number of replication errors',
            ['instance', 'node_id', 'error_type']
        )

        # Policy Metrics
        self.policy_violations = Counter(
            'dfs_policy_violations_total',
            'Number of policy violations',
            ['instance', 'node_id', 'policy_type', 'severity']
        )

    def update_system_metrics(self):
        """Update all system metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_cpu.labels(instance=self.instance_id, node_id=self.node_id).set(cpu_percent)

            # Memory metrics
            memory = psutil.virtual_memory()
            self.system_memory.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                type='used'
            ).set(memory.percent)
            self.system_memory.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                type='available'
            ).set(100 - memory.percent)

            # Load average
            load1, load5, load15 = psutil.getloadavg()
            self.system_load.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                interval='1m'
            ).set(load1)
            self.system_load.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                interval='5m'
            ).set(load5)
            self.system_load.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                interval='15m'
            ).set(load15)

            # Uptime
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            self.system_uptime.labels(
                instance=self.instance_id,
                node_id=self.node_id
            ).set(uptime)

        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")

    def update_storage_metrics(self, mount_point='/'):
        """Update storage metrics for a given mount point"""
        try:
            disk = psutil.disk_usage(mount_point)
            self.storage_capacity.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                mount_point=mount_point
            ).set(disk.total)
            self.storage_used.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                mount_point=mount_point
            ).set(disk.used)

            # IOPS and throughput
            disk_io = psutil.disk_io_counters()
            if disk_io:
                self.storage_iops.labels(
                    instance=self.instance_id,
                    node_id=self.node_id,
                    operation='read'
                ).inc(disk_io.read_count)
                self.storage_iops.labels(
                    instance=self.instance_id,
                    node_id=self.node_id,
                    operation='write'
                ).inc(disk_io.write_count)
                self.storage_throughput.labels(
                    instance=self.instance_id,
                    node_id=self.node_id,
                    operation='read'
                ).inc(disk_io.read_bytes)
                self.storage_throughput.labels(
                    instance=self.instance_id,
                    node_id=self.node_id,
                    operation='write'
                ).inc(disk_io.write_bytes)

        except Exception as e:
            logger.error(f"Error updating storage metrics: {e}")

    def update_network_metrics(self):
        """Update network metrics"""
        try:
            net_io = psutil.net_io_counters(pernic=True)
            for interface, counters in net_io.items():
                self.network_received.labels(
                    instance=self.instance_id,
                    node_id=self.node_id,
                    interface=interface
                ).inc(counters.bytes_recv)
                self.network_transmitted.labels(
                    instance=self.instance_id,
                    node_id=self.node_id,
                    interface=interface
                ).inc(counters.bytes_sent)
                self.network_errors.labels(
                    instance=self.instance_id,
                    node_id=self.node_id,
                    interface=interface,
                    direction='in'
                ).inc(counters.errin)
                self.network_errors.labels(
                    instance=self.instance_id,
                    node_id=self.node_id,
                    interface=interface,
                    direction='out'
                ).inc(counters.errout)

        except Exception as e:
            logger.error(f"Error updating network metrics: {e}")

    def record_request(self, endpoint: str, method: str, duration: float, error: str = None):
        """Record a request with its duration and status"""
        self.requests_total.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            endpoint=endpoint,
            method=method
        ).inc()

        if error:
            self.requests_failed.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                endpoint=endpoint,
                method=method,
                error_type=error
            ).inc()

        self.request_duration.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            endpoint=endpoint,
            method=method
        ).observe(duration)

    def update_queue_length(self, length: int):
        """Update request queue length"""
        self.request_queue_length.labels(
            instance=self.instance_id,
            node_id=self.node_id
        ).set(length)

    def record_cache_operation(self, hit: bool, cache_type: str = 'memory'):
        """Record cache hit/miss"""
        if hit:
            self.cache_hits.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                cache_type=cache_type
            ).inc()
        else:
            self.cache_misses.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                cache_type=cache_type
            ).inc()

    def update_cache_size(self, size: int, cache_type: str = 'memory'):
        """Update cache size"""
        self.cache_size.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            cache_type=cache_type
        ).set(size)

    def record_file_operation(self, operation: str, duration: float, error: str = None):
        """Record a file operation with its duration and status"""
        self.file_ops.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            operation=operation
        ).inc()

        if error:
            self.file_op_errors.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                operation=operation,
                error_type=error
            ).inc()

        self.file_op_duration.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            operation=operation
        ).observe(duration)

    def update_replication_metrics(self, target_node: str, lag: float, queue_length: int):
        """Update replication metrics"""
        self.replication_lag.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            target_node=target_node
        ).set(lag)

        self.replication_queue.labels(
            instance=self.instance_id,
            node_id=self.node_id
        ).set(queue_length)

    def record_replication_error(self, error_type: str):
        """Record a replication error"""
        self.replication_errors.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            error_type=error_type
        ).inc()

    def record_policy_violation(self, policy_type: str, severity: str = 'warning'):
        """Record a policy violation"""
        self.policy_violations.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            policy_type=policy_type,
            severity=severity
        ).inc()

    def get_metrics(self) -> bytes:
        """Get all metrics in Prometheus format"""
        return generate_latest()

class MetricsContextManager:
    """Context manager for tracking operation metrics"""

    def __init__(self, metrics: UnifiedMetricsCollector, operation_type: str):
        self.metrics = metrics
        self.operation_type = operation_type
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type:
            error_type = exc_type.__name__
            self.metrics.record_file_operation(
                self.operation_type,
                duration,
                error=error_type
            )
        else:
            self.metrics.record_file_operation(
                self.operation_type,
                duration
            )
