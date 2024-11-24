"""Advanced storage features service."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

from storage.infrastructure.storage_efficiency import StorageEfficiencyManager
from storage.infrastructure.data.data_protection import DataProtectionManager
from storage.infrastructure.hybrid_api import HybridStorageManager
from src.models.models import (
    Volume,
    StoragePool,
    StorageLocation,
    SnapshotState,
    DataProtectionPolicy,
    RetentionPolicy
)

logger = logging.getLogger(__name__)

class AdvancedStorageService:
    """Service for managing advanced storage features."""
    
    def __init__(self, storage_root: str):
        """Initialize advanced storage features."""
        self.storage_root = Path(storage_root)
        self.efficiency_manager = StorageEfficiencyManager(self.storage_root / 'efficiency')
        self.hybrid_storage = HybridStorageManager(storage_root)
        self.data_protection = DataProtectionManager(
            self.storage_root / 'protection',
            self.hybrid_storage
        )
        
    def create_volume(self, name: str, size_gb: int, pool_id: str,
                     dedup: bool = False, compression: bool = False,
                     cloud_backup: bool = False) -> Volume:
        """Create a new volume with specified features."""
        volume = self.hybrid_storage.create_volume(name, size_gb, pool_id)
        
        if dedup or compression:
            self.efficiency_manager.configure_volume(
                volume,
                deduplication_enabled=dedup,
                compression_enabled=compression
            )
            
        if cloud_backup:
            policy = DataProtectionPolicy(
                backup_enabled=True,
                retention=RetentionPolicy(
                    hourly=24,
                    daily=7,
                    weekly=4,
                    monthly=12
                )
            )
            self.data_protection.set_protection_policy(volume.id, policy)
            
        return volume
        
    def write_file(self, volume_id: str, file_path: str, data: bytes) -> bool:
        """Write a file with efficiency features."""
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
        
    def read_file(self, volume_id: str, file_path: str) -> Optional[bytes]:
        """Read a file with efficiency features."""
        return self.hybrid_storage.read_file(volume_id, file_path)
        
    def create_snapshot(self, volume_id: str, name: str) -> str:
        """Create a volume snapshot."""
        return self.data_protection.create_snapshot(volume_id, name)
        
    def restore_snapshot(self, volume_id: str, snapshot_id: str) -> bool:
        """Restore from a snapshot."""
        return self.data_protection.restore_snapshot(volume_id, snapshot_id)
        
    def create_backup(self, volume_id: str, target_location: str) -> str:
        """Create a backup to specified location."""
        return self.data_protection.create_backup(volume_id, target_location)
        
    def restore_backup(self, volume_id: str, backup_id: str) -> bool:
        """Restore from a backup."""
        return self.data_protection.restore_backup(volume_id, backup_id)
        
    def get_efficiency_stats(self, volume_id: str) -> Dict:
        """Get storage efficiency statistics."""
        volume = self.hybrid_storage.get_volume(volume_id)
        stats = {
            'deduplication': self.efficiency_manager.get_dedup_stats(volume),
            'compression': self.efficiency_manager.get_compression_stats(volume),
            'thin_provisioning': self.efficiency_manager.get_thin_provision_stats(volume)
        }
        return stats
        
    def get_protection_status(self, volume_id: str) -> Dict:
        """Get data protection status."""
        return {
            'snapshots': self.data_protection.list_snapshots(volume_id),
            'backups': self.data_protection.list_backups(volume_id),
            'policy': self.data_protection.get_protection_policy(volume_id),
            'last_backup': self.data_protection.get_last_backup(volume_id),
            'recovery_points': self.data_protection.list_recovery_points(volume_id)
        }
