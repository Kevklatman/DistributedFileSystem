import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import shutil
import dataclasses

from .models import (
    StorageLocation,
    StoragePool,
    Volume,
    CloudTieringPolicy,
    DataProtection,
    HybridStorageSystem
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
        
        if cloud_backup or cloud_tiering:
            # TODO: Implement cloud configuration
            pass
        
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
        
        with open(full_path, 'wb') as f:
            f.write(data)
            
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
            with open(local_path, 'rb') as f:
                return f.read()
                
        # If not found locally and tiering is enabled, check cloud
        if volume.cloud_tiering_enabled:
            # TODO: Implement cloud data retrieval
            pass
            
        raise FileNotFoundError(f"File {path} not found in volume {volume_id}")
    
    def _check_tiering_policy(self, volume_id: str, path: str) -> None:
        """Check if data should be tiered to cloud"""
        if volume_id not in self.system.tiering_policies:
            return
            
        policy = self.system.tiering_policies[volume_id]
        full_path = self.data_path / self.system.volumes[volume_id].primary_pool_id / volume_id / path
        
        # Check file size
        if full_path.stat().st_size < (policy.minimum_file_size_mb * 1024 * 1024):
            return
            
        # Check last access time
        last_access = datetime.fromtimestamp(full_path.stat().st_atime)
        if datetime.now() - last_access > timedelta(days=policy.cold_data_threshold_days):
            self._tier_to_cloud(volume_id, path)
    
    def _tier_to_cloud(self, volume_id: str, path: str) -> None:
        """Move data to cloud tier"""
        # TODO: Implement actual cloud tiering
        # For now, just simulate by moving to a "cloud" directory
        volume = self.system.volumes[volume_id]
        source = self.data_path / volume.primary_pool_id / volume_id / path
        cloud_dir = self.data_path / "cloud_tier" / volume_id
        cloud_dir.mkdir(parents=True, exist_ok=True)
        target = cloud_dir / path
        
        # Move file to cloud tier
        shutil.move(str(source), str(target))
        
        # Create stub file pointing to cloud location
        with open(source, 'w') as f:
            f.write(f"TIERED_TO_CLOUD:{target}")
