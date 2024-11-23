"""Manages data consistency across storage nodes."""
import asyncio
import logging
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class VersionedData:
    """Data with version information."""
    content: bytes
    version: int
    timestamp: datetime
    checksum: str

@dataclass
class WriteOperation:
    """Write operation metadata."""
    data_id: str
    content: bytes
    version: int
    checksum: str
    timestamp: datetime
    consistency_level: str

class ConsistencyManager:
    """Manages data consistency across storage nodes."""

    def __init__(self, quorum_size: int = 2):
        self.quorum_size = quorum_size
        self.logger = logging.getLogger(__name__)
        self._version_map: Dict[str, Dict[str, VersionedData]] = {}  # data_id -> {node_id -> version}
        self._pending_writes: Dict[str, WriteOperation] = {}
        self._write_locks: Dict[str, asyncio.Lock] = {}
        self._active_nodes: Dict[str, Set[str]] = {}  # data_id -> set of node_ids
        self._current_version = 0

    async def get_next_version(self, data_id: str) -> int:
        """Get next version number for data."""
        if data_id not in self._version_map:
            return 1

        max_version = max(
            data.version
            for data in self._version_map[data_id].values()
        )
        return max_version + 1

    async def update_node_version(self, node_id: str, data_id: str,
                                version_data: VersionedData) -> None:
        """Update version information for a node."""
        # Initialize version map for data_id if it doesn't exist
        if data_id not in self._version_map:
            self._version_map[data_id] = {}

        # Initialize active nodes set for data_id if it doesn't exist
        if data_id not in self._active_nodes:
            self._active_nodes[data_id] = set()

        # Update version information
        self._version_map[data_id][node_id] = version_data

        # Add node to active nodes
        self._active_nodes[data_id].add(node_id)

    def get_node_data(self, node_id: str) -> Dict[str, VersionedData]:
        """Get all data versions for a node."""
        result = {}
        for data_id, node_versions in self._version_map.items():
            if node_id in node_versions:
                result[data_id] = node_versions[node_id]
        return result

    async def start_write(self, write_op: WriteOperation) -> None:
        """Start a write operation."""
        if write_op.data_id not in self._write_locks:
            self._write_locks[write_op.data_id] = asyncio.Lock()

        self._pending_writes[write_op.data_id] = write_op

    async def complete_write(self, data_id: str,
                           successful_nodes: Set[str]) -> bool:
        """Complete a write operation."""
        write_op = self._pending_writes.get(data_id)
        if not write_op:
            self.logger.error(f"No pending write operation found for data_id: {data_id}")
            return False

        try:
            # Get total active nodes for this data
            total_nodes = len(self._active_nodes.get(data_id, set()))
            self.logger.info(f"Total active nodes for {data_id}: {total_nodes}")
            self.logger.info(f"Successful nodes: {successful_nodes}")

            # Check if consistency requirements are met
            if write_op.consistency_level == "strong":
                # All nodes must succeed
                if total_nodes > 0 and len(successful_nodes) < total_nodes:
                    self.logger.error(
                        f"Strong consistency failed: {len(successful_nodes)} < {total_nodes} nodes"
                    )
                    return False
            elif write_op.consistency_level == "quorum":
                # Quorum of nodes must succeed
                if len(successful_nodes) < self.quorum_size:
                    self.logger.error(
                        f"Quorum consistency failed: {len(successful_nodes)} < {self.quorum_size} nodes"
                    )
                    return False

            # Update version information for successful nodes
            version_data = VersionedData(
                content=write_op.content,
                version=write_op.version,
                timestamp=write_op.timestamp,
                checksum=write_op.checksum
            )

            for node_id in successful_nodes:
                await self.update_node_version(node_id, data_id, version_data)

            self.logger.info(f"Write operation completed successfully for {data_id}")

            # Only clean up on success
            if data_id in self._pending_writes:
                del self._pending_writes[data_id]

            return True

        except Exception as e:
            self.logger.error(f"Error during write completion: {e}")
            return False

    async def get_latest_version(self, data_id: str,
                               consistency_level: str = "eventual") -> Optional[VersionedData]:
        """Get latest version of data based on consistency level."""
        if data_id not in self._version_map:
            return None

        node_versions = self._version_map[data_id]
        if not node_versions:
            return None

        if consistency_level == "strong":
            # All versions must match
            versions = set(data.version for data in node_versions.values())
            if len(versions) != 1:
                return None

        # Return newest version
        return max(
            node_versions.values(),
            key=lambda x: (x.version, x.timestamp)
        )

    def generate_version(self) -> int:
        """Generate a new version number for data updates."""
        self._current_version += 1
        return self._current_version

    def validate_version(self, version: int, timestamp: datetime) -> bool:
        """Validate if a version is current and consistent."""
        return version > 0 and version <= self._current_version

    def resolve_conflicts(self, versions: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve version conflicts using timestamp and version number."""
        if not versions:
            return None

        # Sort by version number (descending) and timestamp
        sorted_versions = sorted(
            versions.values(),
            key=lambda x: (x.get('version', 0), x.get('timestamp', datetime.min)),
            reverse=True
        )

        return sorted_versions[0]
