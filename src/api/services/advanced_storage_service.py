"""Advanced storage features service."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

from src.storage.infrastructure.storage_efficiency import StorageEfficiencyManager
from src.storage.infrastructure.data.data_protection import DataProtectionManager
from src.storage.infrastructure.hybrid_api import HybridStorageManager
from src.models.models import (
    Volume,
    StoragePool,
    StorageLocation,
    SnapshotState,
    DataProtectionPolicy,
    RetentionPolicy,
)

logger = logging.getLogger(__name__)


class AdvancedStorageService:
    """Service for managing advanced storage features."""

    def __init__(self, storage_root: str):
        """Initialize advanced storage features."""
        self.storage_root = Path(storage_root)
        self.efficiency_manager = StorageEfficiencyManager(
            self.storage_root / "efficiency"
        )
        self.hybrid_storage = HybridStorageManager(storage_root)
        self.data_protection = DataProtectionManager(
            self.storage_root / "protection", self.hybrid_storage
        )

    def create_volume(
        self,
        name: str,
        size_gb: int,
        pool_id: str,
        dedup: bool = False,
        compression: bool = False,
        cloud_backup: bool = False,
    ) -> Volume:
        """Create a new volume with specified features."""
        try:
            # Create storage pool directory if it doesn't exist
            pool_path = self.storage_root / "pools" / pool_id
            pool_path.mkdir(parents=True, exist_ok=True)
            
            # Create volume
            volume = self.hybrid_storage.create_volume(name, size_gb, pool_id)

            if dedup or compression:
                self.efficiency_manager.configure_volume(
                    volume, deduplication_enabled=dedup, compression_enabled=compression
                )

            if cloud_backup:
                policy = DataProtectionPolicy(
                    backup_enabled=True,
                    retention=RetentionPolicy(hourly=24, daily=7, weekly=4, monthly=12),
                )
                self.data_protection.set_protection_policy(volume.id, policy)

            return volume
        except Exception as e:
            logger.error(f"Failed to create volume: {str(e)}")
            raise

    def write_file(self, volume_id: str, file_path: str, data: bytes) -> bool:
        """Write a file with efficiency features."""
        try:
            # Write file through hybrid storage
            success = self.hybrid_storage.write_file(volume_id, file_path, data)
            if not success:
                return False

            # Apply efficiency features
            volume = self.hybrid_storage.get_volume(volume_id)
            if volume.deduplication_enabled:
                self.efficiency_manager.deduplicate_file(volume, file_path)
            if volume.compression_enabled:
                self.efficiency_manager.compress_file(volume, file_path)

            return True
        except Exception as e:
            logger.error(f"Failed to write file: {str(e)}")
            raise

    def read_file(self, volume_id: str, file_path: str) -> Optional[bytes]:
        """Read a file with efficiency features."""
        try:
            return self.hybrid_storage.read_file(volume_id, file_path)
        except Exception as e:
            logger.error(f"Failed to read file: {str(e)}")
            raise

    def create_snapshot(self, volume_id: str, name: str) -> str:
        """Create a volume snapshot."""
        try:
            return self.data_protection.create_snapshot(volume_id, name)
        except Exception as e:
            logger.error(f"Failed to create snapshot: {str(e)}")
            raise

    def restore_snapshot(self, volume_id: str, snapshot_id: str) -> bool:
        """Restore from a snapshot."""
        try:
            volume = self.hybrid_storage.get_volume(volume_id)
            if not volume:
                raise ValueError(f"Volume {volume_id} not found")
                
            return self.data_protection.restore_snapshot(volume_id, snapshot_id)
        except Exception as e:
            logger.error(f"Failed to restore snapshot: {str(e)}")
            raise

    def create_backup(self, volume_id: str, target_location: str) -> str:
        """Create a backup to specified location."""
        try:
            return self.data_protection.create_backup(volume_id, target_location)
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            raise

    def restore_backup(self, volume_id: str, backup_id: str) -> bool:
        """Restore from a backup."""
        try:
            volume = self.hybrid_storage.get_volume(volume_id)
            if not volume:
                raise ValueError(f"Volume {volume_id} not found")
                
            return self.data_protection.restore_backup(volume_id, backup_id)
        except Exception as e:
            logger.error(f"Failed to restore backup: {str(e)}")
            raise

    def get_efficiency_stats(self, volume_id: str) -> Dict:
        """Get storage efficiency statistics."""
        try:
            volume = self.hybrid_storage.get_volume(volume_id)
            if not volume:
                raise ValueError(f"Volume {volume_id} not found")
                
            return {
                "deduplication_ratio": self.efficiency_manager.get_dedup_ratio(volume),
                "compression_ratio": self.efficiency_manager.get_compression_ratio(volume),
                "total_savings": self.efficiency_manager.get_total_savings(volume),
            }
        except Exception as e:
            logger.error(f"Failed to get efficiency stats: {str(e)}")
            raise

    def get_protection_status(self, volume_id: str) -> Dict:
        """Get data protection status."""
        try:
            volume = self.hybrid_storage.get_volume(volume_id)
            if not volume:
                raise ValueError(f"Volume {volume_id} not found")
                
            return {
                "snapshots": self.data_protection.list_snapshots(volume_id),
                "backups": self.data_protection.list_backups(volume_id),
                "policy": self.data_protection.get_protection_policy(volume_id),
            }
        except Exception as e:
            logger.error(f"Failed to get protection status: {str(e)}")
            raise
