"""
Enterprise data protection with snapshots, backups, and rapid recovery
"""

import os
from typing import Dict, List, Optional, Set, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import asyncio
import logging
import json
import hashlib
from enum import Enum

from src.models.models import (
    Volume,
    SnapshotState,
    DataProtectionPolicy,
    RetentionPolicy,
    BackupState,
    RecoveryPoint,
)

logger = logging.getLogger(__name__)


class RetentionType(Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass
class BackupJob:
    """Represents a backup job"""

    id: str
    volume_id: str
    snapshot_id: str
    target_location: str
    start_time: datetime
    status: str
    progress: float = 0.0
    error: Optional[str] = None
    completion_time: Optional[datetime] = None


class DataProtectionManager:
    """Manages data protection features including snapshots, backups, and recovery"""

    def __init__(self, data_path: Union[str, Path], storage_manager):
        # Convert string path to Path object if necessary
        self.data_path = Path(data_path) if isinstance(data_path, str) else data_path
        self.storage_manager = storage_manager
        self.active_backups: Dict[str, BackupJob] = {}
        self._initialized = False
        self._backup_path = self.data_path / "backups"
        self._snapshot_path = self.data_path / "snapshots"
        self._metadata_path = self.data_path / "metadata"
        self.logger = logging.getLogger(__name__)
        self.recovery_points: Dict[str, List[RecoveryPoint]] = {}

    def initialize(
        self,
        backup_retention_days: int = 30,
        snapshot_retention_days: int = 7,
        auto_backup_enabled: bool = True,
    ) -> bool:
        """Initialize the data protection system.

        Args:
            backup_retention_days: Number of days to retain backups
            snapshot_retention_days: Number of days to retain snapshots
            auto_backup_enabled: Whether to enable automatic backups

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Create necessary directories
            os.makedirs(self._backup_path, exist_ok=True)
            os.makedirs(self._snapshot_path, exist_ok=True)
            os.makedirs(self._metadata_path, exist_ok=True)

            # Initialize protection policies
            self.backup_retention_days = backup_retention_days
            self.snapshot_retention_days = snapshot_retention_days
            self.auto_backup_enabled = auto_backup_enabled

            # Create default retention policy
            default_policy = {
                "backup_retention_days": backup_retention_days,
                "snapshot_retention_days": snapshot_retention_days,
                "auto_backup_enabled": auto_backup_enabled,
                "retention_types": {
                    RetentionType.HOURLY.value: 24,  # Keep 24 hourly backups
                    RetentionType.DAILY.value: 7,  # Keep 7 daily backups
                    RetentionType.WEEKLY.value: 4,  # Keep 4 weekly backups
                    RetentionType.MONTHLY.value: 12,  # Keep 12 monthly backups
                },
            }

            # Save default policy
            policy_file = self._metadata_path / "protection_policy.json"
            with open(policy_file, "w") as f:
                json.dump(default_policy, f, indent=4)

            self._initialized = True
            logger.info("Data protection manager initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize data protection manager: {str(e)}")
            return False

    async def create_snapshot(
        self, volume: Volume, name: str = None, snapshot_type: str = "user"
    ) -> SnapshotState:
        """Create a new snapshot"""
        # Get parent snapshot if exists
        parent_id = self._get_latest_snapshot_id(volume)

        # Create new snapshot
        snapshot = SnapshotState(
            parent_id=parent_id,
            metadata={"name": name, "type": snapshot_type, "volume_id": volume.id},
        )

        # Track changed blocks since parent
        if parent_id:
            parent = volume.snapshots[parent_id]
            snapshot.changed_blocks = await self._get_changed_blocks(
                volume, parent.creation_time
            )

        # Add to volume
        volume.snapshots[snapshot.id] = snapshot

        # Update recovery points
        self._update_recovery_points(volume, snapshot)

        # Apply retention policy
        await self._apply_retention_policy(volume)

        return snapshot

    async def schedule_backups(
        self, volume: Volume, policy: DataProtectionPolicy
    ) -> None:
        """Schedule backups according to policy"""
        # Schedule different backup types
        schedules = [
            (policy.hourly_schedule, RetentionType.HOURLY),
            (policy.daily_schedule, RetentionType.DAILY),
            (policy.weekly_schedule, RetentionType.WEEKLY),
            (policy.monthly_schedule, RetentionType.MONTHLY),
        ]

        for schedule, retention_type in schedules:
            if schedule:
                await self._schedule_backup(volume, schedule, retention_type)

    async def _schedule_backup(
        self, volume: Volume, schedule: str, retention_type: RetentionType
    ) -> None:
        """Schedule a specific backup"""
        # Parse schedule and create backup job
        snapshot = await self.create_snapshot(
            volume, name=f"scheduled_{retention_type.value}", snapshot_type="scheduled"
        )

        job = BackupJob(
            id=f"backup_{volume.id}_{datetime.now().isoformat()}",
            volume_id=volume.id,
            snapshot_id=snapshot.id,
            target_location=volume.backup_location,
            start_time=datetime.now(),
            status="pending",
        )

        self.active_backups[job.id] = job
        asyncio.create_task(self._run_backup_job(job))

    async def _run_backup_job(self, job: BackupJob) -> None:
        """Execute a backup job"""
        try:
            job.status = "running"
            volume = await self.storage_manager.get_volume(job.volume_id)
            snapshot = volume.snapshots[job.snapshot_id]

            # Prepare backup data
            data = await self._prepare_backup_data(snapshot)

            # Upload backup data
            await self._upload_chunk(job.target_location, data)

            # Mark job as completed
            job.status = "completed"
            job.completion_time = datetime.now()

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            self.logger.error(f"Backup job {job.id} failed: {str(e)}")

    async def restore_volume(
        self,
        volume: Volume,
        recovery_point: RecoveryPoint,
        target_path: Optional[Path] = None,
    ) -> None:
        """Restore volume from a recovery point"""
        try:
            # Validate recovery point
            if not self._validate_recovery_point(volume, recovery_point):
                raise ValueError("Invalid recovery point")

            # Determine restore location
            restore_path = target_path or self.data_path / volume.id / "restore"
            os.makedirs(restore_path, exist_ok=True)

            # Get backup data from snapshots (since backups are stored as snapshots)
            backup_state = volume.snapshots[recovery_point.backup_id]
            backup_data = await self._download_backup(backup_state)

            # Perform restore
            await self._restore_data(backup_data, restore_path)

            # If restoring to original location, replace volume data
            if not target_path:
                await self._swap_volume_data(volume, restore_path)

        except Exception as e:
            self.logger.error(f"Restore failed: {str(e)}")
            raise

    def get_recovery_points(self, volume: Volume) -> List[RecoveryPoint]:
        """Get available recovery points for a volume"""
        return self.recovery_points.get(volume.id, [])

    async def _apply_retention_policy(self, volume: Volume) -> None:
        """Apply retention policy to snapshots and backups"""
        if not volume.retention_policy:
            return

        policy = volume.retention_policy
        now = datetime.now()

        # Group snapshots by type
        snapshots_by_type = {
            RetentionType.HOURLY: [],
            RetentionType.DAILY: [],
            RetentionType.WEEKLY: [],
            RetentionType.MONTHLY: [],
        }

        for snapshot in volume.snapshots.values():
            if snapshot.metadata.get("type") == "scheduled":
                age = now - snapshot.creation_time

                if age < timedelta(days=1):
                    snapshots_by_type[RetentionType.HOURLY].append(snapshot)
                elif age < timedelta(days=7):
                    snapshots_by_type[RetentionType.DAILY].append(snapshot)
                elif age < timedelta(days=30):
                    snapshots_by_type[RetentionType.WEEKLY].append(snapshot)
                else:
                    snapshots_by_type[RetentionType.MONTHLY].append(snapshot)

        # Apply retention limits
        to_delete = set()

        for retention_type, snapshots in snapshots_by_type.items():
            limit = getattr(policy, f"{retention_type.value}_retention")
            if limit and len(snapshots) > limit:
                # Keep most recent up to limit
                to_delete.update(
                    sorted(snapshots, key=lambda s: s.creation_time)[:-limit]
                )

        # Delete expired snapshots and their backups
        for snapshot in to_delete:
            await self._delete_snapshot_and_backup(volume, snapshot)

    async def _delete_snapshot_and_backup(
        self, volume: Volume, snapshot: SnapshotState
    ) -> None:
        """Delete a snapshot and its associated backup"""
        # Since backups are stored as snapshots, we just need to delete the snapshot
        del volume.snapshots[snapshot.id]

    async def _delete_backup(self, volume: Volume, backup_id: str) -> None:
        """Delete a backup from storage"""
        # Since backups are stored as snapshots, we delete from snapshots
        if backup_id in volume.snapshots:
            del volume.snapshots[backup_id]

    async def _get_changed_blocks(self, volume: Volume, since: datetime) -> List[str]:
        """Get list of blocks that have changed since the given time."""
        # In a real implementation, this would query the storage system
        # For testing, we'll return a dummy list
        return ["block1", "block2"]

    def _update_recovery_points(self, volume: Volume, snapshot: SnapshotState) -> None:
        """Update available recovery points"""
        if volume.id not in self.recovery_points:
            self.recovery_points[volume.id] = []

        recovery_point = RecoveryPoint(
            snapshot_id=snapshot.id,
            backup_id=None,  # Will be updated when backup completes
            timestamp=snapshot.creation_time,
            type=snapshot.metadata.get("type", "user"),
            name=snapshot.metadata.get("name"),
        )

        self.recovery_points[volume.id].append(recovery_point)

    def _validate_recovery_point(
        self, volume: Volume, recovery_point: RecoveryPoint
    ) -> bool:
        """Validate a recovery point"""
        # Check if snapshot exists
        if recovery_point.snapshot_id not in volume.snapshots:
            return False

        # Check if backup exists and is valid (stored as a snapshot)
        if recovery_point.backup_id:
            if recovery_point.backup_id not in volume.snapshots:
                return False

            backup = volume.snapshots[recovery_point.backup_id]
            if backup.snapshot_id != recovery_point.snapshot_id:
                return False

        return True

    def _get_latest_snapshot_id(self, volume: Volume) -> Optional[str]:
        """Get the ID of the latest snapshot for a volume."""
        if not volume.snapshots:
            return None

        latest = max(volume.snapshots.values(), key=lambda s: s.creation_time)
        return latest.id

    @staticmethod
    def _split_into_chunks(data: bytes, chunk_size: int = 1024 * 1024) -> List[bytes]:
        """Split data into chunks"""
        return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]

    async def _prepare_backup_data(self, snapshot: SnapshotState) -> bytes:
        """Prepare data for backup"""
        # Implementation would gather and prepare data
        # For now, return dummy data
        return b"backup_data"

    async def _upload_chunk(self, target_location: str, chunk: bytes) -> None:
        """Upload a chunk to backup storage"""
        # Implementation would handle actual upload
        pass

    async def _download_backup(self, backup_state: SnapshotState) -> bytes:
        """Download backup data"""
        # Implementation would download from backup storage
        # For now, return dummy data
        return b"restored_data"

    async def _restore_data(self, data: bytes, target_path: Path) -> None:
        """Restore data to target path"""
        # Implementation would handle actual restore
        pass

    async def _swap_volume_data(self, volume: Volume, restore_path: Path) -> None:
        """Swap restored data with volume data"""
        volume_path = self.data_path / volume.id
        temp_path = volume_path.with_suffix(".old")

        # Atomic swap
        os.rename(volume_path, temp_path)
        os.rename(restore_path, volume_path)
        # Keep old data for safety
        # os.remove(temp_path)
