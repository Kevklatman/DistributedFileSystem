"""Unified data models for the distributed file system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Literal, Set, Any
from enum import Enum
import uuid
from pathlib import Path

# Enums
class PolicyMode(Enum):
    MANUAL = "manual"
    ML = "ml"
    HYBRID = "hybrid"
    SUPERVISED = "supervised"

class TierType(Enum):
    PERFORMANCE = "performance"  # NVMe/SSD
    CAPACITY = "capacity"      # HDD
    COLD = "cold"             # S3/Azure Blob
    ARCHIVE = "archive"       # Glacier/Archive

# Core Storage Models
@dataclass
class StorageLocation:
    """Represents a storage location either on-premises or in cloud"""
    type: Literal["on_prem", "aws_s3", "azure_blob", "gcp_storage"]
    path: str
    region: Optional[str] = None
    availability_zone: Optional[str] = None
    performance_tier: Literal["premium_ssd", "standard_ssd", "standard_hdd", "archive"] = "standard_ssd"
    cost_per_gb: float = 0.0  # Cost per GB per month

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
    oversubscription_ratio: float = 1.0  # For thin provisioning
    dedup_state: 'DeduplicationState' = field(default_factory=lambda: DeduplicationState())
    compression_state: 'CompressionState' = field(default_factory=lambda: CompressionState())
    created_at: datetime = field(default_factory=datetime.now)

@dataclass(frozen=True)
class Volume:
    """Represents a logical volume that can span across on-prem and cloud."""
    name: str
    size_gb: int
    primary_pool_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    snapshots: Dict[str, 'SnapshotState'] = field(default_factory=dict)
    backups: Dict[str, 'BackupState'] = field(default_factory=dict)
    cloud_backup_enabled: bool = False
    cloud_tiering_enabled: bool = False
    cloud_location: Optional[StorageLocation] = None
    encryption_at_rest: bool = True
    compression_enabled: bool = True
    deduplication_enabled: bool = True
    data_temperature: Dict[str, 'DataTemperature'] = field(default_factory=dict)
    tiering_policy: 'TieringPolicy' = field(default_factory=lambda: TieringPolicy())
    retention_policy: Optional['RetentionPolicy'] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __getitem__(self, key):
        """Support dictionary-like access to snapshots."""
        return self.snapshots[key]

    def __setitem__(self, key, value):
        """Support dictionary-like assignment to snapshots."""
        self.snapshots[key] = value

# Data Efficiency Models
@dataclass
class DeduplicationState:
    """Tracks deduplication state"""
    enabled: bool = True
    global_dedup: bool = False  # Enable cross-volume dedup
    chunk_size: int = 4096  # Chunk size for dedup
    hash_dict: Dict[str, Set[str]] = field(default_factory=dict)  # Hash to paths mapping
    space_saved: float = 0.0  # Space saved in GB

@dataclass
class CompressionState:
    """Tracks compression state and algorithms"""
    enabled: bool = True
    algorithm: Literal["zstd", "lz4", "gzip"] = "zstd"
    level: int = 3  # Compression level
    min_size: int = 4096  # Minimum size to compress
    adaptive: bool = True  # Adapt compression based on data type
    space_saved: float = 0.0  # Space saved in GB

# Data Protection Models
@dataclass
class SnapshotState:
    """Represents the state of a snapshot."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    creation_time: datetime = field(default_factory=datetime.now)
    expiration_time: Optional[datetime] = None
    size_gb: float = 0.0
    changed_blocks: Set[int] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        """Make SnapshotState hashable."""
        return hash(self.id)

    def __eq__(self, other):
        """Compare SnapshotState objects."""
        if not isinstance(other, SnapshotState):
            return NotImplemented
        return self.id == other.id

@dataclass
class BackupState:
    """Represents the state of a backup."""
    snapshot_id: str
    completion_time: Optional[datetime] = None
    size_bytes: int = 0
    location: str = ""

@dataclass
class RecoveryPoint:
    """Represents a point in time for recovery."""
    snapshot_id: str
    backup_id: Optional[str]
    timestamp: datetime
    type: str
    name: Optional[str] = None

@dataclass
class RetentionPolicy:
    """Defines retention policy for snapshots and backups."""
    hourly_retention: int = 24  # Keep 24 hourly snapshots
    daily_retention: int = 7    # Keep 7 daily snapshots
    weekly_retention: int = 4   # Keep 4 weekly snapshots
    monthly_retention: int = 12  # Keep 12 monthly snapshots

@dataclass
class DataProtectionPolicy:
    """Defines data protection policy."""
    hourly_schedule: Optional[str] = None  # Cron expression
    daily_schedule: Optional[str] = None   # Cron expression
    weekly_schedule: Optional[str] = None  # Cron expression
    monthly_schedule: Optional[str] = None # Cron expression
    retention_policy: RetentionPolicy = field(default_factory=RetentionPolicy)

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
    snapshots: Dict[str, SnapshotState] = field(default_factory=dict)

# Data Movement and Temperature Models
@dataclass
class DataTemperature:
    """Tracks data temperature metrics"""
    access_frequency: int  # Number of accesses in measurement period
    days_since_last_access: int
    size_bytes: int
    current_tier: TierType

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
    mode: PolicyMode = PolicyMode.MANUAL
    cold_tier_after_days: int = 30
    archive_tier_after_days: int = 90
    min_object_size: int = 128 * 1024  # 128KB
    exclude_patterns: List[str] = field(default_factory=list)
    cost_threshold: float = float('inf')  # Maximum cost per GB for tiering

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

# Cloud Integration Models
@dataclass
class CloudCredentials:
    """Cloud provider credentials and configuration"""
    provider: Literal["aws", "azure", "gcp"]
    credentials: Dict[str, str]
    default_region: str
    endpoints: Dict[str, str] = field(default_factory=dict)

# System Management Models
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
