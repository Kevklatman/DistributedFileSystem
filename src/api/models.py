"""Data models for the distributed file system."""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class DataTemperature(Enum):
    """Data temperature for tiering decisions."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"

@dataclass
class StorageLocation:
    """Storage location configuration."""
    node_id: str
    path: str
    size_bytes: int
    replicas: List[str]
    temperature: DataTemperature
    cloud_provider: Optional[str] = None
    cloud_region: Optional[str] = None
    cloud_bucket: Optional[str] = None

@dataclass
class Volume:
    """Volume configuration."""
    id: str
    name: str
    size_gb: int
    primary_pool_id: str
    cloud_tiering: bool = False
    created_at: datetime = datetime.now()
    metadata: Dict[str, Any] = None

@dataclass
class StoragePool:
    """Storage pool configuration."""
    id: str
    name: str
    location: StorageLocation
    capacity_gb: int
    used_gb: int = 0
    volumes: Dict[str, Volume] = None

    def __post_init__(self):
        if self.volumes is None:
            self.volumes = {}
