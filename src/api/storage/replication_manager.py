from typing import Dict, List, Optional
import hashlib
import aiohttp
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from .models import StorageLocation, Volume

@dataclass
class ReplicationPolicy:
    source_volume_id: str
    target_location: StorageLocation
    bandwidth_limit_mbps: Optional[int] = None
    compression_enabled: bool = True
    sync_interval_minutes: int = 60
    bandwidth_schedule: Dict[str, int] = None  # Hour -> bandwidth limit
    incremental_only: bool = True
    verify_after_sync: bool = True

class ReplicationManager:
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
        self.logger = logging.getLogger(__name__)
        self.active_replications: Dict[str, ReplicationPolicy] = {}
        self.bandwidth_semaphore = asyncio.Semaphore(10)  # Limit concurrent transfers
        
    async def start_replication(self, policy: ReplicationPolicy):
        """Start replication for a volume with the given policy"""
        if policy.source_volume_id not in self.storage_manager.system.volumes:
            raise ValueError(f"Volume {policy.source_volume_id} not found")
            
        self.active_replications[policy.source_volume_id] = policy
        asyncio.create_task(self._replication_loop(policy))
        
    async def _replication_loop(self, policy: ReplicationPolicy):
        """Main replication loop that handles scheduling and bandwidth management"""
        while policy.source_volume_id in self.active_replications:
            try:
                await self._perform_replication(policy)
                await asyncio.sleep(policy.sync_interval_minutes * 60)
            except Exception as e:
                self.logger.error(f"Replication error for volume {policy.source_volume_id}: {str(e)}")
                await asyncio.sleep(60)  # Wait before retry
                
    async def _perform_replication(self, policy: ReplicationPolicy):
        """Perform actual replication with bandwidth control and optimization"""
        volume = self.storage_manager.system.volumes[policy.source_volume_id]
        
        # Get current bandwidth limit based on schedule
        current_hour = datetime.now().hour
        bandwidth_limit = policy.bandwidth_schedule.get(
            current_hour, 
            policy.bandwidth_limit_mbps
        ) if policy.bandwidth_schedule else policy.bandwidth_limit_mbps
        
        async with self.bandwidth_semaphore:
            # Get changed blocks since last sync if incremental
            changed_blocks = await self._get_changed_blocks(volume) if policy.incremental_only else None
            
            # Calculate optimal chunk size based on bandwidth
            chunk_size = self._calculate_chunk_size(bandwidth_limit) if bandwidth_limit else 1024 * 1024
            
            # Compress data if enabled
            if policy.compression_enabled:
                data = await self._compress_data(changed_blocks or volume.data)
            else:
                data = changed_blocks or volume.data
                
            # Split data into chunks and transfer with bandwidth control
            chunks = self._split_into_chunks(data, chunk_size)
            for chunk in chunks:
                await self._transfer_chunk(
                    chunk, 
                    policy.target_location,
                    bandwidth_limit
                )
                
            if policy.verify_after_sync:
                await self._verify_replication(volume, policy.target_location)

    async def _transfer_chunk(self, chunk: bytes, target: StorageLocation, bandwidth_limit: Optional[int]):
        """Transfer a chunk of data with bandwidth limiting"""
        if bandwidth_limit:
            chunk_size = len(chunk)
            expected_transfer_time = chunk_size / (bandwidth_limit * 1024 * 1024 / 8)
            start_time = datetime.now()
            
            # Actual transfer
            await self._replicate_to_node(chunk, target)
            
            # Calculate and apply delay if transfer was too fast
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed < expected_transfer_time:
                await asyncio.sleep(expected_transfer_time - elapsed)
        else:
            await self._replicate_to_node(chunk, target)

    @staticmethod
    def _calculate_chunk_size(bandwidth_limit_mbps: int) -> int:
        """Calculate optimal chunk size based on bandwidth limit"""
        # Use larger chunks for higher bandwidth
        base_chunk_size = 1024 * 1024  # 1MB base
        return min(base_chunk_size * (bandwidth_limit_mbps // 100 + 1), 
                  16 * 1024 * 1024)  # Cap at 16MB

    async def _get_changed_blocks(self, volume: Volume) -> bytes:
        """Get blocks that changed since last sync (SnapMirror-like)"""
        # Implementation would track block changes
        # For now, return None to indicate full sync needed
        return None

    async def _compress_data(self, data: bytes) -> bytes:
        """Compress data for transfer"""
        # Add actual compression implementation
        return data

    @staticmethod
    def _split_into_chunks(data: bytes, chunk_size: int) -> List[bytes]:
        """Split data into chunks for transfer"""
        return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

    async def _verify_replication(self, volume: Volume, target_location: StorageLocation):
        """Verify successful replication"""
        # Implementation would check checksums between source and target
        pass

    async def _replicate_to_node(self, data: bytes, target: StorageLocation):
        """Replicate data to a specific node"""
        try:
            checksum = hashlib.sha256(data).hexdigest()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{target.pod_ip}:8080/storage/replicate",
                    json={
                        "data": data.hex(),
                        "checksum": checksum
                    }
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Replication failed: {await response.text()}")
                    
                    # Verify the checksum
                    resp_data = await response.json()
                    if resp_data["checksum"] != checksum:
                        raise Exception("Checksum verification failed")
                    
                    return True
        except Exception as e:
            self.logger.error(f"Replication to node {target.node_id} failed: {str(e)}")
            return False
