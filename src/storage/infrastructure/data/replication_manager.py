"""Manages data replication across storage nodes."""
import asyncio
import logging
from typing import Dict, List, Set, Optional, Any
import hashlib
from datetime import datetime
import aiohttp
from dataclasses import dataclass

@dataclass
class ReplicationResult:
    """Result of a replication operation."""
    success: bool
    error: Optional[str] = None
    timestamp: datetime = datetime.now()

class ReplicationManager:
    """Manages data replication across storage nodes."""
    
    def __init__(self, min_replicas: int = 3):
        self.min_replicas = min_replicas
        self.logger = logging.getLogger(__name__)
        self._replication_tasks: Dict[str, asyncio.Task] = {}
        self._data_locations: Dict[str, Set[str]] = {}  # data_id -> set of node_ids
        
    async def replicate_to_node(self, node: Any, data_id: str,
                               content: bytes, checksum: str) -> ReplicationResult:
        """Replicate data to a specific node."""
        try:
            # Verify data integrity
            if hashlib.sha256(content).hexdigest() != checksum:
                return ReplicationResult(
                    success=False,
                    error="Data integrity check failed"
                )
            
            # Send data to node
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    f"http://{node.pod_ip}:8080/data/{data_id}",
                    data=content,
                    headers={
                        'Content-Type': 'application/octet-stream',
                        'X-Checksum': checksum
                    },
                    timeout=30.0
                ) as response:
                    if response.status == 200:
                        # Update data locations
                        if data_id not in self._data_locations:
                            self._data_locations[data_id] = set()
                        self._data_locations[data_id].add(node.node_id)
                        
                        return ReplicationResult(success=True)
                    else:
                        error_msg = await response.text()
                        return ReplicationResult(
                            success=False,
                            error=f"Replication failed: {error_msg}"
                        )
                        
        except Exception as e:
            self.logger.error(f"Replication error: {str(e)}")
            return ReplicationResult(success=False, error=str(e))
            
    def _select_replica_nodes(self, count: int, exclude_nodes: Set[str]) -> List[Any]:
        """Select nodes for replication based on availability and load."""
        # This is a placeholder - in practice, you would:
        # 1. Get list of all available nodes
        # 2. Filter out excluded nodes
        # 3. Sort by capacity and load
        # 4. Return top 'count' nodes
        return []
        
    async def ensure_replication_level(self, data_id: str,
                                     content: bytes,
                                     current_nodes: Set[str]) -> None:
        """Ensure data has minimum number of replicas."""
        if len(current_nodes) >= self.min_replicas:
            return
            
        needed_replicas = self.min_replicas - len(current_nodes)
        target_nodes = self._select_replica_nodes(needed_replicas, current_nodes)
        
        # Start parallel replication to target nodes
        replication_tasks = []
        checksum = hashlib.sha256(content).hexdigest()
        
        for node in target_nodes:
            task = asyncio.create_task(
                self.replicate_to_node(node, data_id, content, checksum)
            )
            replication_tasks.append(task)
            
        # Wait for all replications to complete
        results = await asyncio.gather(*replication_tasks, return_exceptions=True)
        
        # Log any failures
        for node, result in zip(target_nodes, results):
            if isinstance(result, Exception):
                self.logger.error(
                    f"Replication to node {node.node_id} failed: {str(result)}"
                )
            elif not result.success:
                self.logger.error(
                    f"Replication to node {node.node_id} failed: {result.error}"
                )
                
    async def handle_node_failure(self, failed_node_id: str) -> None:
        """Handle node failure by re-replicating affected data."""
        # Find all data that was on the failed node
        affected_data = {
            data_id: nodes
            for data_id, nodes in self._data_locations.items()
            if failed_node_id in nodes
        }
        
        # Remove failed node from locations
        for nodes in affected_data.values():
            nodes.discard(failed_node_id)
            
        # Re-replicate affected data
        for data_id, current_nodes in affected_data.items():
            if len(current_nodes) < self.min_replicas:
                # Note: In practice, you would need to retrieve the data content
                # from one of the surviving replicas
                content = await self._get_data_from_replicas(data_id, current_nodes)
                if content:
                    await self.ensure_replication_level(data_id, content, current_nodes)
                    
    async def _get_data_from_replicas(self, data_id: str,
                                     replica_nodes: Set[str]) -> Optional[bytes]:
        """Retrieve data from any available replica."""
        # This is a placeholder - in practice, you would:
        # 1. Try to get data from each replica node
        # 2. Verify data integrity
        # 3. Return first successful result
        return None
