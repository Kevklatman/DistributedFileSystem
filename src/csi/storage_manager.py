from typing import Optional, Dict
import os
import asyncio
from pathlib import Path
import sys
import shutil

# Add parent directory to path to import storage modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.infrastructure.hybrid_storage import HybridStorageManager
from src.models.models import StorageLocation, Volume, DataTemperature


class CSIStorageManager:
    """Storage Manager for CSI Driver Integration"""

    def __init__(self, root_path: str = "/data/dfs"):
        self.storage_manager = HybridStorageManager(root_path)
        asyncio.run(self._ensure_csi_pool())

    async def _ensure_csi_pool(self):
        """Ensure CSI storage pool exists"""
        pool_name = "csi-pool"
        pools = self.storage_manager.system.pools

        # Check if CSI pool already exists
        for pool in pools.values():
            if pool.name == pool_name:
                return pool

        # Create CSI pool if it doesn't exist
        location = StorageLocation(
            node_id="local",
            path=str(Path(self.storage_manager.root_path) / "csi"),
            size_bytes=1000 * 1024 * 1024 * 1024,  # 1TB
            replicas=[],
            temperature=DataTemperature.HOT,
        )
        return await self.storage_manager.create_storage_pool(
            name=pool_name, location=location, capacity_gb=1000  # Default 1TB pool
        )

    async def create_volume(self, name: str, size_bytes: int) -> str:
        """Create a new volume for CSI"""
        size_gb = (size_bytes + (1024**3 - 1)) // (1024**3)  # Round up to nearest GB

        # Find CSI pool
        pool_id = None
        for pid, pool in self.storage_manager.system.pools.items():
            if pool.name == "csi-pool":
                pool_id = pid
                break

        if not pool_id:
            raise RuntimeError("CSI storage pool not found")

        # Create volume with cloud tiering enabled
        volume = await self.storage_manager.create_volume(
            name=name, size_gb=size_gb, pool_id=pool_id, cloud_tiering=True
        )

        return volume.id

    async def delete_volume(self, volume_id: str):
        """Delete a CSI volume"""
        if volume_id in self.storage_manager.system.volumes:
            volume = self.storage_manager.system.volumes[volume_id]
            # Clean up mount points if any
            if hasattr(volume, "mount_point") and volume.mount_point:
                await self.unmount_volume(volume.mount_point)

            # Delete from storage manager
            del self.storage_manager.system.volumes[volume_id]

            # Delete physical volume directory
            volume_path = (
                Path(self.storage_manager.data_path)
                / volume.primary_pool_id
                / volume_id
            )
            if volume_path.exists():
                shutil.rmtree(str(volume_path))

    async def mount_volume(self, volume_id: str, target_path: str):
        """Mount a volume at the specified path"""
        if volume_id not in self.storage_manager.system.volumes:
            raise ValueError(f"Volume {volume_id} not found")

        # Get volume path
        volume = self.storage_manager.system.volumes[volume_id]
        pool = self.storage_manager.system.pools[volume.primary_pool_id]
        volume_path = Path(self.storage_manager.data_path) / pool.id / volume.id

        # Ensure volume directory exists
        volume_path.mkdir(parents=True, exist_ok=True)

        # Remove target path if it exists
        target = Path(target_path)
        if target.exists():
            if target.is_symlink():
                target.unlink()
            elif target.is_dir():
                target.rmdir()
            else:
                raise ValueError(
                    f"Mount point {target_path} exists and is not a directory or symlink"
                )

        # Create parent directory if needed
        target.parent.mkdir(parents=True, exist_ok=True)

        # Create symlink to target path
        os.symlink(volume_path, target_path)

        # Store mount point in volume
        volume.mount_point = target_path

    async def unmount_volume(self, target_path: str):
        """Unmount a volume from the specified path"""
        if target_path is None:
            return

        if os.path.exists(target_path):
            if os.path.islink(target_path):
                os.unlink(target_path)
            elif os.path.isdir(target_path):
                os.rmdir(target_path)
