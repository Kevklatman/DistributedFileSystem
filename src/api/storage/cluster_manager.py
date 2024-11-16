from typing import Dict, List, Optional
import uuid
import time
from dataclasses import dataclass
from threading import Lock
import kubernetes
from kubernetes import client, config
import json
from datetime import datetime

@dataclass
class StorageNodeInfo:
    node_id: str
    hostname: str
    capacity_bytes: int
    used_bytes: int
    status: str
    last_heartbeat: float
    pods: List[str]
    zone: str

class StorageClusterManager:
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self.nodes: Dict[str, StorageNodeInfo] = {}
        self._lock = Lock()
        self.leader = False
        self.node_id = str(uuid.uuid4())
        
        # Initialize kubernetes client
        try:
            config.load_incluster_config()
        except kubernetes.config.ConfigException:
            config.load_kube_config()
        
        self.k8s_api = client.CoreV1Api()
        self.custom_api = client.CustomObjectsApi()

    def start(self):
        """Start the cluster manager and attempt to become leader"""
        self._register_node()
        self._start_leader_election()
        self._start_heartbeat()

    def _register_node(self):
        """Register this node with the cluster"""
        node_info = StorageNodeInfo(
            node_id=self.node_id,
            hostname=self._get_hostname(),
            capacity_bytes=self._get_capacity(),
            used_bytes=0,
            status="READY",
            last_heartbeat=time.time(),
            pods=[],
            zone=self._get_zone()
        )
        
        self._update_node_status(node_info)

    def _start_leader_election(self):
        """Implement leader election using K8s lease objects"""
        lease_name = "storage-cluster-leader"
        
        try:
            lease = client.V1Lease(
                metadata=client.V1ObjectMeta(name=lease_name),
                spec=client.V1LeaseSpec(
                    holder_identity=self.node_id,
                    lease_duration_seconds=15
                )
            )
            
            self.k8s_api.create_namespaced_lease(
                namespace=self.namespace,
                body=lease
            )
            self.leader = True
        except kubernetes.client.rest.ApiException as e:
            if e.status == 409:  # Conflict, lease exists
                self.leader = False
            else:
                raise

    def _start_heartbeat(self):
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
            
            time.sleep(5)

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
        healthy_nodes = [node for node in self.nodes.values() 
                        if node.status == "READY" and node.node_id != failed_node.node_id]
        
        if not healthy_nodes:
            return
        
        # Get data locations from failed node
        data_locations = self._get_node_data_locations(failed_node.node_id)
        
        # Redistribute each piece of data
        for data_id, data_info in data_locations.items():
            target_node = self._select_target_node(healthy_nodes)
            self._replicate_data(data_id, data_info, target_node)

    def _select_target_node(self, healthy_nodes: List[StorageNodeInfo]) -> StorageNodeInfo:
        """Select the best node for data placement based on capacity and load"""
        return min(healthy_nodes, 
                  key=lambda n: n.used_bytes / n.capacity_bytes if n.capacity_bytes > 0 else float('inf'))

    def _replicate_data(self, data_id: str, data_info: dict, target_node: StorageNodeInfo):
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
                "total_capacity": sum(node.capacity_bytes for node in self.nodes.values()),
                "total_used": sum(node.used_bytes for node in self.nodes.values()),
                "healthy_nodes": sum(1 for node in self.nodes.values() if node.status == "READY"),
                "leader_node": self.node_id if self.leader else None
            }

    def _get_hostname(self) -> str:
        """Get the hostname of the current node"""
        return self.k8s_api.read_node(self.node_id).metadata.name

    def _get_capacity(self) -> int:
        """Get the storage capacity of the current node"""
        # Implementation depends on your storage backend
        return 1000000000000  # 1TB default

    def _get_zone(self) -> str:
        """Get the zone/region of the current node"""
        node = self.k8s_api.read_node(self.node_id)
        return node.metadata.labels.get("topology.kubernetes.io/zone", "unknown")

    def _update_node_status(self, node_info: StorageNodeInfo):
        """Update node status in the cluster"""
        with self._lock:
            self.nodes[node_info.node_id] = node_info
            
            # Update K8s custom resource
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
                    "capacity": node_info.capacity_bytes,
                    "used": node_info.used_bytes,
                    "status": node_info.status,
                    "lastHeartbeat": datetime.fromtimestamp(node_info.last_heartbeat).isoformat(),
                    "zone": node_info.zone
                }
            }
            
            try:
                self.custom_api.create_namespaced_custom_object(
                    group="storage.dfs.io",
                    version="v1",
                    namespace=self.namespace,
                    plural="storagenodestatuses",
                    body=node_status
                )
            except kubernetes.client.rest.ApiException as e:
                if e.status == 409:  # Already exists, update instead
                    self.custom_api.patch_namespaced_custom_object(
                        group="storage.dfs.io",
                        version="v1",
                        namespace=self.namespace,
                        plural="storagenodestatuses",
                        name=node_info.node_id,
                        body=node_status
                    )
