import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
import shutil
import dataclasses
from providers import get_cloud_provider, CloudProviderBase

from models import (
    StorageLocation,
    StoragePool,
    Volume,
    CloudTieringPolicy,
    DataProtection,
    HybridStorageSystem,
    DataTemperature,
    SnapshotState
)

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
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

        # Initialize cloud provider if environment is set to AWS
        self.cloud_provider = None
        if os.getenv('STORAGE_ENV') == 'aws':
            try:
                self.cloud_provider = get_cloud_provider('aws_s3')
            except Exception as e:
                print(f"Warning: Failed to initialize cloud provider: {e}")

        # Ensure required directories exist
        self.metadata_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)

    def _load_or_create_system(self) -> HybridStorageSystem:
        """Load existing system or create new one"""
        system_file = self.metadata_path / "system.json"
        if system_file.exists():
            with open(system_file, 'r') as f:
                data = json.load(f, object_hook=decode_datetime)

                # Reconstruct objects from JSON
                storage_pools = {}
                for pool_id, pool_data in data.get('storage_pools', {}).items():
                    location = StorageLocation(**pool_data['location'])
                    pool = StoragePool(
                        name=pool_data['name'],
                        location=location,
                        total_capacity_gb=pool_data['total_capacity_gb'],
                        available_capacity_gb=pool_data['available_capacity_gb'],
                        id=pool_id,
                        is_thin_provisioned=pool_data.get('is_thin_provisioned', False),
                        encryption_enabled=pool_data.get('encryption_enabled', True),
                        created_at=pool_data.get('created_at', datetime.now())
                    )
                    storage_pools[pool_id] = pool

                volumes = {}
                for vol_id, vol_data in data.get('volumes', {}).items():
                    cloud_location = None
                    if vol_data.get('cloud_location'):
                        cloud_location = StorageLocation(**vol_data['cloud_location'])
                    volume = Volume(
                        name=vol_data['name'],
                        size_gb=vol_data['size_gb'],
                        primary_pool_id=vol_data['primary_pool_id'],
                        id=vol_id,
                        cloud_backup_enabled=vol_data.get('cloud_backup_enabled', False),
                        cloud_tiering_enabled=vol_data.get('cloud_tiering_enabled', False),
                        cloud_location=cloud_location,
                        encryption_at_rest=vol_data.get('encryption_at_rest', True),
                        compression_enabled=vol_data.get('compression_enabled', True),
                        deduplication_enabled=vol_data.get('deduplication_enabled', True),
                        created_at=vol_data.get('created_at', datetime.now())
                    )
                    volumes[vol_id] = volume

                return HybridStorageSystem(
                    name=data.get('name', 'default'),
                    id=data.get('id'),
                    storage_pools=storage_pools,
                    volumes=volumes
                )
        return HybridStorageSystem(name="default")

    def _save_system_state(self) -> None:
        """Save system state to disk"""
        system_file = self.metadata_path / "system.json"
        with open(system_file, 'w') as f:
            json.dump(dataclasses.asdict(self.system), f, cls=EnhancedJSONEncoder, indent=2)

    def create_storage_pool(
        self,
        name: str,
        location: StorageLocation,
        capacity_gb: int
    ) -> StoragePool:
        """Create a new storage pool"""
        pool = StoragePool(
            name=name,
            location=location,
            total_capacity_gb=capacity_gb,
            available_capacity_gb=capacity_gb
        )

        # Create pool directory
        pool_path = self.data_path / pool.id
        pool_path.mkdir(parents=True, exist_ok=True)

        self.system.add_storage_pool(pool)
        self._save_system_state()
        return pool

    def create_volume(
        self,
        name: str,
        size_gb: int,
        pool_id: str,
        cloud_backup: bool = False,
        cloud_tiering: bool = False
    ) -> Volume:
        """Create a new volume in a storage pool"""
        volume = self.system.create_volume(name, size_gb, pool_id)

        # Create volume directory
        pool_path = self.data_path / pool_id
        volume_path = pool_path / volume.id
        volume_path.mkdir(parents=True, exist_ok=True)

        if (cloud_backup or cloud_tiering) and self.cloud_provider:
            # Create a bucket for this volume
            bucket_name = f"hybrid-storage-{volume.id.lower()}"
            if self.cloud_provider.create_bucket(bucket_name):
                volume.cloud_backup_enabled = cloud_backup
                volume.cloud_tiering_enabled = cloud_tiering
                volume.cloud_location = StorageLocation(
                    type='aws_s3',
                    path=bucket_name
                )

        self._save_system_state()
        return volume

    def write_data(self, volume_id: str, path: str, data: bytes) -> None:
        """Write data to a volume"""
        if volume_id not in self.system.volumes:
            raise ValueError(f"Volume {volume_id} not found")

        volume = self.system.volumes[volume_id]
        pool_id = volume.primary_pool_id

        # Construct full path
        full_path = self.data_path / pool_id / volume_id / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write locally
        with open(full_path, 'wb') as f:
            f.write(data)

        # If cloud backup is enabled, write to cloud immediately
        if volume.cloud_backup_enabled and self.cloud_provider and volume.cloud_location:
            self.cloud_provider.upload_file(
                data,
                path,
                volume.cloud_location.path
            )

        # Check if we need to tier this data
        if volume.cloud_tiering_enabled:
            self._check_tiering_policy(volume_id, path)

    def read_data(self, volume_id: str, path: str) -> bytes:
        """Read data from a volume"""
        if volume_id not in self.system.volumes:
            raise ValueError(f"Volume {volume_id} not found")

        volume = self.system.volumes[volume_id]
        pool_id = volume.primary_pool_id

        # Try local first
        local_path = self.data_path / pool_id / volume_id / path
        if local_path.exists():
            # Check if it's a stub file
            with open(local_path, 'r') as f:
                first_line = f.readline().strip()
                if first_line.startswith('TIERED_TO_CLOUD:'):
                    return self._read_from_cloud(volume, path)

            # Regular local file
            with open(local_path, 'rb') as f:
                return f.read()

        # If not found locally and cloud is enabled, check cloud
        if volume.cloud_tiering_enabled and self.cloud_provider and volume.cloud_location:
            return self._read_from_cloud(volume, path)

        raise FileNotFoundError(f"File {path} not found in volume {volume_id}")

    def _read_from_cloud(self, volume: Volume, path: str) -> bytes:
        """Read data from cloud storage"""
        if not self.cloud_provider or not volume.cloud_location:
            raise RuntimeError("Cloud provider not configured")

        data = self.cloud_provider.download_file(path, volume.cloud_location.path)
        if data is None:
            raise FileNotFoundError(f"File {path} not found in cloud storage")
        return data

    def _check_tiering_policy(self, volume_id: str, path: str) -> None:
        """Check if data should be tiered to cloud based on temperature and cost"""
        if volume_id not in self.system.tiering_policies:
            return

        policy = self.system.tiering_policies[volume_id]
        volume = self.system.volumes[volume_id]
        full_path = self.data_path / volume.primary_pool_id / volume_id / path

        # Get or create temperature tracking
        if path not in volume.data_temperature:
            volume.data_temperature[path] = DataTemperature(
                last_access=datetime.fromtimestamp(full_path.stat().st_atime)
            )
        temp_data = volume.data_temperature[path]

        # Update access pattern
        file_size = full_path.stat().st_size
        if file_size < policy.minimum_file_size_mb * 1024 * 1024:
            return

        # Calculate data temperature score
        current_time = datetime.now()
        age_days = (current_time - temp_data.last_access).days

        # Determine temperature based on thresholds
        if age_days > policy.temperature_thresholds["cold_to_frozen_days"]:
            new_temp = "frozen"
        elif age_days > policy.temperature_thresholds["warm_to_cold_days"]:
            new_temp = "cold"
        elif age_days > policy.temperature_thresholds["hot_to_warm_days"]:
            new_temp = "warm"
        else:
            new_temp = "hot"

        if new_temp != temp_data.temperature:
            temp_data.temperature = new_temp

            # Calculate cost savings
            current_tier = self.system.storage_pools[volume.primary_pool_id].location
            target_tier = policy.target_cloud_location
            cost_savings = (current_tier.cost_per_gb - target_tier.cost_per_gb) * (file_size / (1024 * 1024 * 1024))

            # Decision to tier based on temperature and cost
            if (new_temp in ["cold", "frozen"] and
                cost_savings > policy.cost_threshold_per_gb and
                self._should_tier_based_on_prediction(temp_data)):
                self._tier_to_cloud(volume_id, path)

    def _should_tier_based_on_prediction(self, temp_data: DataTemperature) -> bool:
        """Use access pattern and prediction to decide on tiering"""
        if temp_data.predicted_next_access:
            days_until_next_access = (temp_data.predicted_next_access - datetime.now()).days
            if days_until_next_access < 7:  # If predicted access is soon, don't tier
                return False
        return True

    def _tier_to_cloud(self, volume_id: str, path: str) -> None:
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
        if self.cloud_provider.upload_file(data, path, volume.cloud_location.path):
            # Create space-efficient stub
            self._create_cloud_stub(source, volume.cloud_location.path, path)

    def _create_cloud_stub(self, source_path: Path, bucket: str, path: str) -> None:
        """Create space-efficient stub file for tiered data"""
        stub_data = {
            "tiered_to_cloud": True,
            "bucket": bucket,
            "path": path,
            "timestamp": datetime.now().isoformat()
        }
        with open(source_path, 'w') as f:
            json.dump(stub_data, f)

    def create_snapshot(self, volume_id: str, name: str = None) -> str:
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
            self._backup_snapshot_to_cloud(volume_id, snapshot.id)

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

    def _backup_snapshot_to_cloud(self, volume_id: str, snapshot_id: str) -> None:
        """Backup snapshot to cloud storage"""
        volume = self.system.volumes[volume_id]
        protection = self.system.protection_policies[volume_id]
        snapshot = protection.snapshots[snapshot_id]

        if not self.cloud_provider or not volume.cloud_location:
            return

        # Only backup changed blocks for efficiency
        changed_data = self._get_snapshot_changed_data(volume_id, snapshot)

        # Upload with compression and dedup
        self.cloud_provider.upload_snapshot(
            changed_data,
            f"snapshots/{snapshot_id}",
            volume.cloud_location.path
        )
