"""
Storage-specific metrics collection
"""
from prometheus_client import Counter, Gauge, Histogram, Summary
import time
import os
import psutil

# Storage Metrics
STORAGE_USAGE = Gauge(
    'dfs_storage_usage_bytes',
    'Current storage usage in bytes',
    ['instance', 'node_id', 'path']
)

STORAGE_CAPACITY = Gauge(
    'dfs_storage_capacity_bytes',
    'Total storage capacity in bytes',
    ['instance', 'node_id', 'path']
)

STORAGE_IOPS = Counter(
    'dfs_storage_iops_total',
    'Storage IOPS (Input/Output Operations Per Second)',
    ['instance', 'node_id', 'operation']  # operation: read, write
)

STORAGE_BANDWIDTH = Counter(
    'dfs_storage_bandwidth_bytes_total',
    'Storage bandwidth usage in bytes',
    ['instance', 'node_id', 'direction']  # direction: read, write
)

# File Operation Metrics
FILE_OPERATIONS = Counter(
    'dfs_file_operations_total',
    'Number of file operations',
    ['instance', 'node_id', 'operation']  # operation: create, read, write, delete
)

FILE_OPERATION_ERRORS = Counter(
    'dfs_file_operation_errors_total',
    'Number of file operation errors',
    ['instance', 'node_id', 'operation', 'error_type']
)

FILE_SIZES = Histogram(
    'dfs_file_size_bytes',
    'Distribution of file sizes',
    ['instance', 'node_id'],
    buckets=(
        1024,        # 1KB
        10*1024,     # 10KB
        100*1024,    # 100KB
        1024*1024,   # 1MB
        10*1024*1024,# 10MB
        100*1024*1024,# 100MB
        1024*1024*1024# 1GB
    )
)

FILE_OPERATION_DURATION = Histogram(
    'dfs_file_operation_duration_seconds',
    'Duration of file operations',
    ['instance', 'node_id', 'operation'],
    buckets=(
        0.001,  # 1ms
        0.005,  # 5ms
        0.01,   # 10ms
        0.025,  # 25ms
        0.05,   # 50ms
        0.1,    # 100ms
        0.25,   # 250ms
        0.5,    # 500ms
        1.0,    # 1s
        2.5,    # 2.5s
        5.0     # 5s
    )
)

class StorageMetricsCollector:
    """Collector for storage-related metrics"""
    
    def __init__(self, instance_id: str, node_id: str, storage_path: str):
        self.instance_id = instance_id
        self.node_id = node_id
        self.storage_path = storage_path
        self._update_storage_metrics()

    def _update_storage_metrics(self):
        """Update storage usage and capacity metrics"""
        try:
            usage = psutil.disk_usage(self.storage_path)
            STORAGE_USAGE.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                path=self.storage_path
            ).set(usage.used)
            
            STORAGE_CAPACITY.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                path=self.storage_path
            ).set(usage.total)
        except Exception as e:
            FILE_OPERATION_ERRORS.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                operation='storage_update',
                error_type=type(e).__name__
            ).inc()

    def record_operation(self, operation: str):
        """Create a context manager for tracking file operations"""
        return FileOperationTracker(
            instance_id=self.instance_id,
            node_id=self.node_id,
            operation=operation
        )

    def record_file_size(self, size_bytes: int):
        """Record a file size observation"""
        FILE_SIZES.labels(
            instance=self.instance_id,
            node_id=self.node_id
        ).observe(size_bytes)

    def record_bandwidth(self, direction: str, bytes_count: int):
        """Record bandwidth usage"""
        STORAGE_BANDWIDTH.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            direction=direction
        ).inc(bytes_count)

    def record_iops(self, operation: str):
        """Record an I/O operation"""
        STORAGE_IOPS.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            operation=operation
        ).inc()

    def record_error(self, operation: str, error: Exception):
        """Record an operation error"""
        FILE_OPERATION_ERRORS.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            operation=operation,
            error_type=type(error).__name__
        ).inc()

class FileOperationTracker:
    """Context manager for tracking file operations"""
    
    def __init__(self, instance_id: str, node_id: str, operation: str):
        self.instance_id = instance_id
        self.node_id = node_id
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        FILE_OPERATIONS.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            operation=self.operation
        ).inc()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        FILE_OPERATION_DURATION.labels(
            instance=self.instance_id,
            node_id=self.node_id,
            operation=self.operation
        ).observe(duration)

        if exc_type is not None:
            FILE_OPERATION_ERRORS.labels(
                instance=self.instance_id,
                node_id=self.node_id,
                operation=self.operation,
                error_type=exc_type.__name__
            ).inc()

def create_metrics_collector(instance_id: str, node_id: str, storage_path: str) -> StorageMetricsCollector:
    """Factory function to create a storage metrics collector"""
    return StorageMetricsCollector(instance_id, node_id, storage_path)
