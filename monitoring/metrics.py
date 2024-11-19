from prometheus_client import Counter, Histogram, Gauge, Summary
from functools import wraps
import time

# File Operation Metrics
FILE_OP_DURATION = Histogram(
    'dfs_file_operation_seconds',
    'Time spent processing file operations',
    ['operation', 'node'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0)
)

FILE_SIZE = Histogram(
    'dfs_file_size_bytes',
    'Distribution of file sizes',
    ['node'],
    buckets=(1024, 10*1024, 100*1024, 1024*1024, 10*1024*1024, 100*1024*1024)
)

CONCURRENT_OPS = Gauge(
    'dfs_concurrent_operations',
    'Number of concurrent operations',
    ['operation', 'node']
)

CACHE_STATS = Counter(
    'dfs_cache_operations_total',
    'Cache operation statistics',
    ['operation', 'result', 'node']  # operation: read/write, result: hit/miss
)

# Replication Metrics
REPLICATION_LAG = Gauge(
    'dfs_replication_lag_seconds',
    'Replication lag between primary and secondary nodes',
    ['source_node', 'target_node']
)

CONSISTENCY_TIME = Histogram(
    'dfs_consistency_time_seconds',
    'Time to achieve consistency across nodes',
    ['operation'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

REPLICATION_QUEUE = Gauge(
    'dfs_replication_queue_length',
    'Number of operations waiting for replication',
    ['node']
)

# Error & Recovery Metrics
ERROR_COUNTER = Counter(
    'dfs_errors_total',
    'Number of errors by type',
    ['error_type', 'node']
)

RECOVERY_TIME = Histogram(
    'dfs_recovery_time_seconds',
    'Time taken to recover from failures',
    ['failure_type', 'node'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0)
)

RETRY_COUNTER = Counter(
    'dfs_operation_retries_total',
    'Number of operation retries',
    ['operation', 'node']
)

# Node Communication Metrics
RPC_LATENCY = Histogram(
    'dfs_rpc_latency_seconds',
    'Latency of RPC calls between nodes',
    ['source_node', 'target_node', 'operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5)
)

CONNECTION_POOL = Gauge(
    'dfs_connection_pool_size',
    'Size of the connection pool',
    ['node', 'pool_type']
)

NETWORK_ERRORS = Counter(
    'dfs_network_errors_total',
    'Number of network-related errors',
    ['error_type', 'node']
)

# Decorator for measuring operation duration
def measure_time(operation):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            node = kwargs.get('node', 'unknown')
            start_time = time.time()
            CONCURRENT_OPS.labels(operation=operation, node=node).inc()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                FILE_OP_DURATION.labels(operation=operation, node=node).observe(duration)
                return result
            except Exception as e:
                ERROR_COUNTER.labels(error_type=type(e).__name__, node=node).inc()
                raise
            finally:
                CONCURRENT_OPS.labels(operation=operation, node=node).dec()
        return wrapper
    return decorator

# Helper functions for metric collection
def record_file_size(size_bytes, node):
    """Record the size of a file being processed"""
    FILE_SIZE.labels(node=node).observe(size_bytes)

def record_cache_operation(operation, hit, node):
    """Record cache hit/miss"""
    result = 'hit' if hit else 'miss'
    CACHE_STATS.labels(operation=operation, result=result, node=node).inc()

def record_replication_lag(source_node, target_node, lag_seconds):
    """Record the replication lag between nodes"""
    REPLICATION_LAG.labels(source_node=source_node, target_node=target_node).set(lag_seconds)

def record_consistency_time(operation, duration):
    """Record time taken to achieve consistency"""
    CONSISTENCY_TIME.labels(operation=operation).observe(duration)

def record_network_error(error_type, node):
    """Record network-related errors"""
    NETWORK_ERRORS.labels(error_type=error_type, node=node).inc()

def record_rpc_latency(source_node, target_node, operation, duration):
    """Record RPC call latency"""
    RPC_LATENCY.labels(source_node=source_node, target_node=target_node, operation=operation).observe(duration)
