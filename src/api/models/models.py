from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Set
from datetime import datetime
import uuid
from enum import Enum

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

@dataclass
class DataTemperature:
    """Tracks data temperature metrics"""
    access_frequency: int  # Number of accesses in measurement period
    days_since_last_access: int
    size_bytes: int
    current_tier: TierType

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
    dedup_state: DeduplicationState = field(default_factory=DeduplicationState)
    compression_state: CompressionState = field(default_factory=CompressionState)
    created_at: datetime = field(default_factory=datetime.now)

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
class Volume:
    """Logical volume that can span across on-prem and cloud"""
    name: str
    size_gb: int
    primary_pool_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cloud_backup_enabled: bool = False
    cloud_tiering_enabled: bool = False
    cloud_location: Optional[StorageLocation] = None
    encryption_at_rest: bool = True
    compression_enabled: bool = True
    deduplication_enabled: bool = True
    data_temperature: Dict[str, DataTemperature] = field(default_factory=dict)
    tiering_policy: TieringPolicy = field(default_factory=lambda: TieringPolicy())
    created_at: datetime = field(default_factory=datetime.now)

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
    cost_threshold_per_gb: float = 0.05  # Maximum cost per GB for tiering
    access_pattern_weight: float = 0.3  # Weight for access pattern in decisions
    prediction_weight: float = 0.2  # Weight for predicted access in decisions
    exclude_patterns: List[str] = field(default_factory=list)
    schedule: str = "0 0 * * *"  # Default to daily at midnight

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
class SnapshotState:
    """Tracks snapshot state and chain"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    creation_time: datetime = field(default_factory=datetime.now)
    expiration_time: Optional[datetime] = None
    size_gb: float = 0.0
    changed_blocks: Set[int] = field(default_factory=set)
    metadata: Dict[str, str] = field(default_factory=dict)

@dataclass
class DataProtection:
    """Defines data protection policies across hybrid environment"""
    volume_id: str
    local_snapshot_enabled: bool = True
    local_snapshot_schedule: str = "0 * * * *"  # Hourly
    local_snapshot_retention_days: int = 7
    cloud_backup_enabled: bool = False
    cloud_backup_schedule: str = "0 0 * * *"  # Daily
    cloud_backup_retention_days: int = 30
    disaster_recovery_enabled: bool = False
    dr_location: Optional[StorageLocation] = None
    snapshots: Dict[str, SnapshotState] = field(default_factory=dict)

@dataclass
class CloudCredentials:
    """Cloud provider credentials and configuration"""
    provider: Literal["aws", "azure", "gcp"]
    credentials: Dict[str, str]  # Encrypted credentials
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

    def add_storage_pool(self, pool: StoragePool) -> None:
        self.storage_pools[pool.id] = pool

    def create_volume(self, name: str, size_gb: int, pool_id: str) -> Volume:
        if pool_id not in self.storage_pools:
            raise ValueError(f"Storage pool {pool_id} not found")

        pool = self.storage_pools[pool_id]
        if not pool.is_thin_provisioned and pool.available_capacity_gb < size_gb:
            raise ValueError(f"Insufficient capacity in pool {pool_id}")

        volume = Volume(
            name=name,
            size_gb=size_gb,
            primary_pool_id=pool_id
        )
        self.volumes[volume.id] = volume

        if not pool.is_thin_provisioned:
            pool.available_capacity_gb -= size_gb

        return volume
