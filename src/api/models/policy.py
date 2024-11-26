"""Policy-related models for the distributed file system."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from datetime import datetime
from enum import Enum
from src.api.models.base_types import SnapshotState
from .base import StorageLocation


class ReplicationType(Enum):
    SYNCHRONOUS = "sync"
    ASYNCHRONOUS = "async"
    SEMI_SYNC = "semi-sync"


class RetentionType(Enum):
    TIME_BASED = "time-based"
    VERSION_BASED = "version-based"
    HYBRID = "hybrid"


@dataclass
class TieringPolicy:
    """Defines data tiering behavior"""

    enabled: bool = True
    auto_tiering: bool = True
    target_tier: Optional[str] = None
    min_size_mb: int = 100
    min_age_days: int = 30
    exclude_patterns: List[str] = field(default_factory=list)


@dataclass
class CloudTieringPolicy:
    """Defines how data is tiered between on-prem and cloud"""

    volume_id: str
    target_cloud_location: StorageLocation
    temperature_thresholds: Dict[str, int] = field(
        default_factory=lambda: {
            "hot_to_warm_days": 7,
            "warm_to_cold_days": 30,
            "cold_to_frozen_days": 90,
        }
    )
    minimum_file_size_mb: int = 100
    cost_threshold_per_gb: float = 0.05
    access_pattern_weight: float = 0.3
    prediction_weight: float = 0.2
    exclude_patterns: List[str] = field(default_factory=list)
    schedule: str = "0 0 * * *"


@dataclass
class ReplicationPolicy:
    """Policy for data replication across storage nodes"""

    policy_id: str
    name: str
    replication_type: ReplicationType
    replication_factor: int
    priority: int
    target_nodes: List[str]
    created_at: datetime
    updated_at: datetime
    enabled: bool = True


@dataclass
class RetentionPolicy:
    """Policy for data retention and lifecycle"""

    policy_id: str
    name: str
    retention_type: RetentionType
    retention_period: int  # in seconds
    max_versions: int
    created_at: datetime
    updated_at: datetime
    auto_delete: bool = True
    enabled: bool = True


@dataclass
class DataProtection:
    """Defines data protection policies across hybrid environment"""

    volume_id: str
    local_snapshot_enabled: bool = True
    local_snapshot_schedule: str = "0 * * * *"
    local_snapshot_retention_days: int = 7
    cloud_backup_enabled: bool = False
    cloud_backup_schedule: str = "0 0 * * *"
    cloud_backup_retention_days: int = 30
    disaster_recovery_enabled: bool = False
    dr_location: Optional[StorageLocation] = None
    snapshots: Dict[str, "SnapshotState"] = field(default_factory=dict)


@dataclass
class StoragePolicy:
    """Combined storage policies for a volume or node"""

    policy_id: str
    name: str
    description: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    retention_policy: Optional[RetentionPolicy] = None
    replication_policy: Optional[ReplicationPolicy] = None
    tiering_policy: Optional[CloudTieringPolicy] = None
    data_protection: Optional[DataProtection] = None
    enabled: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)
    encryption_enabled: bool = False
    compression_enabled: bool = False
    deduplication_enabled: bool = False
    labels: Dict[str, str] = None

    def __post_init__(self):
        if self.labels is None:
            self.labels = {}
