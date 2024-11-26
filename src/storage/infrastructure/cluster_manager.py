"""Storage cluster management for distributed file system."""

from typing import Dict, List, Optional
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
        self.namespace = namespace

        # Use defaults for development environment
        self.node_id = os.environ.get("NODE_ID", f"dev-node-{uuid.uuid4()}")
        self.pod_ip = os.environ.get("POD_IP", "127.0.0.1")

        self.nodes: Dict[str, StorageNodeInfo] = {}
        self.leader = False
        self.current_leader = None
        self._lock = Lock()
        self.start_time = None
        self._running = False
        self._heartbeat_task = None

        # Initialize kubernetes client
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except:
                logger.warning("Running without Kubernetes configuration")

        self.k8s_api = client.CoreV1Api()
        self.custom_api = client.CustomObjectsApi()
        self.coordination_api = client.CoordinationV1Api()

    def register_node(self, node_id: str) -> bool:
        """Register a new node with the cluster.

        Args:
            node_id: Unique identifier for the node

        Returns:
            bool: True if registration successful, False otherwise
        """
        try:
            node_info = StorageNodeInfo(
                node_id=node_id,
                hostname=os.environ.get("HOSTNAME", "localhost"),
                pod_ip=self.pod_ip,
                capacity_bytes=0,  # Will be updated later
                used_bytes=0,  # Will be updated later
                status="STARTING",
                last_heartbeat=time.time(),
                pods=[],
                zone=os.environ.get("ZONE", "default"),
            )

            with self._lock:
                self.nodes[node_id] = node_info
                logger.info(f"Registered node {node_id} with cluster")
            return True

        except Exception as e:
            logger.error(f"Failed to register node {node_id}: {str(e)}")
            return False

    async def start(self):
        """Start the cluster manager and attempt to become leader"""
        try:
            self.start_time = time.time()
            self._running = True
            logging.info(f"Starting cluster manager for node {self.node_id}")
            self._register_node()

            # Start leader election in development mode without k8s
            if not hasattr(self, "k8s_api") or self.k8s_api is None:
                logger.info("Running in development mode without Kubernetes")
                self.leader = True
                self.current_leader = self.node_id
            else:
                await self._start_leader_election()

            self._heartbeat_task = asyncio.create_task(self._start_heartbeat())
            logger.info(f"Cluster manager started successfully for node {self.node_id}")
        except Exception as e:
            self._running = False
            logger.error(f"Failed to start cluster manager: {str(e)}")
            raise

    async def stop(self):
        """Stop the cluster manager and cleanup resources."""
        logger.info(f"Stopping cluster manager for node {self.node_id}")
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Remove node from cluster
        with self._lock:
            if self.node_id in self.nodes:
                del self.nodes[self.node_id]
                logger.info(f"Removed node {self.node_id} from cluster")

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

    def _register_node(self):
        """Register this node with the cluster"""
        node_info = StorageNodeInfo(
            node_id=self.node_id,
            hostname=self._get_hostname(),
            pod_ip=self.pod_ip,
            capacity_bytes=self._get_capacity(),
            used_bytes=0,
            status="READY",
            last_heartbeat=time.time(),
            pods=[],
            zone=self._get_zone(),
        )

        self._update_node_status(node_info)

    async def _start_leader_election(self):
        """Implement leader election using K8s lease objects"""
        lease_name = "storage-cluster-leader"

        try:
            logging.info("Starting leader election")
            # Try to acquire the lease
            lease = client.V1Lease(
                metadata=client.V1ObjectMeta(name=lease_name),
                spec=client.V1LeaseSpec(
                    holder_identity=self.node_id, lease_duration_seconds=15
                ),
            )

            logging.info(
                f"Attempting to create lease with holder_identity={self.node_id}"
            )
            self.coordination_api.create_namespaced_lease(
                namespace=self.namespace, body=lease
            )
            self.leader = True
            logging.info("Successfully became leader")
            # Start lease renewal
            asyncio.create_task(self._renew_lease(lease_name))
        except kubernetes.client.rest.ApiException as e:
            if e.status == 409:  # Conflict, lease exists
                self.leader = False
                # Get current leader
                try:
                    logging.info("Lease exists, getting current leader")
                    current_lease = self.coordination_api.read_namespaced_lease(
                        name=lease_name, namespace=self.namespace
                    )
                    self.current_leader = current_lease.spec.holder_identity
                    logging.info(f"Current leader is {self.current_leader}")
                except Exception as e:
                    logging.error(f"Failed to get current leader: {str(e)}")
                    self.current_leader = None
            else:
                logging.error(f"Failed to create/get lease: {str(e)}")
                raise

    async def _renew_lease(self, lease_name: str):
        """Periodically renew the lease if we are the leader"""
        while True:
            if not self.leader:
                break

            try:
                # Get current lease
                lease = self.coordination_api.read_namespaced_lease(
                    name=lease_name, namespace=self.namespace
                )

                # Update lease timestamp
                lease.spec.renew_time = client.V1MicroTime(timestamp=time.time())

                # Update the lease
                self.coordination_api.replace_namespaced_lease(
                    name=lease_name, namespace=self.namespace, body=lease
                )
            except Exception as e:
                logging.error(f"Failed to renew lease: {str(e)}")
                self.leader = False
                break

            await asyncio.sleep(5)  # Renew every 5 seconds

    async def _start_heartbeat(self):
        """Start sending heartbeats to the cluster"""
        while True:
            with self._lock:
                current_time = time.time()
                # Update own heartbeat
                if self.node_id in self.nodes:
                    self.nodes[self.node_id].last_heartbeat = current_time

                # Check other nodes' heartbeats
                dead_nodes = []
                for node_id, node in self.nodes.items():
                    if current_time - node.last_heartbeat > 30:  # 30 seconds timeout
                        dead_nodes.append(node_id)

                # Remove dead nodes
                for node_id in dead_nodes:
                    self._handle_node_failure(node_id)

            await asyncio.sleep(5)

    def _handle_node_failure(self, node_id: str):
        """Handle failed node and redistribute its data"""
        with self._lock:
            if node_id in self.nodes:
                failed_node = self.nodes[node_id]
                del self.nodes[node_id]

                if self.leader:
                    self._redistribute_data(failed_node)

    def _redistribute_data(self, failed_node: StorageNodeInfo):
        """Redistribute data from failed node to healthy nodes"""
        # Get list of healthy nodes
        healthy_nodes = [
            node
            for node in self.nodes.values()
            if node.status == "READY" and node.node_id != failed_node.node_id
        ]

        if not healthy_nodes:
            return

        # Get data locations from failed node
        data_locations = self._get_node_data_locations(failed_node.node_id)

        # Redistribute each piece of data
        for data_id, data_info in data_locations.items():
            target_node = self._select_target_node(healthy_nodes)
            self._replicate_data(data_id, data_info, target_node)

    def _select_target_node(
        self, healthy_nodes: List[StorageNodeInfo]
    ) -> StorageNodeInfo:
        """Select the best node for data placement based on capacity and load"""
        return min(
            healthy_nodes,
            key=lambda n: (
                n.used_bytes / n.capacity_bytes
                if n.capacity_bytes > 0
                else float("inf")
            ),
        )

    def _replicate_data(
        self, data_id: str, data_info: dict, target_node: StorageNodeInfo
    ):
        """Replicate data to target node"""
        # Implementation would involve:
        # 1. Reading data from source/backup
        # 2. Writing to target node
        # 3. Updating metadata
        pass

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
                1 for node in nodes.values() if (time.time() - node.last_heartbeat) < 15
            )

            # Get current leader
            try:
                lease = await asyncio.to_thread(
                    self.coordination_api.read_namespaced_lease,
                    name="storage-cluster-leader",
                    namespace=self.namespace,
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

    def _get_hostname(self) -> str:
        """Get the hostname of the current node"""
        try:
            pod = self.k8s_api.read_namespaced_pod(self.node_id, self.namespace)
            return pod.spec.node_name
        except:
            # Return local hostname in development mode
            import socket

            return socket.gethostname()

    def _get_capacity(self) -> int:
        """Get the storage capacity of the current node"""
        try:
            if self.k8s_api:
                # Get node capacity from Kubernetes
                node = self.k8s_api.read_node(self._get_hostname())
                return int(node.status.capacity["ephemeral-storage"])
            else:
                # Fallback to local disk space
                disk = psutil.disk_usage("/")
                return disk.total
        except Exception as e:
            logger.error(f"Failed to get node capacity: {str(e)}")
            return 0

    def _get_zone(self) -> str:
        """Get the zone/region of the current node"""
        try:
            pod = self.k8s_api.read_namespaced_pod(self.node_id, self.namespace)
            node = self.k8s_api.read_node(pod.spec.node_name)
            return node.metadata.labels.get("topology.kubernetes.io/zone", "unknown")
        except:
            # Return default zone in development mode
            return "local-dev"

    def _update_node_status(self, node_info: StorageNodeInfo):
        """Update node status in the cluster"""
        with self._lock:
            self.nodes[node_info.node_id] = node_info

            # Update K8s custom resource
            node_status = {
                "apiVersion": "storage.dfs.io/v1",
                "kind": "StorageNodeStatus",
                "metadata": {"name": node_info.node_id, "namespace": self.namespace},
                "spec": {
                    "nodeId": node_info.node_id,
                    "hostname": node_info.hostname,
                    "podIp": node_info.pod_ip,
                    "capacity": node_info.capacity_bytes,
                    "used": node_info.used_bytes,
                    "status": node_info.status,
                    "lastHeartbeat": datetime.fromtimestamp(
                        node_info.last_heartbeat
                    ).isoformat(),
                    "zone": node_info.zone,
                },
            }

            try:
                self.custom_api.create_namespaced_custom_object(
                    group="storage.dfs.io",
                    version="v1",
                    namespace=self.namespace,
                    plural="storagenodestatuses",
                    body=node_status,
                )
            except kubernetes.client.rest.ApiException as e:
                if e.status == 409:  # Already exists, update instead
                    self.custom_api.patch_namespaced_custom_object(
                        group="storage.dfs.io",
                        version="v1",
                        namespace=self.namespace,
                        plural="storagenodestatuses",
                        name=node_info.node_id,
                        body=node_status,
                    )

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
