import asyncio
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import logging

@dataclass
class VersionedData:
    content: bytes
    version: int
    timestamp: datetime
    checksum: str

class ConsistencyManager:
    def __init__(self, quorum_size: int):
        self.quorum_size = quorum_size
        self.version_map: Dict[str, Dict[str, VersionedData]] = {}  # data_id -> {node_id -> version}
        self.read_locks: Dict[Path, asyncio.Lock] = {}
        self.write_locks: Dict[Path, asyncio.Lock] = {}
        self.logger = logging.getLogger(__name__)

    def get_read_lock(self, path: Path) -> asyncio.Lock:
        """Get or create read lock for path"""
        if path not in self.read_locks:
            self.read_locks[path] = asyncio.Lock()
        return self.read_locks[path]

    def get_write_lock(self, path: Path) -> asyncio.Lock:
        """Get or create write lock for path"""
        if path not in self.write_locks:
            self.write_locks[path] = asyncio.Lock()
        return self.write_locks[path]

    async def verify_write_quorum(self, results: List[Any]) -> bool:
        """Verify if write achieved quorum"""
        successful = sum(1 for r in results if r.get('status') == 'success')
        return successful >= self.quorum_size

    def verify_consistency(self, read_results: List[Any]) -> bool:
        """Verify if all read results are consistent"""
        if not read_results:
            return True

        first_checksum = read_results[0].checksum
        return all(r.checksum == first_checksum for r in read_results)

    def determine_correct_version(self, read_results: List[Any]) -> bytes:
        """Determine the correct version from inconsistent reads"""
        # Group by content
        content_groups: Dict[str, List[Any]] = {}
        for result in read_results:
            checksum = hashlib.sha256(result.content).hexdigest()
            if checksum not in content_groups:
                content_groups[checksum] = []
            content_groups[checksum].append(result)

        # If there's a majority, use it
        total_nodes = len(read_results)
        for content_group in content_groups.values():
            if len(content_group) > total_nodes / 2:
                return content_group[0].content

        # If no majority, use newest version
        newest_result = max(read_results, key=lambda x: x.timestamp)
        return newest_result.content

    async def handle_write_conflict(self, data_id: str, node_versions: Dict[str, VersionedData]) -> None:
        """Handle write conflicts between nodes"""
        # Get the latest version
        latest_version = max(node_versions.values(), key=lambda x: (x.version, x.timestamp))
        
        # Update nodes with older versions
        update_tasks = []
        for node_id, version_data in node_versions.items():
            if version_data.version < latest_version.version:
                update_tasks.append(
                    self.update_node_version(node_id, data_id, latest_version)
                )
        
        if update_tasks:
            await asyncio.gather(*update_tasks)

    async def update_node_version(self, node_id: str, data_id: str, version_data: VersionedData) -> None:
        """Update a node's data version"""
        try:
            # Update version map
            if data_id not in self.version_map:
                self.version_map[data_id] = {}
            self.version_map[data_id][node_id] = version_data
            
            # Trigger actual update on node
            # This would be implemented by the replication manager
            self.logger.info(f"Updated version for node {node_id}, data {data_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to update version for node {node_id}: {str(e)}")

    def get_version_vector(self, data_id: str) -> Dict[str, int]:
        """Get version vector for data across nodes"""
        if data_id not in self.version_map:
            return {}
        
        return {
            node_id: version_data.version
            for node_id, version_data in self.version_map[data_id].items()
        }

    def detect_conflicts(self, version_vector1: Dict[str, int],
                        version_vector2: Dict[str, int]) -> bool:
        """Detect conflicts between version vectors"""
        all_nodes = set(version_vector1.keys()) | set(version_vector2.keys())
        
        for node in all_nodes:
            v1 = version_vector1.get(node, 0)
            v2 = version_vector2.get(node, 0)
            if v1 > 0 and v2 > 0 and v1 != v2:
                return True
        
        return False

    async def resolve_conflicts(self, data_id: str,
                              conflicting_versions: List[VersionedData]) -> VersionedData:
        """Resolve conflicts between multiple versions"""
        # Default to newest version
        resolved_version = max(conflicting_versions,
                             key=lambda x: (x.version, x.timestamp))
        
        # Update version map
        for node_id in self.version_map.get(data_id, {}):
            await self.update_node_version(node_id, data_id, resolved_version)
        
        return resolved_version
