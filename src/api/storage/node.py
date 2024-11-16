import os
import asyncio
import logging
import time
from aiohttp import web
import json
from .cluster_manager import StorageClusterManager
from .replication_manager import ReplicationManager, ReplicationPolicy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StorageNode:
    def __init__(self):
        self.node_id = os.environ.get('NODE_ID')
        self.namespace = os.environ.get('NAMESPACE', 'default')
        self.data_dir = os.environ.get('STORAGE_DATA_DIR', '/data')

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)

        # Initialize managers
        self.cluster_manager = StorageClusterManager(namespace=self.namespace)

        policy = ReplicationPolicy(
            min_copies=3,
            sync_replication=True,
            consistency_level="quorum"
        )
        self.replication_manager = ReplicationManager(self.cluster_manager, policy)

    async def start(self):
        """Start the storage node"""
        # Start HTTP server first
        app = web.Application()
        app.add_routes([
            web.get('/health', self.health_check),
            web.get('/ready', self.ready_check),
            web.post('/storage/replicate', self.handle_replication),
            web.get('/storage/list', self.list_data),
            web.get('/storage/data/{data_id}', self.get_data),
            web.put('/storage/data/{data_id}', self.store_data),
            web.delete('/storage/data/{data_id}', self.delete_data),
        ])

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()

        logger.info(f"Storage node {self.node_id} started and listening on port 8080")

        # Give the HTTP server a moment to start
        await asyncio.sleep(2)

        # Start cluster and replication managers
        await asyncio.gather(
            self.cluster_manager.start(),
            self.replication_manager.start()
        )

    async def health_check(self, request):
        """Health check endpoint"""
        return web.Response(text="healthy")

    async def ready_check(self, request):
        """Readiness check endpoint"""
        try:
            logging.info(f"Starting readiness check for node {self.node_id}")

            # Check if cluster manager is initialized
            if not hasattr(self, 'cluster_manager'):
                logging.error("Cluster manager not initialized")
                return web.Response(status=503, text="not ready - cluster manager not initialized")

            # Get cluster status with timeout
            try:
                cluster_status_task = asyncio.create_task(self.cluster_manager.get_cluster_status_async())
                done, _ = await asyncio.wait({cluster_status_task}, timeout=2.0)
                if cluster_status_task in done:
                    cluster_status = cluster_status_task.result()
                else:
                    raise asyncio.TimeoutError
            except asyncio.TimeoutError:
                logging.error("Timeout getting cluster status")
                return web.Response(status=503, text="not ready - cluster status timeout")

            logging.info(f"Cluster status: {cluster_status}")
            logging.info(f"Current node is leader: {self.cluster_manager.leader}")
            logging.info(f"Current leader: {cluster_status.get('leader_node')}")

            # We're ready if:
            # 1. We are the leader, or
            # 2. We can see the leader and have a healthy connection, or
            # 3. We're in the initial cluster formation phase (grace period)
            startup_grace_period = 30  # seconds
            time_since_start = time.time() - self.cluster_manager.start_time

            if self.cluster_manager.leader:
                logging.info("Node is ready - we are the leader")
                return web.Response(text="ready - leader")
            elif cluster_status.get("leader_node") and cluster_status.get("healthy_nodes", 0) > 0:
                logging.info("Node is ready - healthy connection to leader")
                return web.Response(text="ready - follower")
            elif time_since_start < startup_grace_period:
                logging.info("Node is in startup grace period")
                return web.Response(text="ready - startup grace period")

            logging.warning("Node is not ready - no leader connection and grace period expired")
            return web.Response(status=503, text="not ready - no leader connection")
        except Exception as e:
            logging.error(f"Readiness check failed with exception: {str(e)}")
            return web.Response(status=503, text=f"not ready - internal error: {str(e)}")

    async def handle_replication(self, request):
        """Handle incoming replication requests"""
        data = await request.json()
        data_id = data['data_id']
        content = bytes.fromhex(data['data'])
        checksum = data['checksum']

        # Verify checksum
        import hashlib
        if hashlib.sha256(content).hexdigest() != checksum:
            return web.Response(status=400, text="checksum mismatch")

        # Store the data
        file_path = os.path.join(self.data_dir, data_id)
        with open(file_path, 'wb') as f:
            f.write(content)

        return web.Response(
            text=json.dumps({"status": "success", "checksum": checksum}),
            content_type='application/json'
        )

    async def list_data(self, request):
        """List all data IDs stored on this node"""
        try:
            data_ids = [f for f in os.listdir(self.data_dir) if os.path.isfile(os.path.join(self.data_dir, f))]
            return web.Response(
                text=json.dumps(data_ids),
                content_type='application/json'
            )
        except Exception as e:
            logger.error(f"Failed to list data: {str(e)}")
            return web.Response(status=500, text=str(e))

    async def get_data(self, request):
        """Retrieve data by ID"""
        data_id = request.match_info['data_id']
        file_path = os.path.join(self.data_dir, data_id)

        if not os.path.exists(file_path):
            return web.Response(status=404, text="data not found")

        return web.FileResponse(file_path)

    async def store_data(self, request):
        """Store new data"""
        data_id = request.match_info['data_id']
        content = await request.read()

        # Store locally
        file_path = os.path.join(self.data_dir, data_id)
        with open(file_path, 'wb') as f:
            f.write(content)

        # Trigger replication
        try:
            replicated_nodes = await self.replication_manager.replicate_data(
                data_id,
                content,
                self.node_id
            )
            return web.Response(
                text=json.dumps({
                    "status": "success",
                    "replicated_to": replicated_nodes
                }),
                content_type='application/json'
            )
        except Exception as e:
            logger.error(f"Replication failed: {str(e)}")
            # Delete local copy if replication failed
            os.unlink(file_path)
            return web.Response(status=500, text=str(e))

    async def delete_data(self, request):
        """Delete data by ID"""
        data_id = request.match_info['data_id']
        file_path = os.path.join(self.data_dir, data_id)

        if not os.path.exists(file_path):
            return web.Response(status=404, text="data not found")

        os.unlink(file_path)
        return web.Response(text="deleted")

async def main():
    node = StorageNode()
    await node.start()

    # Keep the node running
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
