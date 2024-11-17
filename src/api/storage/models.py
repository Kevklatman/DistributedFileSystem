from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from datetime import datetime
import uuid

@dataclass
class StorageLocation:
    """Represents a storage location either on-premises or in cloud"""
    type: Literal["on_prem", "aws_s3", "azure_blob", "gcp_storage"]
    path: str
    region: Optional[str] = None  # Required for cloud locations
    availability_zone: Optional[str] = None
    performance_tier: Literal["standard", "premium"] = "standard"

@dataclass
class StoragePool:
    """Physical or cloud storage resources that can be allocated"""
    name: str
    location: StorageLocation
    total_capacity_gb: int
    available_capacity_gb: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_thin_provisioned: bool = False
    encryption_enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Volume:
    """Logical volume that can span across on-prem and cloud"""
    name: str
    size_gb: int
    primary_pool_id: str  # Reference to primary StoragePool
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cloud_backup_enabled: bool = False
    cloud_tiering_enabled: bool = False
    cloud_location: Optional[StorageLocation] = None
    encryption_at_rest: bool = True
    compression_enabled: bool = True
    deduplication_enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    
@dataclass
class CloudTieringPolicy:
    """Defines how data is tiered between on-prem and cloud"""
    volume_id: str
    target_cloud_location: StorageLocation
    cold_data_threshold_days: int = 30
    minimum_file_size_mb: int = 100
    exclude_patterns: List[str] = field(default_factory=list)
    schedule: str = "0 0 * * *"  # Default to daily at midnight

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
    
    def add_storage_pool(self, pool: StoragePool) -> None:
        self.storage_pools[pool.id] = pool
        
    def create_volume(self, name: str, size_gb: int, pool_id: str) -> Volume:
        if pool_id not in self.storage_pools:
            raise ValueError(f"Storage pool {pool_id} not found")
            
        pool = self.storage_pools[pool_id]
        if pool.available_capacity_gb < size_gb:
            raise ValueError(f"Insufficient capacity in pool {pool_id}")
            
        volume = Volume(
            name=name,
            size_gb=size_gb,
            primary_pool_id=pool_id
        )
        self.volumes[volume.id] = volume
        pool.available_capacity_gb -= size_gb
        return volume
        
    def enable_cloud_tiering(
        self, 
        volume_id: str, 
        cloud_location: StorageLocation,
        threshold_days: int = 30
    ) -> None:
        if volume_id not in self.volumes:
            raise ValueError(f"Volume {volume_id} not found")
            
        volume = self.volumes[volume_id]
        volume.cloud_tiering_enabled = True
        volume.cloud_location = cloud_location
        
        policy = CloudTieringPolicy(
            volume_id=volume_id,
            cold_data_threshold_days=threshold_days,
            target_cloud_location=cloud_location
        )
        self.tiering_policies[volume_id] = policy
