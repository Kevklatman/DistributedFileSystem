"""Data models for the distributed storage system."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict

class DataTemperature(Enum):
    """Data temperature for tiering decisions."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"

@dataclass
class StorageLocation:
    """Physical location of stored data."""
    node_id: str
    path: str
    size_bytes: int
    replicas: List[str]
    temperature: DataTemperature

@dataclass
class StoragePool:
    """Collection of storage resources."""
    pool_id: str
    total_bytes: int
    used_bytes: int
    nodes: List[str]
    tier: DataTemperature

@dataclass
class DeduplicationState:
    """State tracking for data deduplication."""
    total_savings: int = 0
    last_run: Optional[datetime] = None
    chunks_deduped: int = 0
    total_chunks: int = 0

@dataclass
class CompressionState:
    """State tracking for data compression."""
    total_savings: int = 0
    compression_ratio: float = 1.0
    algorithm: str = 'zlib'
    last_run: Optional[datetime] = None

@dataclass
class ThinProvisioningState:
    """State tracking for thin provisioning."""
    allocated_size: int = 0
    used_size: int = 0
    oversubscription_ratio: float = 2.0
    last_reclaim: Optional[datetime] = None

@dataclass
class Volume:
    """Logical storage volume."""
    volume_id: str
    size_bytes: int
    used_bytes: int
    created_at: datetime
    last_accessed_at: datetime
    locations: List[StorageLocation]
    primary_pool_id: str = "default"
    deduplication_enabled: bool = False
    deduplication_state: Optional[DeduplicationState] = None
    compression_state: Optional[CompressionState] = None
    thin_provisioning_state: Optional[ThinProvisioningState] = None
    tiering_policy: Optional['CloudTieringPolicy'] = None
    protection: Optional['DataProtection'] = None

@dataclass
class CloudTieringPolicy:
    """Policy for data movement between storage tiers."""
    cold_tier_after_days: int
    archive_tier_after_days: int
    delete_after_days: Optional[int] = None

@dataclass
class DataProtection:
    """Data protection and replication settings."""
    replica_count: int
    consistency_level: str = "eventual"  # eventual, strong
    sync_replication: bool = False
    backup_schedule: Optional[str] = None

@dataclass
class HybridStorageSystem:
    """Overall storage system state."""
    pools: Dict[str, StoragePool]
    volumes: Dict[str, Volume]
    total_capacity_bytes: int
    used_capacity_bytes: int
    node_count: int

@dataclass
class SnapshotState:
    """Point-in-time snapshot of volume state."""
    snapshot_id: str
    volume_id: str
    created_at: datetime
    size_bytes: int
    locations: List[StorageLocation]
    expires_at: Optional[datetime] = None
