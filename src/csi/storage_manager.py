from typing import Optional, Dict
import os
from pathlib import Path
import sys

# Add parent directory to path to import storage modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.storage.core.hybrid_storage import HybridStorageManager
from src.api.models import StorageLocation, Volume

class CSIStorageManager:
    """Storage Manager for CSI Driver Integration"""

    def __init__(self):
        self.storage_manager = HybridStorageManager("/data/dfs")
        self._ensure_csi_pool()

    def _ensure_csi_pool(self):
        """Ensure CSI storage pool exists"""
        pool_name = "csi-pool"
        pools = self.storage_manager.system.storage_pools

        # Check if CSI pool already exists
        for pool in pools.values():
            if pool.name == pool_name:
                return pool

        # Create CSI pool if it doesn't exist
        location = StorageLocation(
            type="hybrid",
            path="/data/dfs/csi"
        )
        return self.storage_manager.create_storage_pool(
            name=pool_name,
            location=location,
            capacity_gb=1000  # Default 1TB pool
        )

    def create_volume(self, name: str, size_bytes: int) -> str:
        """Create a new volume for CSI"""
        size_gb = (size_bytes + (1024**3 - 1)) // (1024**3)  # Round up to nearest GB

        # Find CSI pool
        pool_id = None
        for pid, pool in self.storage_manager.system.storage_pools.items():
            if pool.name == "csi-pool":
                pool_id = pid
                break

        if not pool_id:
            raise RuntimeError("CSI storage pool not found")

        # Create volume with cloud tiering enabled
        volume = self.storage_manager.create_volume(
            name=name,
            size_gb=size_gb,
            pool_id=pool_id,
            cloud_tiering=True
        )

        return volume.id

    def delete_volume(self, volume_id: str):
        """Delete a CSI volume"""
        if volume_id in self.storage_manager.system.volumes:
            # TODO: Implement volume deletion in hybrid_storage.py
            pass

    def mount_volume(self, volume_id: str, target_path: str):
        """Mount a volume at the specified path"""
        if volume_id not in self.storage_manager.system.volumes:
            raise RuntimeError(f"Volume {volume_id} not found")

        # Create mount point
        os.makedirs(target_path, exist_ok=True)

        # TODO: Implement proper mounting
        # For now, we'll create a symlink to the volume's data directory
        volume = self.storage_manager.system.volumes[volume_id]
        source_path = Path(self.storage_manager.data_path) / volume.primary_pool_id / volume_id
        source_path.mkdir(parents=True, exist_ok=True)

        # Create symlink if it doesn't exist
        target_path = Path(target_path)
        if not target_path.exists():
            os.symlink(str(source_path), str(target_path))

    def unmount_volume(self, target_path: str):
        """Unmount a volume"""
        if os.path.exists(target_path):
            if os.path.islink(target_path):
                os.unlink(target_path)
            else:
                os.rmdir(target_path)
