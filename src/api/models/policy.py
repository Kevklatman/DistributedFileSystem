"""Policy-related models for the distributed file system."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from datetime import datetime
from system import SnapshotState
from .base import StorageLocation

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
    temperature_thresholds: Dict[str, int] = field(default_factory=lambda: {
        "hot_to_warm_days": 7,
        "warm_to_cold_days": 30,
        "cold_to_frozen_days": 90
    })
    minimum_file_size_mb: int = 100
    cost_threshold_per_gb: float = 0.05
    access_pattern_weight: float = 0.3
    prediction_weight: float = 0.2
    exclude_patterns: List[str] = field(default_factory=list)
    schedule: str = "0 0 * * *"

@dataclass
class ReplicationPolicy:
    """Defines replication behavior"""
    enabled: bool = True
    target_locations: List[StorageLocation] = field(default_factory=list)
    min_copies: int = 2
    max_copies: int = 5
    sync_mode: Literal["sync", "async"] = "async"
    bandwidth_limit_mbps: Optional[int] = None
    exclude_patterns: List[str] = field(default_factory=list)

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
    snapshots: Dict[str, 'SnapshotState'] = field(default_factory=dict)
