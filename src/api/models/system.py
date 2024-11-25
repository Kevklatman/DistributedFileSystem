"""System-related models for the distributed file system."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Set, Any
from datetime import datetime
import uuid
from enum import Enum

from src.api.models.base_types import SnapshotState
from .base import StorageLocation, Volume
from .storage import StoragePool
from .policy import CloudTieringPolicy, DataProtection, ReplicationPolicy

class SystemStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    MAINTENANCE = "maintenance"

@dataclass
class SystemMetrics:
    """System-wide metrics for the distributed file system"""
    total_storage: int  # in bytes
    used_storage: int   # in bytes
    total_nodes: int
    active_nodes: int
    total_volumes: int
    active_volumes: int
    operations_per_second: float
    last_updated: datetime

    @property
    def available_storage(self) -> int:
        return self.total_storage - self.used_storage

    @property
    def storage_utilization(self) -> float:
        return (self.used_storage / self.total_storage) * 100 if self.total_storage > 0 else 0

    @property
    def node_health(self) -> float:
        return (self.active_nodes / self.total_nodes) * 100 if self.total_nodes > 0 else 0

@dataclass
class SystemConfig:
    """System-wide configuration for the distributed file system"""
    replication_factor: int = 3
    min_nodes_required: int = 1
    max_volume_size: int = 1024 * 1024 * 1024 * 1024  # 1TB
    heartbeat_interval: int = 30  # seconds
    metrics_interval: int = 60    # seconds
    maintenance_window: Optional[Dict[str, str]] = None  # start and end times

@dataclass
class SystemHealth:
    """System health status and diagnostics"""
    status: SystemStatus
    message: str
    last_check: datetime
    warnings: List[str]
    errors: List[str]
    node_statuses: Dict[str, str]  # node_id -> status

@dataclass
class CloudCredentials:
    """Cloud provider credentials and configuration"""
    provider: Literal["aws", "azure", "gcp"]
    credentials: Dict[str, str]
    default_region: str
    endpoints: Dict[str, str] = field(default_factory=dict)

@dataclass
class HybridStorageSystem:
    """Main system managing hybrid storage infrastructure"""
    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    storage_pools: Dict[str, StoragePool] = field(default_factory=dict)
    volumes: Dict[str, Volume] = field(default_factory=dict)
    cloud_credentials: Dict[str, CloudCredentials] = field(default_factory=dict)
    tiering_policies: Dict[str, CloudTieringPolicy] = field(default_factory=dict)
    protection_policies: Dict[str, DataProtection] = field(default_factory=dict)
    replication_policies: Dict[str, ReplicationPolicy] = field(default_factory=dict)

    def add_storage_pool(self, pool: StoragePool):
        """Add a storage pool to the system"""
        self.storage_pools[pool.id] = pool

    def create_volume(self, name: str, size_gb: int, pool_id: str) -> Volume:
        """Create a new volume in the specified pool"""
        if pool_id not in self.storage_pools:
            raise ValueError(f"Storage pool {pool_id} not found")

        pool = self.storage_pools[pool_id]
        volume = Volume(name=name, size_gb=size_gb, primary_pool_id=pool_id)
        self.volumes[volume.id] = volume
        pool.volumes[volume.id] = volume
        return volume

    def get_volume(self, volume_id: str) -> Optional[Volume]:
        """Get a volume by ID"""
        return self.volumes.get(volume_id)

    def delete_volume(self, volume_id: str) -> bool:
        """Delete a volume by ID"""
        if volume_id not in self.volumes:
            return False

        volume = self.volumes[volume_id]
        pool = self.storage_pools.get(volume.primary_pool_id)
        if pool:
            pool.volumes.pop(volume_id, None)

        self.volumes.pop(volume_id)
        return True
