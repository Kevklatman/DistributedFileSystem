"""Storage-related models for the distributed file system."""
from dataclasses import dataclass, field
from typing import Dict, Set
from datetime import datetime
import uuid

from .base import StorageLocation, Volume

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
    algorithm: str = "zstd"
    level: int = 3  # Compression level
    min_size: int = 4096  # Minimum size to compress
    adaptive: bool = True  # Adapt compression based on data type
    space_saved: float = 0.0  # Space saved in GB

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
    oversubscription_ratio: float = 1.0
    dedup_state: DeduplicationState = field(default_factory=DeduplicationState)
    compression_state: CompressionState = field(default_factory=CompressionState)
    created_at: datetime = field(default_factory=datetime.now)
    volumes: Dict[str, Volume] = field(default_factory=dict)

    def __post_init__(self):
        if self.volumes is None:
            self.volumes = {}
