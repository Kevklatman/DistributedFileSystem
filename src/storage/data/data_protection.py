"""
Enterprise data protection with snapshots, backups, and rapid recovery
"""
import os
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import asyncio
import logging
import json
import hashlib
from enum import Enum

from models import (
    Volume,
    SnapshotState,
    DataProtectionPolicy,
    RetentionPolicy,
    BackupState,
    RecoveryPoint
)

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

class DataProtectionManager:
    """Manages data protection features including snapshots, backups, and recovery"""

    def __init__(self, data_path: Path, storage_manager):
        self.data_path = data_path
        self.storage_manager = storage_manager
        self.logger = logging.getLogger(__name__)
        self.active_backups: Dict[str, BackupJob] = {}
        self.recovery_points: Dict[str, List[RecoveryPoint]] = {}

    async def create_snapshot(self, volume: Volume, name: str = None,
                            snapshot_type: str = "user") -> SnapshotState:
        """Create a new snapshot"""
        # Get parent snapshot if exists
        parent_id = self._get_latest_snapshot_id(volume)

        # Create new snapshot
        snapshot = SnapshotState(
            parent_id=parent_id,
            metadata={
                "name": name,
                "type": snapshot_type,
                "volume_id": volume.id
            }
        )

        # Track changed blocks since parent
        if parent_id:
            parent = volume.snapshots[parent_id]
            snapshot.changed_blocks = await self._get_changed_blocks(
                volume,
                parent.creation_time
            )

        # Add to volume
        volume.snapshots[snapshot.id] = snapshot

        # Update recovery points
        self._update_recovery_points(volume, snapshot)

        # Apply retention policy
        await self._apply_retention_policy(volume)

        return snapshot

    async def schedule_backups(self, volume: Volume,
                             policy: DataProtectionPolicy) -> None:
        """Schedule backups according to policy"""
        # Schedule different backup types
        schedules = [
            (policy.hourly_schedule, RetentionType.HOURLY),
            (policy.daily_schedule, RetentionType.DAILY),
            (policy.weekly_schedule, RetentionType.WEEKLY),
            (policy.monthly_schedule, RetentionType.MONTHLY)
        ]

        for schedule, retention_type in schedules:
            if schedule:
                await self._schedule_backup(volume, schedule, retention_type)

    async def _schedule_backup(self, volume: Volume, schedule: str,
                             retention_type: RetentionType) -> None:
        """Schedule a specific backup"""
        # Parse schedule and create backup job
        snapshot = await self.create_snapshot(
            volume,
            name=f"scheduled_{retention_type.value}",
            snapshot_type="scheduled"
        )

        job = BackupJob(
            id=f"backup_{volume.id}_{datetime.now().isoformat()}",
            volume_id=volume.id,
            snapshot_id=snapshot.id,
            target_location=volume.backup_location,
            start_time=datetime.now(),
            status="pending"
        )

        self.active_backups[job.id] = job
        asyncio.create_task(self._run_backup_job(job))

    async def _run_backup_job(self, job: BackupJob) -> None:
        """Execute a backup job"""
        try:
            job.status = "running"
            volume = self.storage_manager.get_volume(job.volume_id)
            snapshot = volume.snapshots[job.snapshot_id]

            # Prepare backup data
            backup_data = await self._prepare_backup_data(volume, snapshot)

            # Upload to backup location with progress tracking
            total_size = len(backup_data)
            uploaded = 0

            for chunk in self._split_into_chunks(backup_data):
                await self._upload_chunk(chunk, job.target_location)
                uploaded += len(chunk)
                job.progress = uploaded / total_size

            # Create backup state
            backup_state = BackupState(
                snapshot_id=snapshot.id,
                completion_time=datetime.now(),
                size_bytes=total_size,
                location=job.target_location
            )

            volume.backups[job.id] = backup_state
            job.status = "completed"

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            self.logger.error(f"Backup job {job.id} failed: {str(e)}")

    async def restore_volume(self, volume: Volume, recovery_point: RecoveryPoint,
                           target_path: Optional[Path] = None) -> None:
        """Restore volume from a recovery point"""
        try:
            # Validate recovery point
            if not self._validate_recovery_point(volume, recovery_point):
                raise ValueError("Invalid recovery point")

            # Determine restore location
            restore_path = target_path or self.data_path / volume.id / "restore"
            os.makedirs(restore_path, exist_ok=True)

            # Get backup data
            backup_state = volume.backups[recovery_point.backup_id]
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
            RetentionType.MONTHLY: []
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

    async def _delete_snapshot_and_backup(self, volume: Volume,
                                        snapshot: SnapshotState) -> None:
        """Delete a snapshot and its associated backup"""
        # Find associated backup
        backup_id = None
        for bid, backup in volume.backups.items():
            if backup.snapshot_id == snapshot.id:
                backup_id = bid
                break

        # Delete backup if exists
        if backup_id:
            await self._delete_backup(volume, backup_id)
            del volume.backups[backup_id]

        # Delete snapshot
        del volume.snapshots[snapshot.id]

    async def _delete_backup(self, volume: Volume, backup_id: str) -> None:
        """Delete a backup from storage"""
        backup = volume.backups[backup_id]
        # Implementation would delete from backup storage
        pass

    def _update_recovery_points(self, volume: Volume,
                              snapshot: SnapshotState) -> None:
        """Update available recovery points"""
        if volume.id not in self.recovery_points:
            self.recovery_points[volume.id] = []

        recovery_point = RecoveryPoint(
            snapshot_id=snapshot.id,
            backup_id=None,  # Will be updated when backup completes
            timestamp=snapshot.creation_time,
            type=snapshot.metadata.get("type", "user"),
            name=snapshot.metadata.get("name")
        )

        self.recovery_points[volume.id].append(recovery_point)

    def _validate_recovery_point(self, volume: Volume,
                               recovery_point: RecoveryPoint) -> bool:
        """Validate a recovery point"""
        # Check if snapshot exists
        if recovery_point.snapshot_id not in volume.snapshots:
            return False

        # Check if backup exists and is valid
        if recovery_point.backup_id:
            if recovery_point.backup_id not in volume.backups:
                return False

            backup = volume.backups[recovery_point.backup_id]
            if backup.snapshot_id != recovery_point.snapshot_id:
                return False

        return True

    @staticmethod
    def _split_into_chunks(data: bytes, chunk_size: int = 1024*1024) -> List[bytes]:
        """Split data into chunks"""
        return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

    async def _prepare_backup_data(self, volume: Volume,
                                 snapshot: SnapshotState) -> bytes:
        """Prepare data for backup"""
        # Implementation would gather and prepare data
        # For now, return dummy data
        return b"backup_data"

    async def _upload_chunk(self, chunk: bytes, target_location: str) -> None:
        """Upload a chunk to backup storage"""
        # Implementation would handle actual upload
        pass

    async def _download_backup(self, backup_state: BackupState) -> bytes:
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
        temp_path = volume_path.with_suffix('.old')

        # Atomic swap
        os.rename(volume_path, temp_path)
        os.rename(restore_path, volume_path)
        # Keep old data for safety
        # os.remove(temp_path)
