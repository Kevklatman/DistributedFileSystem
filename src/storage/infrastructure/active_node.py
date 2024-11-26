"""Active node management for the distributed file system."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set, Any, Union, BinaryIO
import os
from dataclasses import dataclass
from enum import Enum
import hashlib
import aiohttp
from aiohttp import web
from pathlib import Path

from src.storage.infrastructure.interfaces import StorageInterface, MetricsCollector
from src.storage.infrastructure.load_manager import LoadManager
from src.storage.infrastructure.data.consistency_manager import ConsistencyManager
from src.storage.infrastructure.data.replication_manager import ReplicationManager
from src.models.models import (
    Volume,
    NodeState,
    StoragePool,
    ThinProvisioningState,
    DeduplicationState,
    CompressionState,
    DataProtection,
    DataTemperature,
    TierType,
    CloudTieringPolicy,
    ReplicationPolicy
)


class ConsistencyLevel(Enum):
    """Consistency levels for read/write operations."""
    EVENTUAL = "eventual"
    STRONG = "strong"
    QUORUM = "quorum"


@dataclass
class WriteResult:
    """Result of a write operation."""
    success: bool
    block_id: str
    error: Optional[str] = None


class ActiveNode(StorageInterface):
    """Active node in the distributed file system."""

    def __init__(
        self,
        node_id: str,
        data_dir: str = None,
        quorum_size: int = 2,
        write_timeout: float = 5.0,
        replication_policy: Optional[ReplicationPolicy] = None,
        tiering_policy: Optional[CloudTieringPolicy] = None,
        max_cpu_threshold: float = 80.0,
        max_memory_threshold: float = 80.0,
        max_requests_per_second: float = 1000.0
    ):
        """Initialize active node."""
        self.node_id = node_id
        self.data_dir = data_dir or os.path.join(os.getcwd(), "data")
        self.quorum_size = quorum_size
        self.write_timeout = write_timeout
        
        # Initialize state tracking with proper model
        self.node_state = NodeState(
            node_id=node_id,
            status="healthy",
            last_heartbeat=datetime.now(),
            load=0.0,
            available_storage=0,
            network_latency=0.0,
            volumes=[]
        )
        
        # Initialize policies
        self.replication_policy = replication_policy or ReplicationPolicy()
        self.tiering_policy = tiering_policy
        
        # Initialize managers
        self.load_manager = LoadManager(
            max_cpu_threshold=max_cpu_threshold,
            max_memory_threshold=max_memory_threshold,
            max_requests_per_second=max_requests_per_second
        )
        self.consistency_manager = ConsistencyManager(quorum_size)
        self.replication_manager = ReplicationManager()
        self.logger = logging.getLogger(__name__)
        
        # Create data directory
        os.makedirs(self.data_dir, exist_ok=True)

    def is_healthy(self) -> bool:
        """Check if the node is healthy."""
        return self.node_state.status == "healthy"

    def _mark_unhealthy(self) -> None:
        """Mark the node as unhealthy."""
        self.node_state.status = "unhealthy"
        self.node_state.last_heartbeat = datetime.now()

    def _mark_healthy(self) -> None:
        """Mark the node as healthy."""
        self.node_state.status = "healthy"
        self.node_state.last_heartbeat = datetime.now()

    async def _get_replica_nodes(self) -> List[Any]:
        """Get list of available replica nodes."""
        return self._replica_nodes

    def _get_block_path(self, volume_id: str, block_id: str) -> str:
        """Get the filesystem path for a block."""
        volume_dir = os.path.join(self.data_dir, volume_id)
        os.makedirs(volume_dir, exist_ok=True)
        return os.path.join(volume_dir, block_id)

    async def store_data(
        self,
        volume_id: str,
        block_id: str,
        data: bytes,
        consistency_level: ConsistencyLevel
    ) -> WriteResult:
        """Store data block with replication."""
        if not self.is_healthy():
            raise NodeUnhealthyError("Node is not healthy")

        # Store locally
        block_path = self._get_block_path(volume_id, block_id)
        try:
            with open(block_path, 'wb') as f:
                f.write(data)
        except Exception as e:
            self.logger.error(f"Failed to write data locally: {str(e)}")
            raise WriteFailureError("Failed to write data locally")

        # For eventual consistency, we're done
        if consistency_level == ConsistencyLevel.EVENTUAL:
            return WriteResult(success=True, block_id=block_id)

        # Get replica nodes for stronger consistency levels
        replica_nodes = await self._get_replica_nodes()
        
        # Check if we have enough nodes for strong consistency
        if consistency_level == ConsistencyLevel.STRONG and len(replica_nodes) < self.quorum_size - 1:
            # Rollback local write
            try:
                os.remove(block_path)
            except:
                pass
            raise InsufficientNodesError(f"Need {self.quorum_size} nodes for strong consistency")

        # Replicate to other nodes
        if replica_nodes:
            replication_tasks = []
            for node in replica_nodes:
                task = asyncio.create_task(
                    node.store_data(
                        volume_id=volume_id,
                        block_id=block_id,
                        data=data,
                        consistency_level=consistency_level
                    )
                )
                replication_tasks.append(task)

            try:
                done, pending = await asyncio.wait(
                    replication_tasks,
                    timeout=self.write_timeout,
                    return_when=asyncio.ALL_COMPLETED if consistency_level == ConsistencyLevel.STRONG else asyncio.FIRST_COMPLETED
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()

                if consistency_level == ConsistencyLevel.STRONG and len(done) < len(replica_nodes):
                    # Rollback local write for strong consistency
                    try:
                        os.remove(block_path)
                    except:
                        pass
                    raise WriteTimeoutError("Failed to achieve required replication level")

                # Check results
                for task in done:
                    result = await task
                    if not result.success:
                        # Rollback local write
                        try:
                            os.remove(block_path)
                        except:
                            pass
                        raise WriteFailureError(f"Replication failed: {result.error}")

            except asyncio.TimeoutError:
                # Rollback local write
                try:
                    os.remove(block_path)
                except:
                    pass
                raise WriteTimeoutError("Write operation timed out")

        return WriteResult(success=True, block_id=block_id)

    async def read_data(self, volume_id: str, block_id: str) -> bytes:
        """Read data from a block."""
        if not self.is_healthy():
            raise NodeUnhealthyError("Node is not healthy")

        block_path = self._get_block_path(volume_id, block_id)
        try:
            with open(block_path, 'rb') as f:
                return f.read()
        except FileNotFoundError:
            raise KeyError(f"Block {block_id} not found")
        except Exception as e:
            self.logger.error(f"Failed to read data: {str(e)}")
            raise

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
                    f"http://{node.address}/metrics", timeout=2.0
                ) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except Exception as e:
            self.logger.warning(
                f"Failed to get metrics from node {node.node_id}: {str(e)}"
            )
            return None

    def _is_node_degraded(self, metrics: Dict[str, float]) -> bool:
        """Check if node is in a degraded state based on metrics"""
        return (
            metrics.get("cpu_usage", 0) > 80
            or metrics.get("memory_usage", 0) > 80
            or metrics.get("disk_usage", 0) > 90
            or metrics.get("error_rate", 0) > 0.05
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
                    data_id, version_data, exclude_nodes={failed_node.node_id}
                )
                replication_tasks.append(task)

            # Wait for critical replications with timeout
            try:
                await asyncio.wait(
                    replication_tasks, timeout=30.0, return_when=asyncio.ALL_COMPLETED
                )
            except asyncio.TimeoutError:
                self.logger.error("Timeout waiting for failure recovery replication")

            # Update cluster state
            await self.update_cluster_state()

        except Exception as e:
            self.logger.error(f"Failed to handle node failure: {str(e)}")

    async def handle_node_degradation(
        self, node: NodeState, metrics: Dict[str, float]
    ) -> None:
        """Handle degraded node performance"""
        try:
            self.logger.warning(f"Handling degradation of node {node.node_id}")

            # Update node state
            node.status = "degraded"
            node.performance_metrics = metrics

            # Gradually migrate load away from degraded node
            if metrics.get("cpu_usage", 0) > 90:
                # Critical load - migrate aggressively
                await self.migrate_load_from_node(node, aggressive=True)
            else:
                # Normal degradation - migrate gradually
                await self.migrate_load_from_node(node, aggressive=False)

        except Exception as e:
            self.logger.error(f"Failed to handle node degradation: {str(e)}")

    async def migrate_load_from_node(
        self, node: NodeState, aggressive: bool = False
    ) -> None:
        """Migrate load away from a node"""
        try:
            # Get data hosted on the degraded node
            node_data = self.consistency_manager.get_node_data(node.node_id)

            # Sort data by access frequency and size
            sorted_data = sorted(
                node_data.items(),
                key=lambda x: (
                    self.load_manager.get_data_access_frequency(x[0]),
                    len(x[1].content),
                ),
                reverse=True,
            )

            # Determine how much data to migrate
            migration_limit = len(sorted_data) if aggressive else len(sorted_data) // 2

            # Migrate most frequently accessed data first
            migration_tasks = []
            for data_id, version_data in sorted_data[:migration_limit]:
                task = self.migrate_data(
                    data_id, version_data, exclude_nodes={node.node_id}
                )
                migration_tasks.append(task)

            # Wait for migrations with timeout
            try:
                await asyncio.wait(
                    migration_tasks,
                    timeout=60.0 if aggressive else 300.0,
                    return_when=asyncio.ALL_COMPLETED,
                )
            except asyncio.TimeoutError:
                self.logger.warning("Timeout waiting for load migration")

        except Exception as e:
            self.logger.error(f"Failed to migrate load: {str(e)}")

    async def migrate_data(
        self, data_id: str, version_data: Volume, exclude_nodes: Set[str]
    ) -> None:
        """Migrate a single piece of data to a new node"""
        try:
            # Find best target node
            target_node = await self.find_migration_target(
                data_id, len(version_data.content), exclude_nodes
            )
            if not target_node:
                raise ValueError("No suitable migration target found")

            # Replicate to new node
            result = await self.replication_manager.replicate_to_node(
                target_node, data_id, version_data.content, version_data.checksum
            )

            if result.get("status") != "success":
                raise RuntimeError(f"Migration failed: {result.get('error')}")

            # Update version map
            await self.consistency_manager.update_node_version(
                target_node.node_id, data_id, version_data
            )

        except Exception as e:
            self.logger.error(f"Failed to migrate data {data_id}: {str(e)}")
            raise

    async def find_migration_target(
        self, data_id: str, data_size: int, exclude_nodes: Set[str]
    ) -> Optional[NodeState]:
        """Find best node to migrate data to"""
        try:
            candidate_nodes = [
                node
                for node in self.get_active_nodes()
                if (
                    node.node_id not in exclude_nodes
                    and node.status == "active"
                    and node.available_storage > data_size * 1.5  # Include headroom
                )
            ]

            if not candidate_nodes:
                return None

            # Score nodes based on multiple factors
            scored_nodes = []
            for node in candidate_nodes:
                score = (
                    (1 - self.load_manager.get_node_load(node.node_id)) * 0.4  # Load
                    + (node.available_storage / node.total_storage) * 0.3  # Storage
                    + (1 - min(1.0, node.network_latency / 1000.0)) * 0.2  # Latency
                    + (
                        0.1 if node.region != self.region else 0
                    )  # Geographic distribution
                )
                scored_nodes.append((score, node))

            # Return node with highest score
            return max(scored_nodes, key=lambda x: x[0])[1]

        except Exception as e:
            self.logger.error(f"Failed to find migration target: {str(e)}")
            return None

    async def rebalance_cluster(
        self, failed_nodes: List[NodeState], degraded_nodes: List[NodeState]
    ) -> None:
        """Rebalance cluster after node failures or degradation"""
        try:
            self.logger.info("Starting cluster rebalance")

            # Get current data distribution
            distribution = await self.get_data_distribution()

            # Calculate ideal distribution
            ideal_distribution = self.calculate_ideal_distribution(distribution)

            # Generate migration plan
            migration_plan = self.generate_migration_plan(
                distribution, ideal_distribution, failed_nodes, degraded_nodes
            )

            # Execute migrations in parallel with rate limiting
            async with asyncio.Semaphore(5) as semaphore:  # Limit concurrent migrations
                migration_tasks = []
                for source, target, data_id in migration_plan:
                    task = self.execute_migration(source, target, data_id, semaphore)
                    migration_tasks.append(task)

                await asyncio.gather(*migration_tasks)

            self.logger.info("Cluster rebalance completed")

        except Exception as e:
            self.logger.error(f"Cluster rebalance failed: {str(e)}")

    async def execute_migration(
        self,
        source: NodeState,
        target: NodeState,
        data_id: str,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Execute a single migration in the rebalance plan"""
        async with semaphore:
            try:
                version_data = await self.get_version_data(source, data_id)
                if version_data:
                    await self.migrate_data(
                        data_id, version_data, exclude_nodes={source.node_id}
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

        if request.method == "GET":
            return await self.handle_read(request)
        elif request.method in ["PUT", "POST"]:
            return await self.handle_write(request)
        elif request.method == "DELETE":
            return await self.handle_delete(request)

    async def handle_write(self, request) -> web.Response:
        """Handle write requests with parallel replication and load balancing"""
        try:
            data_id = request.match_info["data_id"]
            content = await request.read()
            checksum = hashlib.sha256(content).hexdigest()

            # Check if we should handle this write
            if not self.load_manager.can_handle_write():
                alternate_node = self.find_least_loaded_node()
                if alternate_node:
                    return await self.forward_request(request, alternate_node)

            # Create versioned data
            version_data = Volume(
                content=content,
                version=await self.consistency_manager.get_next_version(data_id),
                timestamp=datetime.now(),
                checksum=checksum,
            )

            # Get target nodes for replication
            target_nodes = self.replication_manager._select_replica_nodes(
                self.quorum_size - 1, {self.node_id}  # Exclude self
            )

            if len(target_nodes) < self.quorum_size - 1:
                return web.Response(
                    status=503,
                    text=f"Not enough nodes available for quorum (need {self.quorum_size})",
                )

            # Start parallel writes
            write_futures = []

            # Local write first to ensure durability
            try:
                local_path = os.path.join(self.data_dir, data_id)
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
                    return_when=asyncio.FIRST_N_COMPLETED(self.quorum_size - 1),
                )

                # Cancel pending operations if quorum achieved
                for task in pending:
                    task.cancel()

                # Check results
                successful_writes = sum(
                    1 for task in done if task.result().get("status") == "success"
                )

                if successful_writes < self.quorum_size - 1:
                    # Rollback if quorum not achieved
                    await self.rollback_write(data_id)
                    return web.Response(
                        status=503,
                        text=f"Write quorum not achieved ({successful_writes + 1}/{self.quorum_size})",
                    )

                # Update load metrics
                self.load_manager.record_write(len(content))

                return web.Response(
                    status=200,
                    text=f"Write successful, replicated to {successful_writes + 1} nodes",
                )

            except asyncio.TimeoutError:
                # Rollback on timeout
                await self.rollback_write(data_id)
                return web.Response(status=503, text="Write timeout waiting for quorum")

        except Exception as e:
            self.logger.error(f"Write failed: {str(e)}")
            return web.Response(status=500, text=str(e))

    async def rollback_write(self, data_id: str) -> None:
        """Rollback a failed write operation"""
        try:
            # Delete local copy
            local_path = os.path.join(self.data_dir, data_id)
            if os.path.exists(local_path):
                os.remove(local_path)

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
                rollback_futures, timeout=2.0, return_when=asyncio.ALL_COMPLETED
            )

        except Exception as e:
            self.logger.error(f"Rollback failed: {str(e)}")

    async def notify_rollback(self, node: NodeState, data_id: str) -> None:
        """Notify a node to rollback a write"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"http://{node.address}/storage/data/{data_id}",
                    headers={"X-Operation": "rollback"},
                ) as response:
                    if response.status != 200:
                        self.logger.warning(
                            f"Rollback notification failed for node {node.node_id}: "
                            f"HTTP {response.status}"
                        )
        except Exception as e:
            self.logger.error(
                f"Failed to notify rollback to node {node.node_id}: {str(e)}"
            )

    def find_least_loaded_node(self) -> Optional[NodeState]:
        """Find the node with the lowest load"""
        active_nodes = self.get_active_nodes()
        if not active_nodes:
            return None

        return min(
            active_nodes, key=lambda n: self.load_manager.get_node_load(n.node_id)
        )

    async def handle_read(self, request) -> web.Response:
        """Handle read requests with load balancing and consistency guarantees"""
        try:
            data_id = request.match_info["data_id"]
            consistency = request.query.get(
                "consistency", ConsistencyLevel.QUORUM.value
            )

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

    async def handle_strong_read(
        self, data_id: str, nodes: List[NodeState]
    ) -> Optional[bytes]:
        """Handle read with strong consistency - read from all nodes"""
        try:
            # Read from all nodes in parallel
            read_futures = []
            for node in nodes:
                future = self.read_from_node(node, data_id)
                read_futures.append(future)

            # Wait for all reads with timeout
            done, pending = await asyncio.wait(
                read_futures, timeout=5.0, return_when=asyncio.ALL_COMPLETED
            )

            # Cancel any pending reads
            for task in pending:
                task.cancel()

            # Collect results
            read_results = []
            for task in done:
                try:
                    result = task.result()
                    if result and result.get("status") == "success":
                        read_results.append(result)
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
            latest_result = max(
                read_results, key=lambda r: (r["version"], r["timestamp"])
            )
            return latest_result["content"]

        except Exception as e:
            self.logger.error(f"Strong read failed: {str(e)}")
            raise

    async def handle_quorum_read(
        self, data_id: str, nodes: List[NodeState]
    ) -> Optional[bytes]:
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
                return_when=asyncio.FIRST_N_COMPLETED(required_reads),
            )

            # Cancel pending reads
            for task in pending:
                task.cancel()

            # Collect successful results
            read_results = []
            for task in done:
                try:
                    result = task.result()
                    if result and result.get("status") == "success":
                        read_results.append(result)
                except Exception as e:
                    self.logger.error(f"Read task failed: {str(e)}")

            if len(read_results) < required_reads:
                raise ConsistencyError(
                    f"Failed to achieve read quorum ({len(read_results)}/{required_reads})"
                )

            # Return the most recent version from quorum
            latest_result = max(
                read_results, key=lambda r: (r["version"], r["timestamp"])
            )

            # Schedule async repair if versions differ
            if not all(r["version"] == latest_result["version"] for r in read_results):
                asyncio.create_task(self.repair_inconsistency(data_id, read_results))

            return latest_result["content"]

        except Exception as e:
            self.logger.error(f"Quorum read failed: {str(e)}")
            raise

    async def handle_eventual_read(
        self, data_id: str, nodes: List[NodeState]
    ) -> Optional[bytes]:
        """Handle read with eventual consistency - read from closest/least loaded node"""
        try:
            # Sort nodes by load and latency
            sorted_nodes = sorted(
                nodes,
                key=lambda n: (
                    self.load_manager.get_node_load(n.node_id),
                    n.network_latency,
                ),
            )

            # Try nodes in order until successful
            for node in sorted_nodes:
                try:
                    result = await self.read_from_node(node, data_id)
                    if result and result.get("status") == "success":
                        return result["content"]
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
                            "status": "success",
                            "content": await response.read(),
                            "version": int(response.headers.get("X-Version", "0")),
                            "timestamp": datetime.fromisoformat(
                                response.headers.get(
                                    "X-Timestamp", datetime.min.isoformat()
                                )
                            ),
                        }
                    else:
                        return {
                            "status": "error",
                            "error": f"HTTP {response.status}: {await response.text()}",
                        }

        except Exception as e:
            self.logger.error(f"Failed to read from node {node.node_id}: {str(e)}")
            return {"status": "error", "error": str(e)}

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
            return [node for node in active_nodes if node.node_id in nodes_in_map]

        except Exception as e:
            self.logger.error(f"Failed to find nodes with data: {str(e)}")
            return []

    async def write_local(self, path: str, content: bytes) -> None:
        """Write data locally with proper locking"""
        async with self.consistency_manager.get_write_lock(path):
            with open(path, "wb") as f:
                f.write(content)

    async def read_local(self, path: str) -> bytes:
        """Read data locally with proper locking"""
        async with self.consistency_manager.get_read_lock(path):
            with open(path, "rb") as f:
                return f.read()

    def get_active_nodes(self) -> List[NodeState]:
        """Get list of active nodes in the cluster"""
        now = datetime.now()
        return [
            node
            for node in self.cluster_nodes.values()
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
                    last_heartbeat=datetime.now(),
                    address="",
                    available_storage=0.0,
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
            node_id
            for node_id, state in self.cluster_nodes.items()
            if (now - state.last_heartbeat).total_seconds() > 30
        ]
        for node_id in inactive_nodes:
            del self.cluster_nodes[node_id]

    async def write_data(
        self, data_id: str, content: bytes, consistency_level: str = "strong"
    ) -> Dict[str, Any]:
        """Write data with parallel replication and load balancing"""
        try:
            # Generate version info
            version = self.consistency_manager.generate_version()
            checksum = hashlib.sha256(content).hexdigest()

            # Select target nodes based on load and health
            target_nodes = await self.select_write_targets(
                data_size=len(content), min_nodes=self.quorum_size
            )

            if len(target_nodes) < self.quorum_size:
                raise InsufficientNodesError(
                    f"Not enough healthy nodes available. Need {self.quorum_size}, got {len(target_nodes)}"
                )

            # Prepare write operation
            write_op = Volume(
                data_id=data_id,
                content=content,
                version=version,
                checksum=checksum,
                timestamp=datetime.now(),
            )

            # Execute parallel writes with load-aware routing
            results = await self.execute_parallel_write(write_op, target_nodes)

            # Validate results based on consistency level
            success = await self.validate_write_results(results, consistency_level)

            if not success:
                await self.rollback_write(write_op, target_nodes)
                raise WriteFailureError("Failed to achieve required write consistency")

            # Update metadata and return success
            await self.update_write_metadata(write_op, results)
            return {
                "status": "success",
                "version": version,
                "nodes": [node.node_id for node in target_nodes],
                "timestamp": write_op.timestamp.isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Write operation failed: {str(e)}")
            raise

    async def select_write_targets(
        self, data_size: int, min_nodes: int
    ) -> List[NodeState]:
        """Select optimal nodes for write operation based on load and health"""
        try:
            # Get all healthy nodes
            healthy_nodes = [
                node
                for node in self.get_active_nodes()
                if (
                    node.status == "active"
                    and node.available_storage >= data_size * 1.5  # Include headroom
                )
            ]

            if len(healthy_nodes) < min_nodes:
                raise InsufficientNodesError(
                    f"Not enough healthy nodes. Need {min_nodes}, got {len(healthy_nodes)}"
                )

            # Score nodes based on multiple factors
            scored_nodes = []
            for node in healthy_nodes:
                # Get real-time metrics
                metrics = await self.get_node_metrics(node)
                if not metrics:
                    continue

                # Calculate composite score
                score = self.calculate_node_write_score(node, metrics, data_size)
                scored_nodes.append((score, node))

            # Sort by score and select top nodes
            selected_nodes = [
                node
                for _, node in sorted(scored_nodes, key=lambda x: x[0], reverse=True)[
                    :min_nodes
                ]
            ]

            return selected_nodes

        except Exception as e:
            self.logger.error(f"Failed to select write targets: {str(e)}")
            raise

    def calculate_node_write_score(
        self, node: NodeState, metrics: Dict[str, float], data_size: int
    ) -> float:
        """Calculate node score for write operations"""
        try:
            # Base capacity score (0-1)
            storage_score = node.available_storage / node.total_storage

            # Load score (0-1, inverse of load)
            cpu_score = 1 - (metrics.get("cpu_usage", 0) / 100)
            memory_score = 1 - (metrics.get("memory_usage", 0) / 100)

            # Network health score (0-1)
            network_score = 1 - min(1.0, node.network_latency / 1000.0)

            # Recent error rate (0-1, inverse of error rate)
            error_score = 1 - min(1.0, metrics.get("error_rate", 0) * 20)

            # Write queue length score (0-1, inverse of queue length)
            queue_score = 1 - min(1.0, len(node.write_queue) / 100)

            # Weight factors
            weights = {
                "storage": 0.25,
                "cpu": 0.2,
                "memory": 0.15,
                "network": 0.2,
                "error": 0.1,
                "queue": 0.1,
            }

            # Calculate composite score
            score = (
                storage_score * weights["storage"]
                + cpu_score * weights["cpu"]
                + memory_score * weights["memory"]
                + network_score * weights["network"]
                + error_score * weights["error"]
                + queue_score * weights["queue"]
            )

            # Apply geographic penalty if different region
            if node.region != self.region:
                score *= 0.8  # 20% penalty for cross-region

            return score

        except Exception as e:
            self.logger.error(f"Failed to calculate node score: {e}")
            return 0.0

    async def execute_parallel_write(
        self, write_op: Volume, target_nodes: List[NodeState]
    ) -> List[Dict[str, Any]]:
        """Execute write operation in parallel across target nodes"""
        try:
            # Prepare write tasks
            write_tasks = []
            for node in target_nodes:
                task = self.write_to_node(node, write_op)
                write_tasks.append(task)

            # Execute writes in parallel with timeout
            results = []
            try:
                done, pending = await asyncio.wait(
                    write_tasks,
                    timeout=30.0,  # 30 second timeout
                    return_when=asyncio.ALL_COMPLETED,
                )

                # Cancel any pending tasks
                for task in pending:
                    task.cancel()

                # Collect results
                results = [task.result() for task in done]

            except asyncio.TimeoutError:
                self.logger.error("Parallel write operation timed out")
                # Cancel all tasks
                for task in write_tasks:
                    task.cancel()
                raise WriteTimeoutError("Write operation timed out")

            return results

        except Exception as e:
            self.logger.error(f"Failed to execute parallel write: {str(e)}")
            raise

    async def write_to_node(self, node: NodeState, write_op: Volume) -> Dict[str, Any]:
        """Write data to a single node with retries"""
        max_retries = 3
        retry_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                # Check node health before write
                if not await self.is_node_healthy(node):
                    raise NodeUnhealthyError(f"Node {node.node_id} is unhealthy")

                # Add to node's write queue
                node.write_queue.append(write_op)

                try:
                    # Perform write operation
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"http://{node.address}/write",
                            data={
                                "data_id": write_op.data_id,
                                "content": write_op.content.hex(),
                                "version": write_op.version,
                                "checksum": write_op.checksum,
                                "timestamp": write_op.timestamp.isoformat(),
                            },
                            timeout=10.0,
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                return {
                                    "node_id": node.node_id,
                                    "status": "success",
                                    "version": write_op.version,
                                    "timestamp": write_op.timestamp.isoformat(),
                                }
                            else:
                                raise WriteFailureError(
                                    f"Write to node {node.node_id} failed with status {response.status}"
                                )

                finally:
                    # Remove from write queue
                    node.write_queue.remove(write_op)

            except Exception as e:
                self.logger.warning(
                    f"Write attempt {attempt + 1} to node {node.node_id} failed: {str(e)}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    raise

        raise WriteFailureError(
            f"Write to node {node.node_id} failed after {max_retries} attempts"
        )

    async def validate_write_results(
        self, results: List[Dict[str, Any]], consistency_level: str
    ) -> bool:
        """Validate write results based on consistency level"""
        try:
            successful_writes = len(
                [r for r in results if r.get("status") == "success"]
            )

            if consistency_level == "strong":
                # All nodes must succeed
                return successful_writes == len(results)
            elif consistency_level == "quorum":
                # Majority must succeed
                return successful_writes >= (len(results) // 2 + 1)
            else:  # eventual consistency
                # At least one write must succeed
                return successful_writes >= 1

        except Exception as e:
            self.logger.error(f"Failed to validate write results: {str(e)}")
            return False

    async def rollback_write(self, write_op: Volume, nodes: List[NodeState]) -> None:
        """Rollback a failed write operation"""
        try:
            rollback_tasks = []
            for node in nodes:
                task = self.rollback_node_write(node, write_op)
                rollback_tasks.append(task)

            # Execute rollbacks in parallel
            await asyncio.gather(*rollback_tasks, return_exceptions=True)

        except Exception as e:
            self.logger.error(f"Failed to rollback write: {str(e)}")

    async def rollback_node_write(self, node: NodeState, write_op: Volume) -> None:
        """Rollback write on a single node"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{node.address}/rollback",
                    data={"data_id": write_op.data_id, "version": write_op.version},
                    timeout=5.0,
                ) as response:
                    if response.status != 200:
                        self.logger.error(
                            f"Failed to rollback write on node {node.node_id}"
                        )

        except Exception as e:
            self.logger.error(
                f"Error during write rollback on node {node.node_id}: {str(e)}"
            )

    async def update_write_metadata(
        self, write_op: Volume, results: List[Dict[str, Any]]
    ) -> None:
        """Update metadata after successful write"""
        try:
            successful_nodes = [
                r["node_id"] for r in results if r.get("status") == "success"
            ]

            # Update version map
            await self.consistency_manager.update_version_map(
                write_op.data_id, write_op.version, successful_nodes
            )

            # Update load statistics
            for node_id in successful_nodes:
                self.load_manager.record_write_operation(node_id, len(write_op.content))

        except Exception as e:
            self.logger.error(f"Failed to update write metadata: {str(e)}")

    async def is_node_healthy(self, node: NodeState) -> bool:
        """Check if a node is healthy and can handle requests"""
        try:
            # Check if node is active
            if node.status != "active":
                return False

            # Check last heartbeat
            heartbeat_age = datetime.now() - node.last_heartbeat
            if heartbeat_age.total_seconds() > self.heartbeat_timeout:
                return False

            # Check load and capacity
            if node.load >= 0.9:  # 90% load threshold
                return False

            if node.available_storage <= 0:
                return False

            # Check network latency
            if node.network_latency > self.max_latency:
                return False

            return True
        except Exception as e:
            self.logger.error(f"Error checking node health: {e}")
            return False

    async def deregister(self) -> None:
        """Deregister this node from the cluster."""
        try:
            self.logger.info(f"Deregistering node {self.node_id} from cluster")
            # Remove node from cluster nodes
            if self.node_id in self.cluster_nodes:
                del self.cluster_nodes[self.node_id]
            # Clean up any resources
            await self.replication_manager.stop()
            await self.consistency_manager.stop()
            self.load_manager.stop_monitoring()
        except Exception as e:
            self.logger.error(f"Error deregistering node: {str(e)}")

    async def write_file(self, path: str, content: Union[bytes, BinaryIO]) -> bool:
        """Write content to a file at the specified path."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            mode = 'wb' if isinstance(content, bytes) else 'wb+'
            with open(path, mode) as f:
                if isinstance(content, bytes):
                    f.write(content)
                else:
                    f.write(content.read())
            return True
        except Exception as e:
            self.logger.error(f"Failed to write file {path}: {str(e)}")
            return False

    async def read_file(self, path: str) -> Optional[bytes]:
        """Read content from a file at the specified path."""
        try:
            with open(path, 'rb') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Failed to read file {path}: {str(e)}")
            return None

    async def delete_file(self, path: str) -> bool:
        """Delete a file at the specified path."""
        try:
            os.remove(path)
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete file {path}: {str(e)}")
            return False

    async def list_files(self, path: str) -> List[str]:
        """List all files in the specified path."""
        try:
            return [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        except Exception as e:
            self.logger.error(f"Failed to list files in {path}: {str(e)}")
            return []

    async def exists(self, path: str) -> bool:
        """Check if a file exists at the specified path."""
        return os.path.exists(path)

    def add_volume(self, volume: Volume) -> bool:
        """Add a volume to the node."""
        try:
            if volume.volume_id not in [v.volume_id for v in self.node_state.volumes]:
                self.node_state.volumes.append(volume)
                volume_path = os.path.join(self.data_dir, volume.volume_id)
                os.makedirs(volume_path, exist_ok=True)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to add volume {volume.volume_id}: {str(e)}")
            return False

    def get_volume_temperature(self, volume: Volume) -> DataTemperature:
        """Get the temperature classification of a volume."""
        try:
            now = datetime.now()
            days_since_access = (now - volume.last_accessed_at).days
            
            return DataTemperature(
                access_frequency=len(volume.locations),
                days_since_last_access=days_since_access,
                size_bytes=volume.size_bytes,
                current_tier=self._determine_tier(days_since_access)
            )
        except Exception as e:
            self.logger.error(f"Failed to get volume temperature: {str(e)}")
            return None

    def _determine_tier(self, days_since_access: int) -> TierType:
        """Determine appropriate storage tier based on access patterns."""
        if days_since_access < 7:
            return TierType.PERFORMANCE
        elif days_since_access < 30:
            return TierType.CAPACITY
        elif days_since_access < 90:
            return TierType.COLD
        else:
            return TierType.ARCHIVE

    async def apply_tiering_policy(self, volume: Volume) -> bool:
        """Apply tiering policy to a volume."""
        try:
            if not self.tiering_policy or not self.tiering_policy.enabled:
                return True

            temp = self.get_volume_temperature(volume)
            if not temp:
                return False

            # Check if volume should be moved to cold storage
            if (temp.days_since_last_access >= self.tiering_policy.cold_tier_after_days and
                temp.size_bytes >= self.tiering_policy.min_object_size):
                await self._move_to_cold_storage(volume)
                return True

            # Check if volume should be archived
            if temp.days_since_last_access >= self.tiering_policy.archive_tier_after_days:
                await self._move_to_archive(volume)
                return True

            return True

        except Exception as e:
            self.logger.error(f"Failed to apply tiering policy: {str(e)}")
            return False

    async def _move_to_cold_storage(self, volume: Volume) -> bool:
        """Move volume to cold storage tier."""
        try:
            # Implement cold storage movement logic
            volume.tiering_policy = self.tiering_policy
            return True
        except Exception as e:
            self.logger.error(f"Failed to move to cold storage: {str(e)}")
            return False

    async def _move_to_archive(self, volume: Volume) -> bool:
        """Move volume to archive storage tier."""
        try:
            # Implement archive movement logic
            volume.tiering_policy = self.tiering_policy
            return True
        except Exception as e:
            self.logger.error(f"Failed to move to archive: {str(e)}")
            return False

    def remove_volume(self, volume_id: str) -> bool:
        """Remove a volume from the node."""
        try:
            self.node_state.volumes = [v for v in self.node_state.volumes if v.volume_id != volume_id]
            volume_path = os.path.join(self.data_dir, volume_id)
            if os.path.exists(volume_path):
                os.rmdir(volume_path)
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove volume {volume_id}: {str(e)}")
            return False

    def get_volume(self, volume_id: str) -> Optional[Volume]:
        """Get volume by ID."""
        for volume in self.node_state.volumes:
            if volume.volume_id == volume_id:
                return volume
        return None

    def list_volumes(self) -> List[Volume]:
        """List all volumes on the node."""
        return self.node_state.volumes.copy()

    def get_volume_path(self, volume_id: str) -> Optional[str]:
        """Get the path for a volume."""
        if self.get_volume(volume_id):
            return os.path.join(self.data_dir, volume_id)
        return None

    async def replicate_data(self, data: bytes, consistency_level: ConsistencyLevel) -> WriteResult:
        """Replicate data across nodes based on consistency level and replication policy."""
        try:
            block_id = hashlib.sha256(data).hexdigest()
            
            if not self.replication_policy.enabled:
                # Write locally only if replication is disabled
                success = await self.write_file(os.path.join(self.data_dir, block_id), data)
                return WriteResult(success=success, block_id=block_id)
            
            if consistency_level == ConsistencyLevel.EVENTUAL:
                # Write locally and trigger async replication
                success = await self.write_file(os.path.join(self.data_dir, block_id), data)
                asyncio.create_task(self._async_replicate(block_id, data))
                return WriteResult(success=success, block_id=block_id)
                
            elif consistency_level == ConsistencyLevel.STRONG:
                # Write to all replicas synchronously
                replicas = await self._get_replica_nodes()
                if len(replicas) < self.replication_policy.min_copies:
                    return WriteResult(success=False, block_id="", error="Not enough replica nodes available")
                
                results = await asyncio.gather(
                    *[self._write_to_replica(replica, block_id, data) for replica in replicas],
                    return_exceptions=True
                )
                
                success = all(isinstance(r, bool) and r for r in results)
                if not success:
                    return WriteResult(success=False, block_id="", error="Failed to write to all replicas")
                
                return WriteResult(success=True, block_id=block_id)
                
            elif consistency_level == ConsistencyLevel.QUORUM:
                # Write to quorum of replicas
                replicas = await self._get_replica_nodes()
                required_copies = max(self.replication_policy.min_copies, self.quorum_size)
                if len(replicas) < required_copies:
                    return WriteResult(success=False, block_id="", error="Not enough replica nodes for quorum")
                
                results = await asyncio.gather(
                    *[self._write_to_replica(replica, block_id, data) for replica in replicas[:required_copies]],
                    return_exceptions=True
                )
                
                success_count = sum(1 for r in results if isinstance(r, bool) and r)
                if success_count < required_copies:
                    return WriteResult(success=False, block_id="", error="Failed to achieve quorum")
                
                return WriteResult(success=True, block_id=block_id)
            
            else:
                return WriteResult(success=False, block_id="", error=f"Unknown consistency level: {consistency_level}")
                
        except Exception as e:
            return WriteResult(success=False, block_id="", error=str(e))

    async def _async_replicate(self, block_id: str, data: bytes) -> None:
        """Asynchronously replicate data to other nodes."""
        try:
            replicas = await self._get_replica_nodes()
            required_copies = min(len(replicas), self.replication_policy.max_copies)
            
            if self.replication_policy.bandwidth_limit_mbps:
                # Implement bandwidth limiting logic
                pass
                
            await asyncio.gather(
                *[self._write_to_replica(replica, block_id, data) for replica in replicas[:required_copies]]
            )
        except Exception as e:
            self.logger.error(f"Async replication failed: {str(e)}")

    async def verify_data_protection(self, block_id: str) -> bool:
        """Verify data protection by checking replicas."""
        try:
            if not self.replication_policy.enabled:
                return os.path.exists(os.path.join(self.data_dir, block_id))
                
            replicas = await self._get_replica_nodes()
            results = await asyncio.gather(
                *[self._verify_replica_data(replica, block_id) for replica in replicas],
                return_exceptions=True
            )
            
            success_count = sum(1 for r in results if isinstance(r, bool) and r)
            return success_count >= self.replication_policy.min_copies
            
        except Exception as e:
            self.logger.error(f"Failed to verify data protection: {str(e)}")
            return False

    async def _write_to_replica(self, replica: Any, block_id: str, data: bytes) -> bool:
        """Write data to a replica node."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    f"http://{replica.address}/write/{block_id}",
                    data=data,
                    timeout=self.write_timeout
                ) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.error(f"Failed to write to replica {replica.node_id}: {str(e)}")
            return False

    async def _verify_replica_data(self, replica: Any, block_id: str) -> bool:
        """Verify data exists on a replica node."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{replica.address}/verify/{block_id}",
                    timeout=self.write_timeout
                ) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.error(f"Failed to verify replica {replica.node_id}: {str(e)}")
            return False


class WriteTimeoutError(Exception):
    """Raised when a write operation times out"""

    pass


class ConsistencyError(Exception):
    """Raised when consistency requirements cannot be met"""

    pass


class InsufficientNodesError(Exception):
    """Raised when there are not enough healthy nodes available"""

    pass


class WriteFailureError(Exception):
    """Raised when a write operation fails to achieve required consistency"""

    pass


class NodeUnhealthyError(Exception):
    """Raised when a node is found to be unhealthy"""

    pass


@dataclass
class Volume:
    """Volume metadata"""

    data_id: str
    content: bytes
    version: int
    checksum: str
    timestamp: datetime


class EdgeNodeState(NodeState):
    """Extended node state for edge computing"""

    def __init__(self, node_id: str, address: str):
        super().__init__(node_id, address)
        self.edge_capabilities = {}  # Specific edge node capabilities
        self.local_cache = {}  # Local data cache
        self.bandwidth_limit = 0  # Available bandwidth to central nodes
        self.processing_power = 0  # Local processing capability
        self.device_type = ""  # Edge device type (mobile, IoT, etc)
        self.battery_level = None  # Battery level for mobile devices
        self.offline_mode = False  # Whether node is operating offline


class EdgeAwareNode(ActiveNode):
    """Edge-computing aware node implementation"""

    def __init__(self, node_id: str, data_dir: str, quorum_size: int):
        super().__init__(node_id, data_dir, quorum_size)
        self.edge_nodes: Dict[str, EdgeNodeState] = {}
        self.cache_manager = EdgeCacheManager()
        self.edge_scheduler = EdgeTaskScheduler()

    async def handle_edge_request(self, request: web.Request) -> web.Response:
        """Handle requests from edge devices with context awareness"""
        try:
            # Get edge context
            edge_context = self.get_edge_context(request)

            # Determine optimal processing location
            if self.should_process_at_edge(edge_context):
                return await self.process_at_edge(request, edge_context)
            else:
                return await self.process_at_cloud(request, edge_context)

        except Exception as e:
            self.logger.error(f"Edge request handling failed: {str(e)}")
            raise

    def get_edge_context(self, request: web.Request) -> Dict[str, Any]:
        """Extract edge computing context from request"""
        return {
            "device_type": request.headers.get("X-Edge-Device-Type", "unknown"),
            "battery_level": float(request.headers.get("X-Battery-Level", 100)),
            "bandwidth": float(request.headers.get("X-Available-Bandwidth", 1000)),
            "latency_requirement": float(
                request.headers.get("X-Latency-Requirement", 1000)
            ),
            "processing_power": float(request.headers.get("X-Processing-Power", 1.0)),
            "location": request.headers.get("X-Device-Location", "unknown"),
        }

    def should_process_at_edge(self, context: Dict[str, Any]) -> bool:
        """Determine if request should be processed at edge"""
        # Consider multiple factors for edge processing decision
        score = 0

        # Latency requirements
        if context["latency_requirement"] < 100:  # Need fast response
            score += 3

        # Bandwidth constraints
        if context["bandwidth"] < 500:  # Limited bandwidth
            score += 2

        # Battery considerations
        if context["battery_level"] < 20:  # Low battery
            score -= 1

        # Processing requirements vs capability
        if context["processing_power"] > 0.7:  # High local processing power
            score += 2

        return score > 3  # Threshold for edge processing

    async def process_at_edge(
        self, request: web.Request, context: Dict[str, Any]
    ) -> web.Response:
        """Process request at edge node"""
        try:
            # Check local cache first
            cache_result = await self.cache_manager.get_cached_result(
                request.path, context
            )
            if cache_result:
                return web.json_response(cache_result)

            # Schedule task for edge processing
            result = await self.edge_scheduler.schedule_edge_task(
                request, context, self.edge_nodes
            )

            # Cache result if appropriate
            if self.should_cache_result(result, context):
                await self.cache_manager.cache_result(request.path, result, context)

            return web.json_response(result)

        except Exception as e:
            self.logger.error(f"Edge processing failed: {str(e)}")
            # Fallback to cloud processing
            return await self.process_at_cloud(request, context)

    async def process_at_cloud(
        self, request: web.Request, context: Dict[str, Any]
    ) -> web.Response:
        """Process request in cloud with edge awareness"""
        try:
            # Optimize data transfer based on edge context
            optimized_request = await self.optimize_for_edge(request, context)

            # Process in cloud
            result = await super().handle_request(optimized_request)

            # Optimize response for edge device
            optimized_response = await self.optimize_response_for_edge(result, context)

            return optimized_response

        except Exception as e:
            self.logger.error(f"Cloud processing failed: {str(e)}")
            raise

    async def optimize_for_edge(
        self, request: web.Request, context: Dict[str, Any]
    ) -> web.Request:
        """Optimize request for edge device constraints"""
        # Implement data reduction techniques based on context
        if context["bandwidth"] < 500:  # Low bandwidth
            request = await self.compress_request(request)

        if context["battery_level"] < 30:  # Low battery
            request = await self.optimize_power_usage(request)

        return request

    async def optimize_response_for_edge(
        self, response: web.Response, context: Dict[str, Any]
    ) -> web.Response:
        """Optimize response for edge device"""
        try:
            if context["bandwidth"] < 500:  # Low bandwidth
                response = await self.compress_response(response)

            if context["device_type"] == "mobile":
                response = await self.optimize_for_mobile(response)

            return response

        except Exception as e:
            self.logger.error(f"Response optimization failed: {str(e)}")
            return response

    async def register_edge_node(self, node: EdgeNodeState) -> None:
        """Register a new edge node"""
        try:
            # Validate edge node capabilities
            if not self.validate_edge_node(node):
                raise ValueError(f"Invalid edge node configuration: {node.node_id}")

            # Register node
            self.edge_nodes[node.node_id] = node

            # Initialize edge node cache
            await self.cache_manager.initialize_cache(node)

            # Start monitoring edge node
            asyncio.create_task(self.monitor_edge_node(node))

            self.logger.info(f"Edge node registered: {node.node_id}")

        except Exception as e:
            self.logger.error(f"Edge node registration failed: {str(e)}")
            raise

    async def monitor_edge_node(self, node: EdgeNodeState) -> None:
        """Monitor edge node health and performance"""
        while True:
            try:
                # Check node health
                metrics = await self.get_edge_node_metrics(node)

                # Update node state
                node.battery_level = metrics.get("battery_level")
                node.bandwidth_limit = metrics.get("bandwidth")
                node.processing_power = metrics.get("processing_power")

                # Check for offline mode
                if metrics.get("connectivity") == "offline":
                    await self.handle_edge_node_offline(node)

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Edge node monitoring failed: {str(e)}")
                await asyncio.sleep(5)  # Brief pause on error

    async def handle_edge_node_offline(self, node: EdgeNodeState) -> None:
        """Handle edge node going offline"""
        try:
            # Mark node as offline
            node.offline_mode = True

            # Ensure critical data is cached
            await self.cache_manager.ensure_critical_data_cached(node)

            # Redirect traffic from this node
            await self.redirect_edge_traffic(node)

            # Notify other nodes
            await self.notify_edge_node_offline(node)

        except Exception as e:
            self.logger.error(f"Failed to handle offline edge node: {str(e)}")


class EdgeCacheManager:
    """Manage caching for edge nodes"""

    def __init__(self):
        self.cache = {}
        self.cache_policy = {}

    async def get_cached_result(
        self, key: str, context: Dict[str, Any]
    ) -> Optional[Any]:
        """Get cached result if available and valid"""
        if key in self.cache:
            entry = self.cache[key]
            if self.is_cache_valid(entry, context):
                return entry["data"]
        return None

    async def cache_result(self, key: str, data: Any, context: Dict[str, Any]) -> None:
        """Cache result with context-aware policies"""
        self.cache[key] = {
            "data": data,
            "timestamp": datetime.now(),
            "context": context,
        }
