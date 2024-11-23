import os
import asyncio
import logging
import time
import psutil
import random
from aiohttp import web
import json
from collections import deque
from prometheus_client import (
    generate_latest,
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry
)
from ..data import CacheStore

# Create a custom registry for DFS metrics
DFS_REGISTRY = CollectorRegistry()

# Request metrics
REQUEST_COUNT = Counter(
    'dfs_request_total',
    'Total requests processed',
    ['method', 'endpoint', 'status'],
    registry=DFS_REGISTRY
)

REQUEST_LATENCY = Histogram(
    'dfs_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint'],
    registry=DFS_REGISTRY
)

REQUEST_QUEUE_LENGTH = Gauge(
    'dfs_request_queue_length',
    'Number of requests in queue',
    ['node_id'],
    registry=DFS_REGISTRY
)

# File operation metrics
FILE_OPERATIONS = Counter(
    'dfs_file_operations_total',
    'Number of file operations',
    ['node_id', 'operation'],
    registry=DFS_REGISTRY
)

FILE_OPERATION_ERRORS = Counter(
    'dfs_file_operation_errors_total',
    'Number of file operation errors',
    ['node_id', 'operation'],
    registry=DFS_REGISTRY
)

FILE_OPERATION_LATENCY = Histogram(
    'dfs_file_operation_latency_seconds',
    'File operation latency in seconds',
    ['node_id', 'operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=DFS_REGISTRY
)

# File size histogram and network I/O metrics
FILE_SIZE_HISTOGRAM = Histogram(
    'dfs_file_size_bytes',
    'Distribution of file sizes in bytes',
    ['node_id'],
    buckets=(0, 1024, 10*1024, 100*1024, 1024*1024, 10*1024*1024, 100*1024*1024),
    registry=DFS_REGISTRY
)

NETWORK_RECEIVED = Counter(
    'dfs_network_received_bytes_total',
    'Total bytes received over network',
    ['node_id'],
    registry=DFS_REGISTRY
)

NETWORK_TRANSMITTED = Counter(
    'dfs_network_transmitted_bytes_total',
    'Total bytes transmitted over network',
    ['node_id'],
    registry=DFS_REGISTRY
)

# Network metrics
NETWORK_IO = Counter(
    'dfs_network_bytes_total',
    'Network I/O in bytes',
    ['node_id', 'direction'],  # direction: in, out
    registry=DFS_REGISTRY
)

NETWORK_OPERATIONS = Counter(
    'dfs_network_operations_total',
    'Number of network operations',
    ['node_id', 'operation'],  # operation: send, receive
    registry=DFS_REGISTRY
)

# Storage metrics
STORAGE_USAGE = Gauge(
    'dfs_storage_usage_bytes',
    'Storage space used in bytes',
    ['node_id', 'path'],
    registry=DFS_REGISTRY
)

STORAGE_CAPACITY = Gauge(
    'dfs_storage_capacity_bytes',
    'Total storage capacity in bytes',
    ['node_id', 'path'],
    registry=DFS_REGISTRY
)

# Replication metrics
REPLICATION_LAG = Gauge(
    'dfs_replication_lag_seconds',
    'Replication delay between nodes',
    ['source_node', 'target_node'],
    registry=DFS_REGISTRY
)

# Cache metrics
CACHE_HITS = Counter(
    'dfs_cache_hits_total',
    'Total number of cache hits',
    ['node_id'],
    registry=DFS_REGISTRY
)

CACHE_MISSES = Counter(
    'dfs_cache_misses_total',
    'Total number of cache misses',
    ['node_id'],
    registry=DFS_REGISTRY
)

CACHE_HIT_RATE = Gauge(
    'dfs_cache_hit_rate',
    'Cache hit rate as percentage',
    ['node_id'],
    registry=DFS_REGISTRY
)

# Process metrics
PROCESS_CPU_SECONDS = Counter(
    'process_cpu_seconds_total',
    'Total user and system CPU time spent in seconds',
    ['node_id'],
    registry=DFS_REGISTRY
)

PROCESS_MEMORY_BYTES = Gauge(
    'process_resident_memory_bytes',
    'Resident memory size in bytes',
    ['node_id'],
    registry=DFS_REGISTRY
)

# Node health metrics
NODE_HEALTH = Gauge(
    'dfs_node_health',
    'Node health status (1 for healthy, 0 for unhealthy)',
    ['node_id'],
    registry=DFS_REGISTRY
)

# System metrics
SYSTEM_METRICS = Gauge(
    'dfs_system_metrics',
    'System metrics (CPU, Memory, etc)',
    ['node_id', 'metric'],
    registry=DFS_REGISTRY
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StorageNode:
    def __init__(self):
        # Get node ID with a default value
        self.node_id = os.environ.get('NODE_ID', 'node1')

        # Use Docker volume path if running in container, otherwise use home directory
        self.data_dir = '/app/data' if os.path.exists('/app') else os.path.expanduser('~/dfs_data')

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info(f"Using storage directory: {self.data_dir}")

        # Request queue
        self.request_queue = deque()
        self.max_queue_size = 1000  # Maximum number of requests to queue

        # Network stats
        self._last_net_io = psutil.net_io_counters()
        self._last_net_io_time = time.time()

        # Initialize cache with proper store
        self.cache = CacheStore(max_size=1000, ttl_seconds=3600)
        self._cache_hits = 0  # Keep counters for metrics
        self._cache_misses = 0

        # Initialize process stats
        self._process = psutil.Process()

        # Mock replication nodes for testing
        self._replication_nodes = ['node2', 'node3']  # In production, this would be dynamic

        # Initialize metrics
        self._init_metrics()

    def _init_metrics(self):
        """Initialize metrics with default values"""
        try:
            # Initialize storage metrics
            usage = psutil.disk_usage(self.data_dir)
            STORAGE_USAGE.labels(node_id=self.node_id, path=self.data_dir).set(usage.used)
            STORAGE_CAPACITY.labels(node_id=self.node_id, path=self.data_dir).set(usage.total)

            # Initialize system metrics
            SYSTEM_METRICS.labels(node_id=self.node_id, metric='cpu_percent').set(psutil.cpu_percent())
            memory = psutil.virtual_memory()
            SYSTEM_METRICS.labels(node_id=self.node_id, metric='memory_used_percent').set(memory.percent)
            SYSTEM_METRICS.labels(node_id=self.node_id, metric='memory_available_bytes').set(memory.available)

            # Initialize request queue metric
            REQUEST_QUEUE_LENGTH.labels(node_id=self.node_id).set(0)

            # Initialize network metrics
            net_io = psutil.net_io_counters()
            NETWORK_IO.labels(node_id=self.node_id, direction='in').inc(0)
            NETWORK_IO.labels(node_id=self.node_id, direction='out').inc(0)

            # Initialize cache metrics
            CACHE_HITS.labels(node_id=self.node_id).inc(0)
            CACHE_MISSES.labels(node_id=self.node_id).inc(0)
            CACHE_HIT_RATE.labels(node_id=self.node_id).set(0)

            # Initialize replication lag metrics
            for target_node in self._replication_nodes:
                REPLICATION_LAG.labels(
                    source_node=self.node_id,
                    target_node=target_node
                ).set(0)

            # Initialize process metrics
            PROCESS_CPU_SECONDS.labels(node_id=self.node_id).inc(0)
            PROCESS_MEMORY_BYTES.labels(node_id=self.node_id).set(0)

            # Set node as healthy
            NODE_HEALTH.labels(node_id=self.node_id).set(1)

            logger.info("Metrics initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing metrics: {e}")
            NODE_HEALTH.labels(node_id=self.node_id).set(0)

    async def start(self):
        """Start the storage node"""
        app = web.Application(middlewares=[self.metrics_middleware])
        app.add_routes([
            web.get('/metrics', self.metrics),
            web.get('/health', self.health_check),
            web.post('/file', self.handle_file_operation),
            web.get('/file/{file_id}', self.handle_file_operation),
            web.delete('/file/{file_id}', self.handle_file_operation)
        ])

        # Use port 8000 for Docker, 8001 for local development
        port = int(os.environ.get('PORT', '8001'))
        host = os.environ.get('HOST', '0.0.0.0')

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        # Start background tasks
        asyncio.create_task(self._update_metrics_periodically())

        logger.info(f"Storage node {self.node_id} started and listening on {host}:{port}")

    @web.middleware
    async def metrics_middleware(self, request, handler):
        """Middleware to track request metrics"""
        # Add request to queue
        if len(self.request_queue) < self.max_queue_size:
            self.request_queue.append(time.time())
        REQUEST_QUEUE_LENGTH.labels(node_id=self.node_id).set(len(self.request_queue))

        # Track request timing
        start_time = time.time()
        try:
            response = await handler(request)
            status = 'success'
        except Exception as e:
            status = 'error'
            raise
        finally:
            # Update request metrics
            duration = time.time() - start_time
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.path,
                status=status
            ).inc()
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.path
            ).observe(duration)

            # Remove request from queue
            if self.request_queue:
                self.request_queue.popleft()
            REQUEST_QUEUE_LENGTH.labels(node_id=self.node_id).set(len(self.request_queue))

        return response

    async def handle_file_operation(self, request):
        """Handle file operations with metrics tracking"""
        operation = request.method.lower()
        start_time = time.time()

        try:
            # Handle different operations
            if operation == 'get':
                file_id = request.match_info.get('file_id')
                # Try to get from cache first
                data = self.cache.get(file_id)
                if data is not None:
                    self._cache_hits += 1
                    CACHE_HITS.labels(node_id=self.node_id).inc()
                    file_size = len(data)
                    NETWORK_TRANSMITTED.labels(node_id=self.node_id).inc(file_size)
                else:
                    self._cache_misses += 1
                    CACHE_MISSES.labels(node_id=self.node_id).inc()
                    # Simulate fetching from disk
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                    data = "Simulated file content"
                    # Cache the fetched data
                    self.cache.put(file_id, data)
                    file_size = len(data)
                    NETWORK_TRANSMITTED.labels(node_id=self.node_id).inc(file_size)

            elif operation == 'post':
                # Simulate receiving file data
                file_size = 1024 * (2 ** random.randint(0, 16))
                file_id = f"file_{random.randint(1000, 9999)}"
                data = "Simulated file content"

                # Store in cache
                self.cache.put(file_id, data)
                FILE_SIZE_HISTOGRAM.labels(node_id=self.node_id).observe(file_size)
                NETWORK_RECEIVED.labels(node_id=self.node_id).inc(file_size)

            elif operation == 'delete':
                file_id = request.match_info.get('file_id')
                # Remove from cache if exists
                self.cache.delete(file_id)

            # Record operation
            FILE_OPERATIONS.labels(
                node_id=self.node_id,
                operation=operation
            ).inc()

            # Record latency
            duration = time.time() - start_time
            FILE_OPERATION_LATENCY.labels(
                node_id=self.node_id,
                operation=operation
            ).observe(duration)

            return web.Response(text="Operation successful")
        except Exception as e:
            # Record error
            FILE_OPERATION_ERRORS.labels(
                node_id=self.node_id,
                operation=operation
            ).inc()
            raise

    async def health_check(self, request):
        """Health check endpoint"""
        try:
            return web.Response(
                text=json.dumps({"status": "healthy"}),
                content_type="application/json"
            )
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return web.Response(
                text=json.dumps({"status": "unhealthy", "error": str(e)}),
                content_type="application/json",
                status=500
            )

    async def metrics(self, request):
        """Expose Prometheus metrics"""
        try:
            # Update current metrics
            self._update_metrics()

            # Generate metrics ONLY from our custom registry
            metrics_data = generate_latest(DFS_REGISTRY)
            return web.Response(
                body=metrics_data,
                content_type='text/plain'
            )
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            NODE_HEALTH.labels(node_id=self.node_id).set(0)
            return web.Response(
                text=json.dumps({"error": str(e)}),
                content_type="application/json",
                status=500
            )

    def _update_metrics(self):
        """Update current metric values"""
        try:
            # Update storage metrics
            usage = psutil.disk_usage(self.data_dir)
            STORAGE_USAGE.labels(node_id=self.node_id, path=self.data_dir).set(usage.used)
            STORAGE_CAPACITY.labels(node_id=self.node_id, path=self.data_dir).set(usage.total)

            # Update system metrics
            SYSTEM_METRICS.labels(node_id=self.node_id, metric='cpu_percent').set(psutil.cpu_percent())
            memory = psutil.virtual_memory()
            SYSTEM_METRICS.labels(node_id=self.node_id, metric='memory_used_percent').set(memory.percent)
            SYSTEM_METRICS.labels(node_id=self.node_id, metric='memory_available_bytes').set(memory.available)

            # Update network metrics
            current_net_io = psutil.net_io_counters()
            current_time = time.time()
            time_diff = current_time - self._last_net_io_time

            # Calculate network I/O differences
            bytes_sent = current_net_io.bytes_sent - self._last_net_io.bytes_sent
            bytes_recv = current_net_io.bytes_recv - self._last_net_io.bytes_recv

            # Update network counters
            NETWORK_IO.labels(node_id=self.node_id, direction='out').inc(bytes_sent)
            NETWORK_IO.labels(node_id=self.node_id, direction='in').inc(bytes_recv)

            # Update operation counters
            NETWORK_OPERATIONS.labels(
                node_id=self.node_id,
                operation='send'
            ).inc(current_net_io.packets_sent - self._last_net_io.packets_sent)
            NETWORK_OPERATIONS.labels(
                node_id=self.node_id,
                operation='receive'
            ).inc(current_net_io.packets_recv - self._last_net_io.packets_recv)

            # Store current values for next update
            self._last_net_io = current_net_io
            self._last_net_io_time = current_time

            # Update cache hit rate
            total_cache_ops = self._cache_hits + self._cache_misses
            if total_cache_ops > 0:
                hit_rate = (self._cache_hits / total_cache_ops) * 100
                CACHE_HIT_RATE.labels(node_id=self.node_id).set(hit_rate)

            # Update process metrics
            cpu_times = self._process.cpu_times()
            PROCESS_CPU_SECONDS.labels(node_id=self.node_id).inc(
                cpu_times.user + cpu_times.system
            )
            PROCESS_MEMORY_BYTES.labels(node_id=self.node_id).set(
                self._process.memory_info().rss
            )

            # Simulate replication lag (random values for testing)
            for target_node in self._replication_nodes:
                # In production, this would be actual replication lag calculation
                lag = time.time() % 10  # Simulate 0-10 seconds lag
                REPLICATION_LAG.labels(
                    source_node=self.node_id,
                    target_node=target_node
                ).set(lag)

            # Update node health
            NODE_HEALTH.labels(node_id=self.node_id).set(1)
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            NODE_HEALTH.labels(node_id=self.node_id).set(0)

    async def _update_metrics_periodically(self):
        """Update metrics every 5 seconds"""
        while True:
            try:
                self._update_metrics()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error in periodic metrics update: {e}")
                await asyncio.sleep(5)  # Still sleep on error to prevent tight loop

async def main():
    try:
        node = StorageNode()
        await node.start()
        while True:
            await asyncio.sleep(3600)  # Keep the server running
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down storage node")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
