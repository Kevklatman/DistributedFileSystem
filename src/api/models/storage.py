"""Storage-related models for the distributed file system."""

from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional
from datetime import datetime
import uuid
from enum import Enum

from .base import StorageLocation, Volume


@dataclass
class DeduplicationState:
    """Tracks deduplication state"""

    enabled: bool = True
    global_dedup: bool = False  # Enable cross-volume dedup
    chunk_size: int = 4096  # Chunk size for dedup
    hash_dict: Dict[str, Set[str]] = field(
        default_factory=dict
    )  # Hash to paths mapping
    space_saved: float = 0.0  # Space saved in GB


@dataclass
class CompressionState:
    """Tracks compression state and algorithms"""

    enabled: bool = True
    algorithm: str = "zstd"
    level: int = 3  # Compression level
    min_size: int = 4096  # Minimum size to compress
    adaptive: bool = True  # Adapt compression based on data type
    space_saved: float = 0.0  # Space saved in GB


@dataclass
class StoragePool:
    """Physical or cloud storage resources that can be allocated"""

    name: str
    location: StorageLocation
    total_capacity_gb: int
    available_capacity_gb: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_thin_provisioned: bool = True
    encryption_enabled: bool = True
    oversubscription_ratio: float = 1.0
    dedup_state: DeduplicationState = field(default_factory=DeduplicationState)
    compression_state: CompressionState = field(default_factory=CompressionState)
    created_at: datetime = field(default_factory=datetime.now)
    volumes: Dict[str, Volume] = field(default_factory=dict)

    def __post_init__(self):
        if self.volumes is None:
            self.volumes = {}


class StorageNodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"


@dataclass
class StorageNode:
    """Represents a storage node in the distributed file system"""

    node_id: str
    hostname: str
    ip_address: str
    port: int
    status: StorageNodeStatus
    total_space: int  # in bytes
    used_space: int  # in bytes
    last_heartbeat: datetime
    labels: dict
    metrics_port: Optional[int] = None

    @property
    def available_space(self) -> int:
        return self.total_space - self.used_space

    @property
    def utilization(self) -> float:
        return (self.used_space / self.total_space) * 100 if self.total_space > 0 else 0


@dataclass
class StorageVolume:
    """Represents a storage volume in the distributed file system"""

    volume_id: str
    name: str
    size: int  # in bytes
    node_id: str
    mount_point: str
    created_at: datetime
    status: str
    persistent: bool = True


@dataclass
class StorageAllocation:
    """Represents a storage allocation request/response"""

    volume_id: str
    requested_size: int  # in bytes
    allocated_size: int  # in bytes
    node_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None
