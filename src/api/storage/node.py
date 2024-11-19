import os
import asyncio
import logging
import time
import psutil
from aiohttp import web
import json
from prometheus_client import (
    generate_latest,
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry
)

# Create a custom registry for DFS metrics
DFS_REGISTRY = CollectorRegistry()

# Define request metrics
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

        # Use a directory in the user's home for testing
        self.data_dir = os.path.expanduser('~/dfs_data')

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info(f"Using storage directory: {self.data_dir}")

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

            # Initialize request metrics with 0
            REQUEST_COUNT.labels(method='GET', endpoint='/metrics', status='success').inc(0)
            REQUEST_LATENCY.labels(method='GET', endpoint='/metrics').observe(0)

            # Set node as healthy
            NODE_HEALTH.labels(node_id=self.node_id).set(1)

            logger.info("Metrics initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing metrics: {e}")
            NODE_HEALTH.labels(node_id=self.node_id).set(0)

    async def start(self):
        """Start the storage node"""
        app = web.Application()
        app.add_routes([
            web.get('/metrics', self.metrics),
            web.get('/health', self.health_check)
        ])

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8001)
        await site.start()

        logger.info(f"Storage node {self.node_id} started and listening on port 8001")

    async def health_check(self, request):
        """Health check endpoint"""
        try:
            start_time = time.time()

            # Track this request
            REQUEST_COUNT.labels(method='GET', endpoint='/health', status='success').inc()
            REQUEST_LATENCY.labels(method='GET', endpoint='/health').observe(time.time() - start_time)

            return web.Response(
                text=json.dumps({"status": "healthy"}),
                content_type="application/json"
            )
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            REQUEST_COUNT.labels(method='GET', endpoint='/health', status='error').inc()
            return web.Response(
                text=json.dumps({"status": "unhealthy", "error": str(e)}),
                content_type="application/json",
                status=500
            )

    async def metrics(self, request):
        """Expose Prometheus metrics"""
        try:
            start_time = time.time()

            # Update current metrics
            self._update_metrics()

            # Track this request
            REQUEST_COUNT.labels(method='GET', endpoint='/metrics', status='success').inc()
            REQUEST_LATENCY.labels(method='GET', endpoint='/metrics').observe(time.time() - start_time)

            # Generate metrics ONLY from our custom registry
            metrics_data = generate_latest(DFS_REGISTRY)
            return web.Response(
                body=metrics_data,
                content_type='text/plain; version=0.0.4'
            )
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            REQUEST_COUNT.labels(method='GET', endpoint='/metrics', status='error').inc()
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

            # Update node health
            NODE_HEALTH.labels(node_id=self.node_id).set(1)
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            NODE_HEALTH.labels(node_id=self.node_id).set(0)

async def main():
    try:
        node = StorageNode()
        await node.start()

        # Keep the application running
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
