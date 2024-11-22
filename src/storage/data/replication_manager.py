"""
Cross-region replication manager with SnapMirror-like functionality
"""
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import asyncio
import aiohttp
import json
from pathlib import Path
import hashlib
from dataclasses import dataclass
from .models import (
    Volume,
    ReplicationPolicy,
    ReplicationState,
    StorageLocation,
    SnapshotState,
    NodeState,
    VersionedData
)
from .policy_engine import HybridPolicyEngine, PolicyMode
import logging
import random

@dataclass
class ChunkMetadata:
    """Metadata for a chunk during replication"""
    offset: int
    size: int
    checksum: str
    compressed: bool = False

class SyncManager:
    pass

class ConsistencyManager:
    def __init__(self, quorum_size: int):
        self.quorum_size = quorum_size
        self.version_map: Dict[str, Dict[str, VersionedData]] = {}

    async def update_node_version(self, node_id: str, data_id: str, version_data: VersionedData) -> None:
        if data_id not in self.version_map:
            self.version_map[data_id] = {}
        self.version_map[data_id][node_id] = version_data

    def get_version_vector(self, data_id: str) -> Dict[str, int]:
        if data_id not in self.version_map:
            return {}
        return {node_id: version_data.version for node_id, version_data in self.version_map[data_id].items()}

class ReplicationManager:
    """Manages cross-region replication with SnapMirror-like functionality"""
    
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.chunk_size = 1024 * 1024  # 1MB default chunk size
        self.bandwidth_limit = None  # Bytes per second, None for unlimited
        self.active_replications: Dict[str, ReplicationState] = {}
        self.chunk_cache: Dict[str, bytes] = {}  # Checksum -> chunk data
        self.sync_manager = SyncManager()
        self.consistency_manager = ConsistencyManager(quorum_size=2)
        self.logger = logging.getLogger(__name__)

    async def setup_replication(self, volume: Volume, target_location: StorageLocation,
                              policy: ReplicationPolicy) -> None:
        """Initialize replication for a volume"""
        if volume.id in self.active_replications:
            return
            
        # Use policy engine for decision
        decision = HybridPolicyEngine(self.data_path).evaluate_replication_decision(
            volume, target_location
        )
        
        if decision.action != "replicate":
            self.logger.info(
                f"Skipping replication for {volume.id}. Reason: {decision.reason}"
            )
            return
            
        state = ReplicationState(
            source_volume=volume,
            target_location=decision.parameters["target_location"],
            policy=policy,
            last_sync=None,
            in_progress=False,
            priority=decision.parameters.get("priority", "normal")
        )
        self.active_replications[volume.id] = state
        
        # Initialize baseline snapshot if needed
        if not volume.snapshots:
            await self._create_baseline_snapshot(volume)
            
    async def _create_baseline_snapshot(self, volume: Volume) -> None:
        """Create initial snapshot for replication"""
        snapshot = SnapshotState(
            parent_id=None,
            metadata={"type": "replication_baseline"}
        )
        volume.snapshots[snapshot.id] = snapshot
        
    async def start_replication(self, volume_id: str) -> None:
        """Start replication process for a volume"""
        if volume_id not in self.active_replications:
            raise ValueError(f"Replication not set up for volume {volume_id}")
            
        state = self.active_replications[volume_id]
        if state.in_progress:
            return
            
        state.in_progress = True
        try:
            await self._replicate_volume(state)
        finally:
            state.in_progress = False
            
    async def _replicate_volume(self, state: ReplicationState) -> None:
        """Perform volume replication"""
        volume = state.source_volume
        policy = state.policy
        
        # Get latest snapshot
        latest_snapshot = max(
            volume.snapshots.values(),
            key=lambda s: s.creation_time
        )
        
        # Get changed blocks since last sync
        changed_blocks = await self._get_changed_blocks(
            volume,
            latest_snapshot,
            state.last_sync
        )
        
        # Optimize chunk size based on network conditions
        optimal_chunk_size = await self._calculate_optimal_chunk_size()
        chunks = await self._prepare_chunks(volume, changed_blocks, optimal_chunk_size)
        
        # Start transfer with bandwidth management
        async with self._bandwidth_limiter():
            await self._transfer_chunks(chunks, state.target_location)
            
        # Update replication state
        state.last_sync = datetime.now()
        
    async def _get_changed_blocks(self, volume: Volume, snapshot: SnapshotState,
                                last_sync: Optional[datetime]) -> Set[int]:
        """Get blocks that changed since last sync"""
        if not last_sync:
            # First sync, return all blocks
            return set(range(volume.size // self.chunk_size))
            
        changed = set()
        # Compare with previous snapshot
        for block_id in snapshot.changed_blocks:
            changed.add(block_id)
            
        return changed
        
    async def _prepare_chunks(self, volume: Volume, block_ids: Set[int],
                            chunk_size: int) -> List[ChunkMetadata]:
        """Prepare chunks for transfer with deduplication"""
        chunks = []
        volume_path = self.data_path / volume.primary_pool_id / volume.id
        
        for block_id in block_ids:
            offset = block_id * chunk_size
            with open(volume_path, 'rb') as f:
                f.seek(offset)
                data = f.read(chunk_size)
                
            checksum = hashlib.sha256(data).hexdigest()
            
            # Check if chunk is in cache
            if checksum not in self.chunk_cache:
                self.chunk_cache[checksum] = data
                
            chunks.append(ChunkMetadata(
                offset=offset,
                size=len(data),
                checksum=checksum
            ))
            
        return chunks
        
    async def _calculate_optimal_chunk_size(self) -> int:
        """Calculate optimal chunk size based on network conditions"""
        # Implement network speed test and RTT measurement
        # For now, return default
        return self.chunk_size
        
    async def _transfer_chunks(self, chunks: List[ChunkMetadata],
                             target: StorageLocation) -> None:
        """Transfer chunks to target with bandwidth management"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            for chunk in chunks:
                if self.bandwidth_limit:
                    await self._wait_for_bandwidth(chunk.size)
                    
                task = asyncio.create_task(
                    self._transfer_chunk(session, chunk, target)
                )
                tasks.append(task)
                
            await asyncio.gather(*tasks)
            
    async def _transfer_chunk(self, session: aiohttp.ClientSession,
                            chunk: ChunkMetadata, target: StorageLocation) -> None:
        """Transfer a single chunk"""
        data = self.chunk_cache[chunk.checksum]
        
        # Compress if beneficial
        if len(data) > 1024:  # Only compress chunks > 1KB
            compressed = await self._compress_chunk(data)
            if len(compressed) < len(data):
                data = compressed
                chunk.compressed = True
                
        # Upload to target
        async with session.put(
            f"{target.endpoint}/{chunk.offset}",
            data=data,
            headers={
                "X-Checksum": chunk.checksum,
                "X-Compressed": str(chunk.compressed)
            }
        ) as response:
            await response.read()
            
    async def _compress_chunk(self, data: bytes) -> bytes:
        """Compress chunk data"""
        import zlib
        return zlib.compress(data)
        
    async def _wait_for_bandwidth(self, size: int) -> None:
        """Wait to respect bandwidth limit"""
        if not self.bandwidth_limit:
            return
            
        wait_time = size / self.bandwidth_limit
        await asyncio.sleep(wait_time)
        
    @asyncio.contextmanager
    async def _bandwidth_limiter(self):
        """Context manager for bandwidth limiting"""
        # Could implement token bucket algorithm here
        yield
        
    def update_policy(self, volume_id: str, policy: ReplicationPolicy) -> None:
        """Update replication policy for a volume"""
        if volume_id not in self.active_replications:
            raise ValueError(f"No active replication for volume {volume_id}")
            
        self.active_replications[volume_id].policy = policy
        
    def set_bandwidth_limit(self, limit_bytes_per_sec: Optional[int]) -> None:
        """Set bandwidth limit for replication"""
        self.bandwidth_limit = limit_bytes_per_sec

    async def replicate_to_node(self, target_node: NodeState, data_id: str,
                              content: bytes, checksum: str) -> Dict[str, any]:
        """Replicate data to a specific node"""
        try:
            # Create versioned data
            version_data = VersionedData(
                content=content,
                version=self._get_next_version(data_id),
                timestamp=datetime.now(),
                checksum=checksum
            )

            # Send data to node
            result = await self._send_to_node(target_node, data_id, version_data)

            # Update version map on success
            if result.get('status') == 'success':
                await self.consistency_manager.update_node_version(
                    target_node.node_id, data_id, version_data
                )

            return result

        except Exception as e:
            self.logger.error(f"Replication to node {target_node.node_id} failed: {str(e)}")
            return {'status': 'error', 'error': str(e)}

    async def _send_to_node(self, node: NodeState, data_id: str,
                           version_data: VersionedData) -> Dict[str, any]:
        """Send data to a node"""
        try:
            # Implement actual send logic here
            # This could use gRPC, HTTP, or other protocols
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    f"http://{node.address}/storage/data/{data_id}",
                    data=version_data.content,
                    headers={
                        'X-Version': str(version_data.version),
                        'X-Checksum': version_data.checksum,
                        'X-Timestamp': version_data.timestamp.isoformat()
                    }
                ) as response:
                    if response.status == 200:
                        return {'status': 'success'}
                    else:
                        return {
                            'status': 'error',
                            'error': f"HTTP {response.status}: {await response.text()}"
                        }

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    def _get_next_version(self, data_id: str) -> int:
        """Get next version number for data"""
        version_vector = self.consistency_manager.get_version_vector(data_id)
        if not version_vector:
            return 1
        return max(version_vector.values()) + 1

    async def handle_node_failure(self, failed_node_id: str) -> None:
        """Handle node failure"""
        try:
            # Get all data versions from failed node
            failed_versions = self._get_node_versions(failed_node_id)

            # Trigger re-replication for all affected data
            replication_tasks = []
            for data_id, version_data in failed_versions.items():
                task = self.ensure_replication_level(data_id, version_data)
                replication_tasks.append(task)

            await asyncio.gather(*replication_tasks)

        except Exception as e:
            self.logger.error(f"Failed to handle node failure: {str(e)}")

    async def ensure_replication_level(self, data_id: str,
                                     version_data: VersionedData) -> None:
        """Ensure data is replicated to enough nodes"""
        try:
            # Get current replicas
            current_replicas = self._get_data_locations(data_id)
            
            # Calculate how many new replicas we need
            needed_replicas = max(0, self.consistency_manager.quorum_size - len(current_replicas))
            
            if needed_replicas > 0:
                # Find suitable nodes for new replicas
                target_nodes = self._select_replica_nodes(needed_replicas, current_replicas)
                
                # Replicate to new nodes
                replication_tasks = []
                for node in target_nodes:
                    task = self.replicate_to_node(
                        node, data_id, version_data.content, version_data.checksum
                    )
                    replication_tasks.append(task)
                
                await asyncio.gather(*replication_tasks)

        except Exception as e:
            self.logger.error(f"Failed to ensure replication level: {str(e)}")

    def _get_node_versions(self, node_id: str) -> Dict[str, VersionedData]:
        """Get all version data for a node"""
        versions = {}
        for data_id, node_versions in self.consistency_manager.version_map.items():
            if node_id in node_versions:
                versions[data_id] = node_versions[node_id]
        return versions

    def _get_data_locations(self, data_id: str) -> Set[str]:
        """Get set of nodes that have a copy of the data"""
        if data_id not in self.consistency_manager.version_map:
            return set()
        return set(self.consistency_manager.version_map[data_id].keys())

    def _select_replica_nodes(self, count: int, exclude_nodes: Set[str]) -> List[NodeState]:
        """
        Select suitable nodes for new replicas based on multiple factors:
        - Node health (CPU, memory, disk usage)
        - Geographic location for data locality
        - Current load and capacity
        - Network latency
        
        Args:
            count: Number of replica nodes needed
            exclude_nodes: Set of node IDs to exclude from selection
            
        Returns:
            List of selected NodeState objects
        """
        try:
            # Get all available nodes from cluster state
            available_nodes = self._get_available_nodes()
            
            # Filter out excluded nodes
            candidate_nodes = [
                node for node in available_nodes 
                if node.node_id not in exclude_nodes
            ]
            
            if not candidate_nodes:
                raise ValueError("No available nodes for replication")
                
            # Score each node based on multiple factors
            scored_nodes = []
            for node in candidate_nodes:
                score = self._calculate_node_score(node)
                scored_nodes.append((score, node))
                
            # Sort by score (highest first) and select top nodes
            scored_nodes.sort(reverse=True, key=lambda x: x[0])
            selected_nodes = [node for _, node in scored_nodes[:count]]
            
            if len(selected_nodes) < count:
                self.logger.warning(
                    f"Could only find {len(selected_nodes)} nodes for replication, "
                    f"wanted {count}"
                )
                
            return selected_nodes
            
        except Exception as e:
            self.logger.error(f"Error selecting replica nodes: {str(e)}")
            return []
            
    def _calculate_node_score(self, node: NodeState) -> float:
        """
        Calculate a score for a node based on various metrics.
        Higher score = better candidate for replication.
        """
        try:
            # Start with base score
            score = 100.0
            
            # Factor 1: System Load (0-30 points)
            # Lower load is better
            load_score = 30 * (1 - min(1.0, node.system_load / 10.0))
            score += load_score
            
            # Factor 2: Available Storage (0-25 points)
            # More free storage is better
            storage_ratio = node.available_storage / node.total_storage
            storage_score = 25 * storage_ratio
            score += storage_score
            
            # Factor 3: Memory Usage (0-20 points)
            # Lower memory usage is better
            memory_ratio = node.used_memory / node.total_memory
            memory_score = 20 * (1 - memory_ratio)
            score += memory_score
            
            # Factor 4: Network Health (0-15 points)
            # Lower latency and higher bandwidth is better
            if node.network_latency > 0:
                latency_score = 15 * (1 - min(1.0, node.network_latency / 1000.0))
                score += latency_score
                
            # Factor 5: Geographic Location (0-10 points)
            # Prefer nodes in different regions for redundancy
            geo_score = self._calculate_geo_distribution_score(node)
            score += geo_score
            
            return max(0.0, min(200.0, score))
            
        except Exception as e:
            self.logger.error(f"Error calculating node score: {str(e)}")
            return 0.0
            
    def _calculate_geo_distribution_score(self, node: NodeState) -> float:
        """Calculate score based on geographic distribution of replicas"""
        try:
            # Get current replica locations
            current_regions = set()
            for existing_node in self._get_available_nodes():
                if existing_node.region:
                    current_regions.add(existing_node.region)
                    
            # Reward nodes in new regions
            if node.region and node.region not in current_regions:
                return 10.0
            return 5.0
            
        except Exception as e:
            self.logger.error(f"Error calculating geo distribution score: {str(e)}")
            return 0.0
            
    def _get_available_nodes(self) -> List[NodeState]:
        """Get list of all available nodes in the cluster"""
        try:
            # This would typically come from your cluster manager
            # For now, we'll get it from the consistency manager's state
            available_nodes = set()
            for node_versions in self.consistency_manager.version_map.values():
                for node_id in node_versions.keys():
                    # Convert node_id to NodeState object
                    # This would normally fetch actual node state from cluster
                    node_state = self._get_node_state(node_id)
                    if node_state:
                        available_nodes.add(node_state)
            
            return list(available_nodes)
            
        except Exception as e:
            self.logger.error(f"Error getting available nodes: {str(e)}")
            return []
            
    def _get_node_state(self, node_id: str) -> Optional[NodeState]:
        """Get current state of a node"""
        try:
            # This would typically fetch real-time metrics from the node
            # For now, return a dummy state
            return NodeState(
                node_id=node_id,
                address=f"node-{node_id}:8080",
                system_load=random.uniform(0, 10),
                available_storage=random.uniform(100_000_000, 1_000_000_000),
                total_storage=1_000_000_000,
                used_memory=random.uniform(0, 16_000_000_000),
                total_memory=16_000_000_000,
                network_latency=random.uniform(10, 1000),
                region=f"region-{random.randint(1, 5)}"
            )
            
        except Exception as e:
            self.logger.error(f"Error getting node state: {str(e)}")
            return None
