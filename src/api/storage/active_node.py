from typing import List, Dict, Optional, Set
import asyncio
import logging
from datetime import datetime
from pathlib import Path
import hashlib
from dataclasses import dataclass
from enum import Enum

@dataclass
class NodeState:
    node_id: str
    status: str
    load: float
    capacity: float
    last_heartbeat: datetime

class ConsistencyLevel(Enum):
    EVENTUAL = "eventual"
    STRONG = "strong"
    QUORUM = "quorum"

class ActiveNode:
    def __init__(self, node_id: str, data_dir: Path, quorum_size: int = 2):
        self.node_id = node_id
        self.data_dir = data_dir
        self.quorum_size = quorum_size
        self.cluster_nodes: Dict[str, NodeState] = {}
        self.load_manager = LoadManager()
        self.consistency_manager = ConsistencyManager(quorum_size)
        self.replication_manager = ReplicationManager()
        self.logger = logging.getLogger(__name__)

    async def start_health_monitor(self) -> None:
        """Start monitoring node health"""
        while True:
            try:
                await self.check_node_health()
                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                self.logger.error(f"Health monitor error: {str(e)}")
                await asyncio.sleep(1)  # Brief pause on error

    async def check_node_health(self) -> None:
        """Check health of all nodes and handle failures"""
        try:
            now = datetime.now()
            failed_nodes = []
            degraded_nodes = []

            for node_id, state in self.cluster_nodes.items():
                if node_id == self.node_id:
                    continue

                # Check heartbeat age
                heartbeat_age = (now - state.last_heartbeat).total_seconds()
                
                # Check node metrics
                node_metrics = await self.get_node_metrics(state)
                
                if heartbeat_age > 30 or not node_metrics:
                    # Node appears to be down
                    failed_nodes.append(state)
                    await self.handle_node_failure(state)
                elif self._is_node_degraded(node_metrics):
                    # Node is up but performing poorly
                    degraded_nodes.append(state)
                    await self.handle_node_degradation(state, node_metrics)

            if failed_nodes or degraded_nodes:
                await self.rebalance_cluster(failed_nodes, degraded_nodes)

        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")

    async def get_node_metrics(self, node: NodeState) -> Optional[Dict[str, float]]:
        """Get current metrics from a node"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{node.address}/metrics",
                    timeout=2.0
                ) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except Exception as e:
            self.logger.warning(f"Failed to get metrics from node {node.node_id}: {str(e)}")
            return None

    def _is_node_degraded(self, metrics: Dict[str, float]) -> bool:
        """Check if node is in a degraded state based on metrics"""
        return (
            metrics.get('cpu_usage', 0) > 80 or
            metrics.get('memory_usage', 0) > 80 or
            metrics.get('disk_usage', 0) > 90 or
            metrics.get('error_rate', 0) > 0.05
        )

    async def handle_node_failure(self, failed_node: NodeState) -> None:
        """Handle complete node failure"""
        try:
            self.logger.warning(f"Handling failure of node {failed_node.node_id}")

            # Remove from active nodes
            self.cluster_nodes.pop(failed_node.node_id, None)

            # Get all data that was on the failed node
            affected_data = self.consistency_manager.get_node_data(failed_node.node_id)

            # Ensure replication factor for all affected data
            replication_tasks = []
            for data_id, version_data in affected_data.items():
                task = self.ensure_replication_level(
                    data_id,
                    version_data,
                    exclude_nodes={failed_node.node_id}
                )
                replication_tasks.append(task)

            # Wait for critical replications with timeout
            try:
                await asyncio.wait(
                    replication_tasks,
                    timeout=30.0,
                    return_when=asyncio.ALL_COMPLETED
                )
            except asyncio.TimeoutError:
                self.logger.error("Timeout waiting for failure recovery replication")

            # Update cluster state
            await self.update_cluster_state()

        except Exception as e:
            self.logger.error(f"Failed to handle node failure: {str(e)}")

    async def handle_node_degradation(self, node: NodeState, metrics: Dict[str, float]) -> None:
        """Handle degraded node performance"""
        try:
            self.logger.warning(f"Handling degradation of node {node.node_id}")

            # Update node state
            node.status = "degraded"
            node.performance_metrics = metrics

            # Gradually migrate load away from degraded node
            if metrics.get('cpu_usage', 0) > 90:
                # Critical load - migrate aggressively
                await self.migrate_load_from_node(node, aggressive=True)
            else:
                # Normal degradation - migrate gradually
                await self.migrate_load_from_node(node, aggressive=False)

        except Exception as e:
            self.logger.error(f"Failed to handle node degradation: {str(e)}")

    async def migrate_load_from_node(self, node: NodeState, aggressive: bool = False) -> None:
        """Migrate load away from a node"""
        try:
            # Get data hosted on the degraded node
            node_data = self.consistency_manager.get_node_data(node.node_id)

            # Sort data by access frequency and size
            sorted_data = sorted(
                node_data.items(),
                key=lambda x: (
                    self.load_manager.get_data_access_frequency(x[0]),
                    len(x[1].content)
                ),
                reverse=True
            )

            # Determine how much data to migrate
            migration_limit = len(sorted_data) if aggressive else len(sorted_data) // 2

            # Migrate most frequently accessed data first
            migration_tasks = []
            for data_id, version_data in sorted_data[:migration_limit]:
                task = self.migrate_data(data_id, version_data, exclude_nodes={node.node_id})
                migration_tasks.append(task)

            # Wait for migrations with timeout
            try:
                await asyncio.wait(
                    migration_tasks,
                    timeout=60.0 if aggressive else 300.0,
                    return_when=asyncio.ALL_COMPLETED
                )
            except asyncio.TimeoutError:
                self.logger.warning("Timeout waiting for load migration")

        except Exception as e:
            self.logger.error(f"Failed to migrate load: {str(e)}")

    async def migrate_data(self, data_id: str, version_data: VersionedData,
                          exclude_nodes: Set[str]) -> None:
        """Migrate a single piece of data to a new node"""
        try:
            # Find best target node
            target_node = await self.find_migration_target(
                data_id,
                len(version_data.content),
                exclude_nodes
            )
            if not target_node:
                raise ValueError("No suitable migration target found")

            # Replicate to new node
            result = await self.replication_manager.replicate_to_node(
                target_node,
                data_id,
                version_data.content,
                version_data.checksum
            )

            if result.get('status') != 'success':
                raise RuntimeError(f"Migration failed: {result.get('error')}")

            # Update version map
            await self.consistency_manager.update_node_version(
                target_node.node_id,
                data_id,
                version_data
            )

        except Exception as e:
            self.logger.error(f"Failed to migrate data {data_id}: {str(e)}")
            raise

    async def find_migration_target(self, data_id: str, data_size: int,
                                  exclude_nodes: Set[str]) -> Optional[NodeState]:
        """Find best node to migrate data to"""
        try:
            candidate_nodes = [
                node for node in self.get_active_nodes()
                if (
                    node.node_id not in exclude_nodes and
                    node.status == "active" and
                    node.available_storage > data_size * 1.5  # Include headroom
                )
            ]

            if not candidate_nodes:
                return None

            # Score nodes based on multiple factors
            scored_nodes = []
            for node in candidate_nodes:
                score = (
                    (1 - self.load_manager.get_node_load(node.node_id)) * 0.4 +  # Load
                    (node.available_storage / node.total_storage) * 0.3 +  # Storage
                    (1 - min(1.0, node.network_latency / 1000.0)) * 0.2 +  # Latency
                    (0.1 if node.region != self.region else 0)  # Geographic distribution
                )
                scored_nodes.append((score, node))

            # Return node with highest score
            return max(scored_nodes, key=lambda x: x[0])[1]

        except Exception as e:
            self.logger.error(f"Failed to find migration target: {str(e)}")
            return None

    async def rebalance_cluster(self, failed_nodes: List[NodeState],
                               degraded_nodes: List[NodeState]) -> None:
        """Rebalance cluster after node failures or degradation"""
        try:
            self.logger.info("Starting cluster rebalance")
            
            # Get current data distribution
            distribution = await self.get_data_distribution()
            
            # Calculate ideal distribution
            ideal_distribution = self.calculate_ideal_distribution(distribution)
            
            # Generate migration plan
            migration_plan = self.generate_migration_plan(
                distribution,
                ideal_distribution,
                failed_nodes,
                degraded_nodes
            )
            
            # Execute migrations in parallel with rate limiting
            async with asyncio.Semaphore(5) as semaphore:  # Limit concurrent migrations
                migration_tasks = []
                for source, target, data_id in migration_plan:
                    task = self.execute_migration(
                        source, target, data_id, semaphore
                    )
                    migration_tasks.append(task)
                
                await asyncio.gather(*migration_tasks)
            
            self.logger.info("Cluster rebalance completed")
            
        except Exception as e:
            self.logger.error(f"Cluster rebalance failed: {str(e)}")

    async def execute_migration(self, source: NodeState, target: NodeState,
                              data_id: str, semaphore: asyncio.Semaphore) -> None:
        """Execute a single migration in the rebalance plan"""
        async with semaphore:
            try:
                version_data = await self.get_version_data(source, data_id)
                if version_data:
                    await self.migrate_data(
                        data_id,
                        version_data,
                        exclude_nodes={source.node_id}
                    )
            except Exception as e:
                self.logger.error(
                    f"Failed to migrate {data_id} from {source.node_id} "
                    f"to {target.node_id}: {str(e)}"
                )

    async def handle_request(self, request) -> web.Response:
        """Handle incoming requests with load balancing"""
        if not self.load_manager.can_handle_request():
            alternate_node = self.find_available_node()
            if alternate_node:
                return await self.forward_request(request, alternate_node)

        if request.method == 'GET':
            return await self.handle_read(request)
        elif request.method in ['PUT', 'POST']:
            return await self.handle_write(request)
        elif request.method == 'DELETE':
            return await self.handle_delete(request)

    async def handle_write(self, request) -> web.Response:
        """Handle write requests with parallel replication and load balancing"""
        try:
            data_id = request.match_info['data_id']
            content = await request.read()
            checksum = hashlib.sha256(content).hexdigest()

            # Check if we should handle this write
            if not self.load_manager.can_handle_write():
                alternate_node = self.find_least_loaded_node()
                if alternate_node:
                    return await self.forward_request(request, alternate_node)

            # Create versioned data
            version_data = VersionedData(
                content=content,
                version=await self.consistency_manager.get_next_version(data_id),
                timestamp=datetime.now(),
                checksum=checksum
            )

            # Get target nodes for replication
            target_nodes = self.replication_manager._select_replica_nodes(
                self.quorum_size - 1,  # Exclude self
                {self.node_id}
            )

            if len(target_nodes) < self.quorum_size - 1:
                return web.Response(
                    status=503,
                    text=f"Not enough nodes available for quorum (need {self.quorum_size})"
                )

            # Start parallel writes
            write_futures = []
            
            # Local write first to ensure durability
            try:
                local_path = self.data_dir / data_id
                await self.write_local(local_path, content)
                await self.consistency_manager.update_node_version(
                    self.node_id, data_id, version_data
                )
            except Exception as e:
                self.logger.error(f"Local write failed: {str(e)}")
                return web.Response(status=500, text=f"Local write failed: {str(e)}")

            # Parallel remote writes
            for node in target_nodes:
                future = self.replication_manager.replicate_to_node(
                    node, data_id, content, checksum
                )
                write_futures.append(future)

            # Wait for quorum with timeout
            try:
                done, pending = await asyncio.wait(
                    write_futures,
                    timeout=5.0,  # 5 second timeout
                    return_when=asyncio.FIRST_N_COMPLETED(self.quorum_size - 1)
                )

                # Cancel pending operations if quorum achieved
                for task in pending:
                    task.cancel()

                # Check results
                successful_writes = sum(
                    1 for task in done 
                    if task.result().get('status') == 'success'
                )

                if successful_writes < self.quorum_size - 1:
                    # Rollback if quorum not achieved
                    await self.rollback_write(data_id)
                    return web.Response(
                        status=503,
                        text=f"Write quorum not achieved ({successful_writes + 1}/{self.quorum_size})"
                    )

                # Update load metrics
                self.load_manager.record_write(len(content))

                return web.Response(
                    status=200,
                    text=f"Write successful, replicated to {successful_writes + 1} nodes"
                )

            except asyncio.TimeoutError:
                # Rollback on timeout
                await self.rollback_write(data_id)
                return web.Response(
                    status=503,
                    text="Write timeout waiting for quorum"
                )

        except Exception as e:
            self.logger.error(f"Write failed: {str(e)}")
            return web.Response(status=500, text=str(e))

    async def rollback_write(self, data_id: str) -> None:
        """Rollback a failed write operation"""
        try:
            # Delete local copy
            local_path = self.data_dir / data_id
            if local_path.exists():
                local_path.unlink()

            # Remove version from consistency manager
            await self.consistency_manager.remove_version(self.node_id, data_id)

            # Notify other nodes to rollback
            rollback_futures = []
            for node in self.get_active_nodes():
                if node.node_id != self.node_id:
                    future = self.notify_rollback(node, data_id)
                    rollback_futures.append(future)

            # Wait for rollbacks with timeout
            await asyncio.wait(
                rollback_futures,
                timeout=2.0,
                return_when=asyncio.ALL_COMPLETED
            )

        except Exception as e:
            self.logger.error(f"Rollback failed: {str(e)}")

    async def notify_rollback(self, node: NodeState, data_id: str) -> None:
        """Notify a node to rollback a write"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"http://{node.address}/storage/data/{data_id}",
                    headers={'X-Operation': 'rollback'}
                ) as response:
                    if response.status != 200:
                        self.logger.warning(
                            f"Rollback notification failed for node {node.node_id}: "
                            f"HTTP {response.status}"
                        )
        except Exception as e:
            self.logger.error(f"Failed to notify rollback to node {node.node_id}: {str(e)}")

    def find_least_loaded_node(self) -> Optional[NodeState]:
        """Find the node with the lowest load"""
        active_nodes = self.get_active_nodes()
        if not active_nodes:
            return None

        return min(
            active_nodes,
            key=lambda n: self.load_manager.get_node_load(n.node_id)
        )

    async def handle_read(self, request) -> web.Response:
        """Handle read requests with load balancing and consistency guarantees"""
        try:
            data_id = request.match_info['data_id']
            consistency = request.query.get('consistency', ConsistencyLevel.QUORUM.value)
            
            # Check if we should handle this read
            if not self.load_manager.can_handle_read():
                alternate_node = self.find_least_loaded_node()
                if alternate_node:
                    return await self.forward_request(request, alternate_node)

            # Get available nodes with the data
            nodes_with_data = await self.find_nodes_with_data(data_id)
            if not nodes_with_data:
                return web.Response(status=404, text="Data not found")

            if consistency == ConsistencyLevel.STRONG.value:
                content = await self.handle_strong_read(data_id, nodes_with_data)
            elif consistency == ConsistencyLevel.QUORUM.value:
                content = await self.handle_quorum_read(data_id, nodes_with_data)
            else:  # EVENTUAL consistency
                content = await self.handle_eventual_read(data_id, nodes_with_data)

            # Update read metrics
            self.load_manager.record_read(len(content) if content else 0)

            if content is None:
                return web.Response(status=404, text="Data not found")

            return web.Response(body=content)

        except ConsistencyError as e:
            return web.Response(status=409, text=str(e))
        except Exception as e:
            self.logger.error(f"Read failed: {str(e)}")
            return web.Response(status=500, text=str(e))

    async def handle_strong_read(self, data_id: str, nodes: List[NodeState]) -> Optional[bytes]:
        """Handle read with strong consistency - read from all nodes"""
        try:
            # Read from all nodes in parallel
            read_futures = []
            for node in nodes:
                future = self.read_from_node(node, data_id)
                read_futures.append(future)

            # Wait for all reads with timeout
            done, pending = await asyncio.wait(
                read_futures,
                timeout=5.0,
                return_when=asyncio.ALL_COMPLETED
            )

            # Cancel any pending reads
            for task in pending:
                task.cancel()

            # Collect results
            read_results = []
            for task in done:
                try:
                    result = task.result()
                    if result and result.get('status') == 'success':
                        read_results.append(ReadResult(
                            content=result['content'],
                            version=result['version'],
                            timestamp=result['timestamp']
                        ))
                except Exception as e:
                    self.logger.error(f"Read task failed: {str(e)}")

            if not read_results:
                return None

            # Check consistency
            if not self.consistency_manager.verify_consistency(read_results):
                # Trigger repair if inconsistent
                await self.repair_inconsistency(data_id, read_results)
                raise ConsistencyError("Inconsistent data detected, repair initiated")

            # Return the most recent version
            latest_result = max(read_results, key=lambda r: (r.version, r.timestamp))
            return latest_result.content

        except Exception as e:
            self.logger.error(f"Strong read failed: {str(e)}")
            raise

    async def handle_quorum_read(self, data_id: str, nodes: List[NodeState]) -> Optional[bytes]:
        """Handle read with quorum consistency"""
        try:
            # Calculate required quorum size
            required_reads = (len(nodes) // 2) + 1

            # Read from nodes in parallel
            read_futures = []
            for node in nodes:
                future = self.read_from_node(node, data_id)
                read_futures.append(future)

            # Wait for quorum with timeout
            done, pending = await asyncio.wait(
                read_futures,
                timeout=3.0,
                return_when=asyncio.FIRST_N_COMPLETED(required_reads)
            )

            # Cancel pending reads
            for task in pending:
                task.cancel()

            # Collect successful results
            read_results = []
            for task in done:
                try:
                    result = task.result()
                    if result and result.get('status') == 'success':
                        read_results.append(ReadResult(
                            content=result['content'],
                            version=result['version'],
                            timestamp=result['timestamp']
                        ))
                except Exception as e:
                    self.logger.error(f"Read task failed: {str(e)}")

            if len(read_results) < required_reads:
                raise ConsistencyError(
                    f"Failed to achieve read quorum ({len(read_results)}/{required_reads})"
                )

            # Return the most recent version from quorum
            latest_result = max(read_results, key=lambda r: (r.version, r.timestamp))
            
            # Schedule async repair if versions differ
            if not all(r.version == latest_result.version for r in read_results):
                asyncio.create_task(
                    self.repair_inconsistency(data_id, read_results)
                )

            return latest_result.content

        except Exception as e:
            self.logger.error(f"Quorum read failed: {str(e)}")
            raise

    async def handle_eventual_read(self, data_id: str, nodes: List[NodeState]) -> Optional[bytes]:
        """Handle read with eventual consistency - read from closest/least loaded node"""
        try:
            # Sort nodes by load and latency
            sorted_nodes = sorted(
                nodes,
                key=lambda n: (
                    self.load_manager.get_node_load(n.node_id),
                    n.network_latency
                )
            )

            # Try nodes in order until successful
            for node in sorted_nodes:
                try:
                    result = await self.read_from_node(node, data_id)
                    if result and result.get('status') == 'success':
                        return result['content']
                except Exception as e:
                    self.logger.warning(
                        f"Failed to read from node {node.node_id}: {str(e)}"
                    )
                    continue

            return None

        except Exception as e:
            self.logger.error(f"Eventual read failed: {str(e)}")
            raise

    async def read_from_node(self, node: NodeState, data_id: str) -> Dict[str, Any]:
        """Read data from a specific node"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{node.address}/storage/data/{data_id}"
                ) as response:
                    if response.status == 200:
                        return {
                            'status': 'success',
                            'content': await response.read(),
                            'version': int(response.headers.get('X-Version', '0')),
                            'timestamp': datetime.fromisoformat(
                                response.headers.get('X-Timestamp', datetime.min.isoformat())
                            )
                        }
                    else:
                        return {
                            'status': 'error',
                            'error': f"HTTP {response.status}: {await response.text()}"
                        }

        except Exception as e:
            self.logger.error(f"Failed to read from node {node.node_id}: {str(e)}")
            return {'status': 'error', 'error': str(e)}

    async def find_nodes_with_data(self, data_id: str) -> List[NodeState]:
        """Find all nodes that have a copy of the data"""
        try:
            # Get all active nodes
            active_nodes = self.get_active_nodes()
            
            # Check version map first for efficiency
            nodes_in_map = set(
                self.consistency_manager.version_map.get(data_id, {}).keys()
            )
            
            # Filter active nodes that have the data
            return [
                node for node in active_nodes
                if node.node_id in nodes_in_map
            ]

        except Exception as e:
            self.logger.error(f"Failed to find nodes with data: {str(e)}")
            return []

    async def write_local(self, path: Path, content: bytes) -> None:
        """Write data locally with proper locking"""
        async with self.consistency_manager.get_write_lock(path):
            path.write_bytes(content)

    async def read_local(self, path: Path) -> bytes:
        """Read data locally with proper locking"""
        async with self.consistency_manager.get_read_lock(path):
            return path.read_bytes()

    def get_active_nodes(self) -> List[NodeState]:
        """Get list of active nodes in the cluster"""
        now = datetime.now()
        return [
            node for node in self.cluster_nodes.values()
            if (now - node.last_heartbeat).total_seconds() < 30
            and node.status == "active"
        ]

    async def update_cluster_state(self) -> None:
        """Periodic cluster state update"""
        while True:
            try:
                # Update local node state
                self.cluster_nodes[self.node_id] = NodeState(
                    node_id=self.node_id,
                    status="active",
                    load=self.load_manager.get_current_load(),
                    capacity=self.load_manager.get_capacity(),
                    last_heartbeat=datetime.now()
                )

                # Get states from other nodes
                node_states = await self.fetch_node_states()
                self.cluster_nodes.update(node_states)

                # Clean up inactive nodes
                self.remove_inactive_nodes()

            except Exception as e:
                self.logger.error(f"Failed to update cluster state: {str(e)}")

            await asyncio.sleep(5)  # Update every 5 seconds

    def remove_inactive_nodes(self) -> None:
        """Remove nodes that haven't sent heartbeat recently"""
        now = datetime.now()
        inactive_nodes = [
            node_id for node_id, state in self.cluster_nodes.items()
            if (now - state.last_heartbeat).total_seconds() > 30
        ]
        for node_id in inactive_nodes:
            del self.cluster_nodes[node_id]

class ConsistencyError(Exception):
    """Raised when consistency requirements cannot be met"""
    pass

@dataclass
class ReadResult:
    """Result from a read operation"""
    content: bytes
    version: int
    timestamp: datetime
