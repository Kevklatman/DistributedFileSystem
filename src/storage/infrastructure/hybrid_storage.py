import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
import shutil
import dataclasses
import asyncio
import logging
from enum import Enum
from src.storage.infrastructure.providers import get_cloud_provider, CloudProviderBase

from src.models.models import (
    Volume,
    StoragePool,
    StorageLocation,
    CloudTieringPolicy,
    DataProtection,
    DataTemperature,
    TieringPolicy,
    HybridStorageSystem,
    SnapshotState
)

logger = logging.getLogger(__name__)

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)

def decode_datetime(obj):
    for key, value in obj.items():
        if key.endswith('_at') and isinstance(value, str):
            try:
                obj[key] = datetime.fromisoformat(value)
            except ValueError:
                pass
    return obj

class HybridStorageManager:
    """Manages hybrid storage operations across on-prem and cloud"""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.metadata_path = self.root_path / "metadata"
        self.data_path = self.root_path / "data"
        self.system = self._load_or_create_system()
        self.cloud_provider = None
        self._initialize_cloud_provider()

    def initialize(self) -> bool:
        """Initialize the hybrid storage system.
        
        Creates necessary directories and initializes the storage system state.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Create required directories
            self.metadata_path.mkdir(parents=True, exist_ok=True)
            self.data_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize storage pools
            self._init_storage_pools()
            
            # Initialize cloud provider if configured
            self._initialize_cloud_provider()
            
            # Save initial system state
            self._save_system_state()
            
            logger.info("Hybrid storage system initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize hybrid storage: {str(e)}")
            return False

    def _initialize_cloud_provider(self):
        """Initialize cloud storage provider if configured."""
        try:
            # Get provider type from environment or use default
            provider_type = os.getenv('CLOUD_PROVIDER_TYPE', 'aws')  # Default to AWS if not specified
            self.cloud_provider = get_cloud_provider(provider_type)
            if self.cloud_provider:
                logger.info(f"Initialized cloud provider: {self.cloud_provider.__class__.__name__}")
        except Exception as e:
            logger.warning(f"Failed to initialize cloud provider: {str(e)}")
            self.cloud_provider = None

    def _init_storage_pools(self):
        """Initialize default storage pools."""
        if not self.system.storage_pools:
            default_pool = StoragePool(
                id="default",
                name="Default Storage Pool",
                location=StorageLocation(
                    node_id="default",
                    path=str(self.data_path),
                    size_bytes=0,
                    replicas=[],
                    temperature=DataTemperature.COLD
                ),
                capacity_gb=0,  
                used_gb=0,
                created_at=datetime.now()
            )
            self.system.storage_pools[default_pool.id] = default_pool

    def _load_or_create_system(self) -> HybridStorageSystem:
        """Load existing system or create new one"""
        system_file = self.metadata_path / "system.json"
        if system_file.exists():
            with open(system_file, 'r') as f:
                data = json.load(f, object_hook=decode_datetime)
                return HybridStorageSystem(**data)
        return HybridStorageSystem(
            name="Default Hybrid Storage System",
            storage_pools={},
            volumes={},
            cloud_credentials={},
            tiering_policies={},
            protection_policies={},
            replication_policies={}
        )

    def _save_system_state(self) -> None:
        """Save system state to disk"""
        system_file = self.metadata_path / "system.json"
        with open(system_file, 'w') as f:
            json.dump(dataclasses.asdict(self.system), f, cls=EnhancedJSONEncoder, indent=2)

    async def create_storage_pool(
        self,
        name: str,
        location: StorageLocation,
        capacity_gb: int
    ) -> StoragePool:
        """Create a new storage pool"""
        # Generate a unique ID for the pool
        pool_id = f"pool-{len(self.system.storage_pools)}"
        
        pool = StoragePool(
            id=pool_id,
            name=name,
            location=location,
            capacity_gb=capacity_gb,
            used_gb=0
        )

        # Create pool directory
        pool_path = self.data_path / pool.id
        pool_path.mkdir(parents=True, exist_ok=True)

        self.system.storage_pools[pool.id] = pool
        self._save_system_state()
        return pool

    async def create_volume(
        self,
        name: str,
        size_gb: int,
        pool_id: str,
        cloud_backup: bool = False,
        cloud_tiering: bool = False
    ) -> Volume:
        """Create a new volume in a storage pool"""
        if pool_id not in self.system.storage_pools:
            raise ValueError(f"Pool {pool_id} not found")

        # Generate a unique ID for the volume
        volume_id = f"volume-{len(self.system.volumes)}"

        volume = Volume(
            id=volume_id,
            name=name,
            size_gb=size_gb,
            primary_pool_id=pool_id,
            cloud_tiering=cloud_tiering,
            created_at=datetime.now()
        )

        # Create volume directory
        pool_path = self.data_path / pool_id
        volume_path = pool_path / volume_id
        volume_path.mkdir(parents=True, exist_ok=True)

        if (cloud_backup or cloud_tiering) and self.cloud_provider:
            # Create a bucket for this volume
            bucket_name = f"hybrid-storage-{volume_id.lower()}"
            try:
                await self.cloud_provider.create_bucket(bucket_name)
                volume.cloud_location = StorageLocation(
                    node_id="cloud",
                    path=bucket_name,
                    size_bytes=0,
                    replicas=[],
                    temperature=DataTemperature.COLD
                )
            except Exception as e:
                logger.error(f"Failed to create cloud bucket: {e}")

        self.system.volumes[volume.id] = volume
        self._save_system_state()
        return volume

    async def write_data(self, volume_id: str, path: str, data: bytes) -> None:
        """Write data to a volume"""
        if volume_id not in self.system.volumes:
            raise ValueError(f"Volume {volume_id} not found")

        volume = self.system.volumes[volume_id]
        pool_id = volume.primary_pool_id

        # Construct full path
        full_path = self.data_path / pool_id / volume_id / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write locally
        async with asyncio.Lock():
            with open(full_path, 'wb') as f:
                f.write(data)

        # If cloud backup is enabled, write to cloud
        if volume.cloud_backup_enabled and self.cloud_provider and volume.cloud_location:
            try:
                await self.cloud_provider.upload_file(
                    data,
                    path,
                    volume.cloud_location.path
                )
            except Exception as e:
                logger.error(f"Failed to backup to cloud: {e}")

        # Check if we need to tier this data
        if volume.cloud_tiering_enabled:
            await self._check_tiering_policy(volume_id, path)

    async def read_data(self, volume_id: str, path: str) -> bytes:
        """Read data from a volume"""
        if volume_id not in self.system.volumes:
            raise ValueError(f"Volume {volume_id} not found")

        volume = self.system.volumes[volume_id]
        pool_id = volume.primary_pool_id

        # Try reading from local storage first
        full_path = self.data_path / pool_id / volume_id / path
        if full_path.exists():
            async with asyncio.Lock():
                with open(full_path, 'rb') as f:
                    return f.read()

        # If not found locally and cloud tiering is enabled, try cloud
        if volume.cloud_tiering_enabled and self.cloud_provider and volume.cloud_location:
            try:
                data = await self.cloud_provider.download_file(
                    path,
                    volume.cloud_location.path
                )
                if data:
                    # Cache data locally
                    async with asyncio.Lock():
                        with open(full_path, 'wb') as f:
                            f.write(data)
                    return data
            except Exception as e:
                logger.error(f"Failed to read from cloud: {e}")

        raise FileNotFoundError(f"Data not found: {path}")

    async def _check_tiering_policy(self, volume_id: str, path: str) -> None:
        """Check if data should be tiered to cloud storage"""
        volume = self.system.volumes[volume_id]
        if not volume.cloud_tiering_enabled or not volume.cloud_location:
            return

        full_path = self.data_path / volume.primary_pool_id / volume_id / path
        if not full_path.exists():
            return

        # Get file stats
        stats = full_path.stat()
        age = datetime.now() - datetime.fromtimestamp(stats.st_mtime)

        # Check if file should be tiered
        if age > timedelta(days=7):  # Cold tier after 7 days
            try:
                # Read file
                with open(full_path, 'rb') as f:
                    data = f.read()

                # Upload to cloud
                await self.cloud_provider.upload_file(
                    data,
                    path,
                    volume.cloud_location.path
                )

                # Remove local copy
                full_path.unlink()
            except Exception as e:
                logger.error(f"Failed to tier data to cloud: {e}")

    async def get_data_temperature(self, volume_id: str) -> DataTemperature:
        """Get the current temperature of volume data"""
        if volume_id not in self.system.volumes:
            raise ValueError(f"Volume {volume_id} not found")

        volume = self.system.volumes[volume_id]
        pool_id = volume.primary_pool_id

        # Check if data exists locally
        volume_path = self.data_path / pool_id / volume_id
        if not volume_path.exists():
            return DataTemperature.COLD

        # Calculate average file age
        total_age = 0
        file_count = 0
        for path in volume_path.rglob('*'):
            if path.is_file():
                age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
                total_age += age.days
                file_count += 1

        if file_count == 0:
            return DataTemperature.COLD

        avg_age = total_age / file_count
        if avg_age <= 1:
            return DataTemperature.HOT
        elif avg_age <= 7:
            return DataTemperature.WARM
        else:
            return DataTemperature.COLD

    async def create_snapshot(self, volume_id: str, name: str = None) -> str:
        """Create space-efficient snapshot"""
        volume = self.system.volumes[volume_id]
        protection = self.system.protection_policies.get(volume_id)

        if not protection:
            protection = DataProtection(volume_id=volume_id)
            self.system.protection_policies[volume_id] = protection

        # Create new snapshot state
        snapshot = SnapshotState(
            parent_id=self._get_latest_snapshot_id(protection),
            metadata={"name": name} if name else {}
        )

        # Track changed blocks since parent
        if snapshot.parent_id:
            parent = protection.snapshots[snapshot.parent_id]
            snapshot.changed_blocks = self._get_changed_blocks_since(
                volume_id,
                parent.creation_time
            )

        protection.snapshots[snapshot.id] = snapshot
        self._save_system_state()

        # If cloud backup enabled, replicate snapshot
        if protection.cloud_backup_enabled and self.cloud_provider:
            await self._backup_snapshot_to_cloud(volume_id, snapshot.id)

        return snapshot.id

    def _get_latest_snapshot_id(self, protection: DataProtection) -> Optional[str]:
        """Get the most recent snapshot ID"""
        if not protection.snapshots:
            return None
        return max(
            protection.snapshots.items(),
            key=lambda x: x[1].creation_time
        )[0]

    def _get_changed_blocks_since(self, volume_id: str, timestamp: datetime) -> Set[int]:
        """Get blocks that changed since timestamp"""
        # Implementation would track block changes
        # For now, return empty set
        return set()

    async def _backup_snapshot_to_cloud(self, volume_id: str, snapshot_id: str) -> None:
        """Backup snapshot to cloud storage"""
        volume = self.system.volumes[volume_id]
        protection = self.system.protection_policies[volume_id]
        snapshot = protection.snapshots[snapshot_id]

        if not self.cloud_provider or not volume.cloud_location:
            return

        # Only backup changed blocks for efficiency
        changed_data = self._get_snapshot_changed_data(volume_id, snapshot)

        # Upload with compression and dedup
        await self.cloud_provider.upload_snapshot(
            changed_data,
            f"snapshots/{snapshot_id}",
            volume.cloud_location.path
        )

    def _get_snapshot_changed_data(self, volume_id: str, snapshot: SnapshotState) -> bytes:
        """Get changed data for snapshot"""
        # Implementation would get changed data
        # For now, return empty bytes
        return b''

    async def _should_tier_based_on_prediction(self, temp_data: DataTemperature) -> bool:
        """Use access pattern and prediction to decide on tiering"""
        if temp_data.predicted_next_access:
            days_until_next_access = (temp_data.predicted_next_access - datetime.now()).days
            if days_until_next_access < 7:  # If predicted access is soon, don't tier
                return False
        return True

    async def _tier_to_cloud(self, volume_id: str, path: str) -> None:
        """Move data to cloud tier with optimization"""
        volume = self.system.volumes[volume_id]
        if not self.cloud_provider or not volume.cloud_location:
            return

        source = self.data_path / volume.primary_pool_id / volume_id / path

        # Optimize data before upload
        with open(source, 'rb') as f:
            data = f.read()

        # Apply compression if enabled
        if volume.compression_enabled:
            pool = self.system.storage_pools[volume.primary_pool_id]
            if pool.compression_state.adaptive:
                # Choose compression algorithm based on data type
                data = self._compress_data_adaptive(data)
            else:
                data = self._compress_data(data, pool.compression_state.algorithm)

        # Apply deduplication if enabled
        if volume.deduplication_enabled:
            data = self._deduplicate_data(data, volume_id, path)

        # Upload to cloud with optimal chunk size
        if await self.cloud_provider.upload_file(data, path, volume.cloud_location.path):
            # Create space-efficient stub
            await self._create_cloud_stub(source, volume.cloud_location.path, path)

    async def _create_cloud_stub(self, source_path: Path, bucket: str, path: str) -> None:
        """Create space-efficient stub file for tiered data"""
        stub_data = {
            "tiered_to_cloud": True,
            "bucket": bucket,
            "path": path,
            "timestamp": datetime.now().isoformat()
        }
        async with asyncio.Lock():
            with open(source_path, 'w') as f:
                json.dump(stub_data, f)
