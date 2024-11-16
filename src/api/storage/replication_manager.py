from typing import Dict, List, Optional, Tuple
import hashlib
import asyncio
import aiohttp
from dataclasses import dataclass
import time
from concurrent.futures import ThreadPoolExecutor
import logging

@dataclass
class ReplicationPolicy:
    min_copies: int = 3
    sync_replication: bool = True
    consistency_level: str = "quorum"  # one, quorum, all
    preferred_zones: List[str] = None

class ReplicationManager:
    def __init__(self, cluster_manager, policy: ReplicationPolicy = None):
        self.cluster_manager = cluster_manager
        self.policy = policy or ReplicationPolicy()
        self.replication_queue = asyncio.Queue()
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Start the replication manager"""
        await asyncio.gather(
            self._process_replication_queue(),
            self._monitor_replication_health()
        )

    async def replicate_data(self, data_id: str, data: bytes, source_node: str) -> List[str]:
        """
        Replicate data to multiple nodes according to the replication policy
        Returns list of node IDs where data was successfully replicated
        """
        target_nodes = self._select_target_nodes(
            excluding_nodes=[source_node],
            count=self.policy.min_copies
        )

        if not target_nodes:
            raise Exception("Not enough healthy nodes available for replication")

        replication_tasks = []
        for node in target_nodes:
            task = self._replicate_to_node(data_id, data, node)
            replication_tasks.append(task)

        if self.policy.sync_replication:
            # Wait for all replications to complete
            results = await asyncio.gather(*replication_tasks, return_exceptions=True)
            successful_nodes = [
                node for node, success in zip(target_nodes, results)
                if not isinstance(success, Exception)
            ]

            if len(successful_nodes) < self._get_min_successful_copies():
                raise Exception("Failed to meet minimum replication requirement")

            return successful_nodes
        else:
            # Async replication - queue the tasks and return immediately
            for task in replication_tasks:
                await self.replication_queue.put(task)
            return [node.node_id for node in target_nodes]

    def _select_target_nodes(self, excluding_nodes: List[str], count: int) -> List[str]:
        """Select appropriate target nodes for replication"""
        available_nodes = [
            node for node in self.cluster_manager.nodes.values()
            if node.node_id not in excluding_nodes
            and node.status == "READY"
            and (node.capacity_bytes - node.used_bytes) > 0
        ]

        if self.policy.preferred_zones:
            # Prioritize nodes in preferred zones
            available_nodes.sort(
                key=lambda n: n.zone in self.policy.preferred_zones,
                reverse=True
            )

        # Select nodes with most available space
        return sorted(
            available_nodes,
            key=lambda n: (n.capacity_bytes - n.used_bytes),
            reverse=True
        )[:count]

    async def _replicate_to_node(self, data_id: str, data: bytes, target_node: str) -> bool:
        """Replicate data to a specific node"""
        try:
            checksum = hashlib.sha256(data).hexdigest()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{target_node.hostname}:8080/storage/replicate",
                    json={
                        "data_id": data_id,
                        "data": data.hex(),
                        "checksum": checksum
                    }
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Replication failed: {await response.text()}")
                    
                    # Verify the checksum
                    resp_data = await response.json()
                    if resp_data["checksum"] != checksum:
                        raise Exception("Checksum verification failed")
                    
                    return True
        except Exception as e:
            self.logger.error(f"Replication to node {target_node.node_id} failed: {str(e)}")
            return False

    async def _process_replication_queue(self):
        """Process async replication queue"""
        while True:
            task = await self.replication_queue.get()
            try:
                await task
            except Exception as e:
                self.logger.error(f"Async replication failed: {str(e)}")
            finally:
                self.replication_queue.task_done()

    async def _monitor_replication_health(self):
        """Monitor and maintain replication health"""
        while True:
            try:
                await self._check_replication_status()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                self.logger.error(f"Replication health check failed: {str(e)}")
                await asyncio.sleep(60)  # Retry after 1 minute on error

    async def _check_replication_status(self):
        """Check and repair replication status of all data"""
        # Get all data locations
        data_locations = await self._get_all_data_locations()
        
        for data_id, locations in data_locations.items():
            if len(locations) < self.policy.min_copies:
                # Need to create more replicas
                await self._repair_replication(data_id, locations)

    async def _repair_replication(self, data_id: str, current_locations: List[str]):
        """Repair replication for under-replicated data"""
        needed_copies = self.policy.min_copies - len(current_locations)
        if needed_copies <= 0:
            return

        # Get the data from one of the existing locations
        source_node = current_locations[0]
        data = await self._fetch_data(data_id, source_node)
        
        # Replicate to new nodes
        await self.replicate_data(data_id, data, source_node)

    async def _fetch_data(self, data_id: str, node_id: str) -> bytes:
        """Fetch data from a specific node"""
        node = self.cluster_manager.nodes.get(node_id)
        if not node:
            raise Exception(f"Node {node_id} not found")

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://{node.hostname}:8080/storage/data/{data_id}"
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch data: {await response.text()}")
                return await response.read()

    def _get_min_successful_copies(self) -> int:
        """Get minimum number of successful copies needed based on consistency level"""
        if self.policy.consistency_level == "one":
            return 1
        elif self.policy.consistency_level == "quorum":
            return (self.policy.min_copies // 2) + 1
        elif self.policy.consistency_level == "all":
            return self.policy.min_copies
        else:
            return self.policy.min_copies
