"""Data models for the distributed file system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Any, List
from pathlib import Path
import uuid

@dataclass(frozen=True)  # Make the class immutable
class Volume:
    """Represents a storage volume."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    snapshots: Dict[str, 'SnapshotState'] = field(default_factory=dict)
    backups: Dict[str, 'BackupState'] = field(default_factory=dict)
    backup_location: str = ""
    retention_policy: Optional['RetentionPolicy'] = None

    def __getitem__(self, key):
        """Support dictionary-like access to snapshots."""
        return self.snapshots[key]

    def __setitem__(self, key, value):
        """Support dictionary-like assignment to snapshots."""
        self.snapshots[key] = value

@dataclass  # Remove frozen=True to allow modification in tests
class SnapshotState:
    """Represents the state of a snapshot."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    creation_time: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    changed_blocks: List[str] = field(default_factory=list)

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
