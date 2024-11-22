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
class Volume:
    """Logical storage volume."""
    volume_id: str
    size_bytes: int
    used_bytes: int
    created_at: datetime
    last_accessed_at: datetime
    locations: List[StorageLocation]
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
