"""Storage cluster management for distributed file system."""

from typing import Dict, List, Optional, Tuple
import uuid
import time
import os
import asyncio
from dataclasses import dataclass
from threading import Lock
import kubernetes
from kubernetes import client, config
import json
from datetime import datetime
import logging
import psutil

logger = logging.getLogger(__name__)


class ClusterManagerError(Exception):
    """Base class for cluster manager errors."""
    pass


class LeaderElectionError(ClusterManagerError):
    """Raised when leader election fails."""
    pass


class NodeRegistrationError(ClusterManagerError):
    """Raised when node registration fails."""
    pass


class NodeNotFoundError(ClusterManagerError):
    """Raised when a requested node is not found."""
    pass


@dataclass
class StorageNodeInfo:
    node_id: str
    hostname: str
    pod_ip: str
    capacity_bytes: int
    used_bytes: int
    status: str
    last_heartbeat: float
    pods: List[str]
    zone: str


class StorageClusterManager:
    def __init__(self, namespace: str = "default"):
        """Initialize the cluster manager."""
        self.namespace = namespace
        self.node_id = os.environ.get("NODE_ID", "test-node-1")
        if not self.node_id:
            self.node_id = f"dev-node-{uuid.uuid4()}"
        
        self.pod_ip = os.environ.get("POD_IP", "127.0.0.1")
        self.hostname = os.environ.get("HOSTNAME", "localhost")
        
        self.nodes: Dict[str, StorageNodeInfo] = {}
        self.leader = False
        self.current_leader = None
        self._lock = Lock()
        self.start_time = datetime.now().timestamp()
        self._running = False
        self._heartbeat_task = None
        
        # Initialize kubernetes client
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        
        self._k8s_api = client.CoordinationV1Api()
        self._custom_api = client.CustomObjectsApi()

    async def _register_node(self, node_info: StorageNodeInfo) -> bool:
        """Register a node with the cluster."""
        try:
            node_status = {
                "apiVersion": "storage.dfs.io/v1",
                "kind": "StorageNodeStatus",
                "metadata": {
                    "name": node_info.node_id,
                    "namespace": self.namespace
                },
                "spec": {
                    "nodeId": node_info.node_id,
                    "hostname": node_info.hostname,
                    "podIp": node_info.pod_ip,
                    "capacityBytes": node_info.capacity_bytes,
                    "usedBytes": node_info.used_bytes,
                    "status": node_info.status,
                    "lastHeartbeat": node_info.last_heartbeat,
                    "pods": node_info.pods,
                    "zone": node_info.zone
                }
            }
            
            await self._custom_api.create_namespaced_custom_object(
                group="storage.dfs.io",
                version="v1",
                namespace=self.namespace,
                plural="storagenodestatuses",
                body=node_status
            )
            
            with self._lock:
                self.nodes[node_info.node_id] = node_info
            return True
            
        except kubernetes.client.rest.ApiException as e:
            if e.status == 409:  # Already exists
                raise NodeRegistrationError(f"Node {node_info.node_id} already registered")
            else:
                raise NodeRegistrationError(f"Failed to register node: {str(e)}")

    async def register_node(self, node_info: StorageNodeInfo) -> bool:
        """Register a node with the cluster.
        
        Args:
            node_info (StorageNodeInfo): Information about the node to register
            
        Returns:
            bool: True if registration successful, False otherwise
            
        Raises:
            NodeRegistrationError: If registration fails
        """
        return await self._register_node(node_info)

    async def _acquire_leadership(self) -> bool:
        """Attempt to acquire cluster leadership."""
        lease_name = "storage-cluster-leader"
        lease_duration = 15  # seconds
        
        try:
            # Create lease object
            lease = client.V1Lease(
                metadata=client.V1ObjectMeta(name=lease_name),
                spec=client.V1LeaseSpec(
                    holder_identity=self.node_id,
                    lease_duration_seconds=lease_duration,
                    acquire_time=datetime.now().isoformat() + "Z",
                    renew_time=datetime.now().isoformat() + "Z"
                )
            )
            
            # Try to create the lease
            await self._k8s_api.create_namespaced_lease(
                namespace=self.namespace,
                body=lease
            )
            
            self.leader = True
            return True
            
        except kubernetes.client.rest.ApiException as e:
            if e.status == 409:  # Lease exists
                try:
                    # Get current lease
                    current_lease = await self._k8s_api.read_namespaced_lease(
                        name=lease_name,
                        namespace=self.namespace
                    )
                    self.current_leader = current_lease.spec.holder_identity
                except Exception as e:
                    logger.error(f"Failed to get current leader: {str(e)}")
                    self.current_leader = None
            
            raise LeaderElectionError(f"Failed to acquire leadership: {str(e)}")

    async def _check_node_health(self):
        """Check health of all nodes and remove unhealthy ones."""
        current_time = datetime.now().timestamp()
        unhealthy_nodes = []
        
        with self._lock:
            for node_id, node_info in self.nodes.items():
                # Node is considered unhealthy if no heartbeat for 5 minutes
                if current_time - node_info.last_heartbeat > 300:  # 5 minutes
                    unhealthy_nodes.append(node_id)
            
            # Remove unhealthy nodes
            for node_id in unhealthy_nodes:
                del self.nodes[node_id]

    def _get_target_nodes(self, count: int) -> List[StorageNodeInfo]:
        """Get target nodes for data placement based on usage."""
        with self._lock:
            # Sort nodes by used space
            sorted_nodes = sorted(
                self.nodes.values(),
                key=lambda x: x.used_bytes / x.capacity_bytes if x.capacity_bytes > 0 else float('inf')
            )
            return sorted_nodes[:count]

    async def shutdown(self):
        """Gracefully shutdown the cluster manager."""
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.leader:
            try:
                await self._k8s_api.delete_namespaced_lease(
                    name="storage-cluster-leader",
                    namespace=self.namespace
                )
            except Exception as e:
                logger.error(f"Error releasing leadership: {str(e)}")
        
        self.leader = False
        self.nodes.clear()

    async def start(self):
        """Start the cluster manager and attempt to become leader"""
        try:
            self._running = True
            logging.info(f"Starting cluster manager for node {self.node_id}")
            
            # Register node
            node_info = StorageNodeInfo(
                node_id=self.node_id,
                hostname=self.hostname,
                pod_ip=self.pod_ip,
                capacity_bytes=0,  # Will be updated later
                used_bytes=0,  # Will be updated later
                status="STARTING",
                last_heartbeat=datetime.now().timestamp(),
                pods=[],
                zone=os.environ.get("ZONE", "default"),
            )
            await self._register_node(node_info)
            
            # Start leader election
            await self._acquire_leadership()
            
            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._start_heartbeat())
            logger.info(f"Cluster manager started successfully for node {self.node_id}")
        except Exception as e:
            self._running = False
            logger.error(f"Failed to start cluster manager: {str(e)}")
            raise

    async def stop(self):
        """Stop the cluster manager and cleanup resources."""
        logger.info(f"Stopping cluster manager for node {self.node_id}")
        await self.shutdown()

    async def _start_heartbeat(self):
        """Start sending heartbeats to the cluster"""
        while True:
            if not self._running:
                break
            
            # Update own heartbeat
            node_info = self.nodes[self.node_id]
            node_info.last_heartbeat = datetime.now().timestamp()
            await self._register_node(node_info)
            
            # Check other nodes' heartbeats
            await self._check_node_health()
            
            await asyncio.sleep(5)

    def deregister_node(self, node_id: str) -> None:
        """Deregister a node from the cluster."""
        with self._lock:
            if node_id in self.nodes:
                logger.info(f"Removing node {node_id} from cluster")
                del self.nodes[node_id]
                # If this was the leader, trigger re-election
                if self.current_leader == node_id:
                    self.current_leader = None
                    self.leader = False
            else:
                logger.warning(f"Attempted to deregister unknown node {node_id}")

    def get_cluster_status(self) -> Dict:
        """Get current status of the storage cluster"""
        with self._lock:
            return {
                "nodes": len(self.nodes),
                "healthy_nodes": sum(
                    1 for n in self.nodes.values() if n.status == "READY"
                ),
                "leader_node": (
                    self.node_id
                    if self.leader
                    else getattr(self, "current_leader", None)
                ),
            }

    async def get_cluster_status_async(self) -> dict:
        """Get cluster status asynchronously with timeout protection"""
        try:
            # Get current nodes
            nodes = await asyncio.to_thread(self._get_current_nodes)

            # Count healthy nodes (nodes with recent heartbeat)
            healthy_nodes = sum(
                1 for node in nodes.values() if (datetime.now().timestamp() - node.last_heartbeat) < 15
            )

            # Get current leader
            try:
                lease = await self._k8s_api.read_namespaced_lease(
                    name="storage-cluster-leader",
                    namespace=self.namespace
                )
                leader_node = lease.spec.holder_identity
            except kubernetes.client.rest.ApiException as e:
                if e.status == 404:
                    leader_node = None
                else:
                    raise

            return {
                "total_nodes": len(nodes),
                "healthy_nodes": healthy_nodes,
                "leader_node": leader_node,
                "current_node": self.node_id,
                "is_leader": self.leader,
            }
        except Exception as e:
            logging.error(f"Error getting cluster status: {str(e)}")
            return {
                "error": str(e),
                "total_nodes": 0,
                "healthy_nodes": 0,
                "leader_node": None,
                "current_node": self.node_id,
                "is_leader": self.leader,
            }

    def _get_current_nodes(self) -> Dict[str, StorageNodeInfo]:
        """Get current nodes in the cluster"""
        with self._lock:
            return self.nodes.copy()

    def is_healthy(self) -> bool:
        """Check if the cluster manager is healthy.

        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # Check if we have any registered nodes
            if not self.nodes:
                return False

            # Check if we have a leader
            if not self.current_leader:
                return False

            # Check node health
            healthy_nodes = 0
            for node in self.nodes.values():
                if node.status == "healthy":
                    healthy_nodes += 1

            # Consider healthy if at least one node is healthy
            return healthy_nodes > 0
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
