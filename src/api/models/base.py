"""Base models for the distributed file system."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Set, Any
from datetime import datetime
import uuid
from enum import Enum

class DataTemperature(Enum):
    """Data temperature for tiering decisions."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"

class TierType(Enum):
    """Storage tier types."""
    PERFORMANCE = "performance"  # NVMe/SSD
    CAPACITY = "capacity"      # HDD
    COLD = "cold"             # S3/Azure Blob
    ARCHIVE = "archive"       # Glacier/Archive

@dataclass
class StorageLocation:
    """Represents a storage location either on-premises or in cloud"""
    type: Literal["on_prem", "aws_s3", "azure_blob", "gcp_storage"]
    path: str
    node_id: str
    size_bytes: int
    replicas: List[str]
    temperature: DataTemperature
    region: Optional[str] = None
    availability_zone: Optional[str] = None
    performance_tier: Literal["premium_ssd", "standard_ssd", "standard_hdd", "archive"] = "standard_ssd"
    cost_per_gb: float = 0.0
    cloud_provider: Optional[str] = None
    cloud_region: Optional[str] = None
    cloud_bucket: Optional[str] = None

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
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
