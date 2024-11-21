from prometheus_client import Counter, Histogram, Gauge, Summary
from functools import wraps
import time

# Request Metrics
REQUEST_TOTAL = Counter(
    'dfs_request_total',
    'Total number of requests',
    ['endpoint', 'status', 'instance']
)

REQUEST_LATENCY = Histogram(
    'dfs_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint', 'instance'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0)
)

REQUEST_QUEUE_LENGTH = Gauge(
    'dfs_request_queue_length',
    'Number of requests in queue',
    ['instance']
)

# File Operation Metrics
FILE_OPERATIONS = Counter(
    'dfs_file_operations_total',
    'Number of file operations',
    ['operation', 'instance']
)

FILE_OP_DURATION = Histogram(
    'dfs_file_operation_seconds',
    'Time spent processing file operations',
    ['operation', 'instance'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0)
)

FILE_SIZE = Histogram(
    'dfs_file_size_bytes',
    'Distribution of file sizes',
    ['instance'],
    buckets=(1024, 10*1024, 100*1024, 1024*1024, 10*1024*1024, 100*1024*1024)
)

# Storage Metrics
STORAGE_USAGE = Gauge(
    'dfs_storage_usage_bytes',
    'Current storage usage in bytes',
    ['instance', 'node_id']
)

STORAGE_CAPACITY = Gauge(
    'dfs_storage_capacity_bytes',
    'Total storage capacity in bytes',
    ['instance', 'node_id']
)

# Network Metrics
NETWORK_IO = Counter(
    'dfs_network_bytes_total',
    'Network I/O in bytes',
    ['direction', 'instance']  # direction: received/transmitted
)

# Cache Metrics
CACHE_HITS = Counter(
    'dfs_cache_hits_total',
    'Number of cache hits',
    ['instance']
)

CACHE_MISSES = Counter(
    'dfs_cache_misses_total',
    'Number of cache misses',
    ['instance']
)

# Replication Metrics
REPLICATION_LAG = Gauge(
    'dfs_replication_lag_seconds',
    'Replication lag between nodes',
    ['instance', 'target_node']
)

REPLICATION_QUEUE = Gauge(
    'dfs_replication_queue_length',
    'Number of operations waiting for replication',
    ['instance']
)

# Node Health Metrics
NODE_HEALTH = Gauge(
    'dfs_node_health',
    'Node health status (1 for healthy, 0 for unhealthy)',
    ['instance']
)

# Resource Usage Metrics
CPU_USAGE = Gauge(
    'dfs_cpu_usage_percent',
    'CPU usage percentage',
    ['instance']
)

MEMORY_USAGE = Gauge(
    'dfs_memory_usage_bytes',
    'Memory usage in bytes',
    ['instance']
)

class MetricsCollector:
    def __init__(self, instance_id):
        self.instance_id = instance_id

    def record_request(self, endpoint, status, latency):
        """Record a request with its latency and status"""
        REQUEST_TOTAL.labels(
            endpoint=endpoint,
            status=status,
            instance=self.instance_id
        ).inc()

        REQUEST_LATENCY.labels(
            endpoint=endpoint,
            instance=self.instance_id
        ).observe(latency)

    def update_queue_length(self, length):
        """Update request queue length"""
        REQUEST_QUEUE_LENGTH.labels(instance=self.instance_id).set(length)

    def record_file_operation(self, operation, duration):
        """Record a file operation and its duration"""
        FILE_OPERATIONS.labels(
            operation=operation,
            instance=self.instance_id
        ).inc()

        FILE_OP_DURATION.labels(
            operation=operation,
            instance=self.instance_id
        ).observe(duration)

    def record_file_size(self, size_bytes):
        """Record file size"""
        FILE_SIZE.labels(instance=self.instance_id).observe(size_bytes)

    def update_storage_metrics(self, usage_bytes, capacity_bytes, node_id):
        """Update storage usage and capacity"""
        STORAGE_USAGE.labels(
            instance=self.instance_id,
            node_id=node_id
        ).set(usage_bytes)

        STORAGE_CAPACITY.labels(
            instance=self.instance_id,
            node_id=node_id
        ).set(capacity_bytes)

    def record_network_io(self, direction, bytes_count):
        """Record network I/O"""
        NETWORK_IO.labels(
            direction=direction,
            instance=self.instance_id
        ).inc(bytes_count)

    def record_cache_access(self, hit):
        """Record cache hit/miss"""
        if hit:
            CACHE_HITS.labels(instance=self.instance_id).inc()
        else:
            CACHE_MISSES.labels(instance=self.instance_id).inc()

    def update_replication_metrics(self, target_node, lag_seconds, queue_length):
        """Update replication metrics"""
        REPLICATION_LAG.labels(
            instance=self.instance_id,
            target_node=target_node
        ).set(lag_seconds)

        REPLICATION_QUEUE.labels(instance=self.instance_id).set(queue_length)

    def update_node_health(self, is_healthy):
        """Update node health status"""
        NODE_HEALTH.labels(instance=self.instance_id).set(1 if is_healthy else 0)

    def update_resource_usage(self, cpu_percent, memory_bytes):
        """Update resource usage metrics"""
        CPU_USAGE.labels(instance=self.instance_id).set(cpu_percent)
        MEMORY_USAGE.labels(instance=self.instance_id).set(memory_bytes)

def measure_operation(operation_type):
    """Decorator to measure operation duration"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)
                status = 'success'
            except Exception as e:
                status = 'error'
                raise
            finally:
                duration = time.time() - start_time
                if hasattr(self, 'metrics'):
                    self.metrics.record_request(operation_type, status, duration)
            return result
        return wrapper
    return decorator
#k
