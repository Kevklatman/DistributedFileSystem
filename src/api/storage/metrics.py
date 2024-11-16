from prometheus_client import Counter, Gauge, Histogram
import time

# Storage metrics
STORAGE_USAGE = Gauge(
    'dfs_storage_usage_bytes',
    'Current storage usage in bytes',
    ['node']
)

STORAGE_CAPACITY = Gauge(
    'dfs_storage_capacity_bytes',
    'Total storage capacity in bytes',
    ['node']
)

# Operation metrics
OPERATION_LATENCY = Histogram(
    'dfs_operation_latency_seconds',
    'Time spent processing operations',
    ['operation', 'node'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

OPERATION_COUNTER = Counter(
    'dfs_operations_total',
    'Total number of operations',
    ['operation', 'node', 'status']
)

# Replication metrics
REPLICATION_LAG = Gauge(
    'dfs_replication_lag_seconds',
    'Replication lag in seconds',
    ['source_node', 'target_node']
)

REPLICATION_QUEUE_SIZE = Gauge(
    'dfs_replication_queue_size',
    'Number of pending replication operations',
    ['node']
)

# Node health metrics
NODE_HEALTH = Gauge(
    'dfs_node_health',
    'Node health status (1 for healthy, 0 for unhealthy)',
    ['node']
)

CLUSTER_MEMBER_COUNT = Gauge(
    'dfs_cluster_members',
    'Number of nodes in the cluster',
    ['status']  # 'active' or 'total'
)

class MetricsCollector:
    def __init__(self, node_id):
        self.node_id = node_id

    def set_storage_usage(self, bytes_used):
        """Update storage usage metric"""
        STORAGE_USAGE.labels(node=self.node_id).set(bytes_used)

    def set_storage_capacity(self, bytes_total):
        """Update storage capacity metric"""
        STORAGE_CAPACITY.labels(node=self.node_id).set(bytes_total)

    def track_operation(self, operation_name):
        """Context manager to track operation latency and count"""
        return OperationTracker(operation_name, self.node_id)

    def update_replication_lag(self, target_node, lag_seconds):
        """Update replication lag metric"""
        REPLICATION_LAG.labels(
            source_node=self.node_id,
            target_node=target_node
        ).set(lag_seconds)

    def set_replication_queue_size(self, size):
        """Update replication queue size metric"""
        REPLICATION_QUEUE_SIZE.labels(node=self.node_id).set(size)

    def set_node_health(self, is_healthy):
        """Update node health metric"""
        NODE_HEALTH.labels(node=self.node_id).set(1 if is_healthy else 0)

    def update_cluster_members(self, active_count, total_count):
        """Update cluster member metrics"""
        CLUSTER_MEMBER_COUNT.labels(status='active').set(active_count)
        CLUSTER_MEMBER_COUNT.labels(status='total').set(total_count)


class OperationTracker:
    def __init__(self, operation_name, node_id):
        self.operation_name = operation_name
        self.node_id = node_id
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        OPERATION_LATENCY.labels(
            operation=self.operation_name,
            node=self.node_id
        ).observe(duration)

        status = 'error' if exc_type else 'success'
        OPERATION_COUNTER.labels(
            operation=self.operation_name,
            node=self.node_id,
            status=status
        ).inc()
