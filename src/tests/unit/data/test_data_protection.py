"""Unit tests for the DataProtectionManager."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from storage.data.data_protection import (
    DataProtectionManager,
    BackupJob,
    RetentionType
)
from storage.models import (
    Volume,
    SnapshotState,
    DataProtectionPolicy,
    RetentionPolicy,
    BackupState,
    RecoveryPoint
)

@pytest.fixture
def storage_manager(volume):
    """Mock storage manager fixture."""
    manager = Mock()

    # Configure get_volume to be async and return the volume
    async def get_volume(volume_id):
        return volume
    manager.get_volume = get_volume

    return manager

@pytest.fixture
def data_path(tmp_path):
    """Temporary data path fixture."""
    return tmp_path / "data"

@pytest.fixture
def volume():
    """Volume fixture."""
    volume = Volume(
        id="test-volume-1",
        backup_location="backup://test-bucket/test-volume-1",
        retention_policy=RetentionPolicy(
            hourly_retention=24,
            daily_retention=7,
            weekly_retention=4,
            monthly_retention=12
        )
    )
    return volume

@pytest.fixture
def protection_manager(data_path, storage_manager):
    """DataProtectionManager fixture."""
    return DataProtectionManager(data_path, storage_manager)

class TestDataProtectionManager:
    """Test suite for DataProtectionManager."""

    @pytest.mark.asyncio
    async def test_create_snapshot(self, protection_manager, volume):
        """Test snapshot creation."""
        # Create initial snapshot
        snapshot = await protection_manager.create_snapshot(volume, "test-snap-1")

        assert snapshot.id is not None
        assert snapshot.parent_id is None
        assert snapshot.metadata["name"] == "test-snap-1"
        assert snapshot.metadata["type"] == "user"
        assert snapshot.metadata["volume_id"] == volume.id
        assert snapshot.creation_time is not None

        # Create second snapshot to test parent linking
        snapshot2 = await protection_manager.create_snapshot(volume, "test-snap-2")
        assert snapshot2.parent_id == snapshot.id

    @pytest.mark.asyncio
    async def test_schedule_backups(self, protection_manager, volume):
        """Test backup scheduling."""
        policy = Mock(spec=DataProtectionPolicy)
        policy.hourly_schedule = "0 * * * *"
        policy.daily_schedule = "0 0 * * *"
        policy.weekly_schedule = "0 0 * * 0"
        policy.monthly_schedule = "0 0 1 * *"

        with patch.object(protection_manager, '_schedule_backup') as mock_schedule:
            await protection_manager.schedule_backups(volume, policy)
            assert mock_schedule.call_count == 4

    @pytest.mark.asyncio
    async def test_backup_job_execution(self, protection_manager, volume):
        """Test backup job execution."""
        snapshot = await protection_manager.create_snapshot(volume)

        job = BackupJob(
            id="test-job-1",
            volume_id=volume.id,
            snapshot_id=snapshot.id,
            target_location=volume.backup_location,
            start_time=datetime.now(),
            status="pending"
        )

        # Mock the backup data preparation and upload
        async def mock_prepare_backup_data(*args):
            return b"test_data"
        async def mock_upload_chunk(*args):
            pass

        with patch.object(protection_manager, '_prepare_backup_data', side_effect=mock_prepare_backup_data), \
             patch.object(protection_manager, '_upload_chunk', side_effect=mock_upload_chunk):
            await protection_manager._run_backup_job(job)

            assert job.status == "completed"

    @pytest.mark.asyncio
    async def test_failed_backup_job(self, protection_manager, volume):
        """Test backup job failure handling."""
        snapshot = await protection_manager.create_snapshot(volume)

        job = BackupJob(
            id="test-job-2",
            volume_id=volume.id,
            snapshot_id=snapshot.id,
            target_location=volume.backup_location,
            start_time=datetime.now(),
            status="pending"
        )

        # Mock the backup data preparation to fail
        async def mock_prepare_backup_data(*args):
            raise Exception("Backup failed")

        with patch.object(protection_manager, '_prepare_backup_data', side_effect=mock_prepare_backup_data):
            await protection_manager._run_backup_job(job)

            assert job.status == "failed"
            assert job.error == "Backup failed"

    @pytest.mark.asyncio
    async def test_restore_volume(self, protection_manager, volume, tmp_path):
        """Test volume restoration."""
        recovery_point = Mock(spec=RecoveryPoint)
        recovery_point.backup_id = "test-backup-1"
        recovery_point.snapshot_id = "test-snap-1"

        volume.backups["test-backup-1"] = Mock(spec=BackupState)
        volume.snapshots["test-snap-1"] = Mock(spec=SnapshotState)

        with patch.object(protection_manager, '_validate_recovery_point', return_value=True), \
             patch.object(protection_manager, '_download_backup'), \
             patch.object(protection_manager, '_restore_data'), \
             patch.object(protection_manager, '_swap_volume_data'):

            await protection_manager.restore_volume(volume, recovery_point, tmp_path)
            # If no exception is raised, the test passes

    @pytest.mark.asyncio
    async def test_retention_policy(self, protection_manager, volume):
        """Test retention policy application."""
        # Create snapshots with different ages
        now = datetime.now()

        # Hourly snapshots
        for i in range(5):
            snapshot = SnapshotState(
                parent_id=None,
                metadata={"type": "scheduled", "name": f"hourly-{i}"}
            )
            snapshot.creation_time = now - timedelta(hours=i)
            volume.snapshots[snapshot.id] = snapshot

        # Daily snapshots
        for i in range(3):
            snapshot = SnapshotState(
                parent_id=None,
                metadata={"type": "scheduled", "name": f"daily-{i}"}
            )
            snapshot.creation_time = now - timedelta(days=i+1)
            volume.snapshots[snapshot.id] = snapshot

        # Set retention policy
        volume.retention_policy.hourly_retention = 3
        volume.retention_policy.daily_retention = 2

        with patch.object(protection_manager, '_delete_snapshot_and_backup'):
            await protection_manager._apply_retention_policy(volume)
            # Should delete 2 hourly and 1 daily snapshots

    def test_recovery_points(self, protection_manager, volume):
        """Test recovery points management."""
        snapshot = SnapshotState(
            parent_id=None,
            metadata={"type": "user", "name": "test-snap"}
        )

        protection_manager._update_recovery_points(volume, snapshot)

        recovery_points = protection_manager.get_recovery_points(volume)
        assert len(recovery_points) == 1
        assert recovery_points[0].snapshot_id == snapshot.id
        assert recovery_points[0].type == "user"
        assert recovery_points[0].name == "test-snap"

    def test_validate_recovery_point(self, protection_manager, volume):
        """Test recovery point validation."""
        # Valid recovery point
        snapshot = SnapshotState(parent_id=None)
        volume.snapshots[snapshot.id] = snapshot

        backup = BackupState(snapshot_id=snapshot.id)
        volume.backups["test-backup"] = backup

        recovery_point = RecoveryPoint(
            snapshot_id=snapshot.id,
            backup_id="test-backup",
            timestamp=datetime.now(),
            type="user"
        )

        assert protection_manager._validate_recovery_point(volume, recovery_point)

        # Invalid recovery point
        invalid_recovery_point = RecoveryPoint(
            snapshot_id="non-existent",
            backup_id="non-existent",
            timestamp=datetime.now(),
            type="user"
        )

        assert not protection_manager._validate_recovery_point(volume, invalid_recovery_point)
