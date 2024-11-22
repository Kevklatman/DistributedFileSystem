"""
Storage efficiency features including deduplication, compression, and thin provisioning
"""
import hashlib
import zlib
import lz4.frame
import snappy
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import os
import json
from pathlib import Path

from .models import (
    DeduplicationState,
    CompressionState,
    ThinProvisioningState,
    Volume,
    StoragePool
)

class StorageEfficiencyManager:
    """Manages storage efficiency features including deduplication, compression, and thin provisioning"""

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.chunk_size = 64 * 1024  # 64KB chunks for deduplication
        self.dedup_index: Dict[str, Set[str]] = {}  # hash -> set of file paths
        self.compression_stats: Dict[str, Dict] = {}
        self.thin_provision_map: Dict[str, Dict] = {}

    def deduplicate_file(self, volume: Volume, file_path: str) -> Tuple[int, int]:
        """Deduplicate a file, returns (original_size, new_size)"""
        if not volume.deduplication_enabled:
            return 0, 0

        full_path = self.data_path / volume.primary_pool_id / volume.id / file_path
        if not full_path.exists():
            return 0, 0

        original_size = full_path.stat().st_size
        saved_size = 0

        # Read file in chunks
        with open(full_path, 'rb') as f:
            while chunk := f.read(self.chunk_size):
                chunk_hash = hashlib.sha256(chunk).hexdigest()

                if chunk_hash in self.dedup_index:
                    # Deduplication found
                    saved_size += len(chunk)
                    self.dedup_index[chunk_hash].add(str(full_path))
                else:
                    # New unique chunk
                    self.dedup_index[chunk_hash] = {str(full_path)}

        # Update deduplication state
        if volume.deduplication_state is None:
            volume.deduplication_state = DeduplicationState()

        volume.deduplication_state.total_savings += saved_size
        volume.deduplication_state.last_run = datetime.now()

        return original_size, original_size - saved_size

    def compress_data(self, data: bytes, algorithm: str = 'zlib') -> Tuple[bytes, float]:
        """Compress data using specified algorithm, returns (compressed_data, ratio)"""
        original_size = len(data)

        if algorithm == 'zlib':
            compressed = zlib.compress(data, level=6)
        elif algorithm == 'lz4':
            compressed = lz4.frame.compress(data)
        elif algorithm == 'snappy':
            compressed = snappy.compress(data)
        else:
            raise ValueError(f"Unsupported compression algorithm: {algorithm}")

        ratio = len(compressed) / original_size
        return compressed, ratio

    def adaptive_compression(self, data: bytes, sample_size: int = 4096) -> Tuple[bytes, str, float]:
        """Choose best compression algorithm based on data sample"""
        # Take a sample of the data for testing
        sample = data[:sample_size]

        # Test different algorithms
        results = []
        for algo in ['zlib', 'lz4', 'snappy']:
            compressed, ratio = self.compress_data(sample, algo)
            results.append((algo, ratio))

        # Choose best algorithm (lowest ratio = best compression)
        best_algo = min(results, key=lambda x: x[1])[0]

        # Compress full data with best algorithm
        compressed, ratio = self.compress_data(data, best_algo)
        return compressed, best_algo, ratio

    def setup_thin_provisioning(self, volume: Volume, requested_size: int) -> None:
        """Initialize thin provisioning for a volume"""
        if volume.thin_provisioning_state is None:
            volume.thin_provisioning_state = ThinProvisioningState(
                allocated_size=requested_size,
                used_size=0,
                oversubscription_ratio=2.0  # Default 2x oversubscription
            )

        # Initialize block allocation map
        self.thin_provision_map[volume.id] = {
            'allocated_blocks': set(),
            'block_size': 4096,  # 4KB blocks
            'total_blocks': requested_size // 4096
        }

    def allocate_blocks(self, volume: Volume, size: int) -> bool:
        """Allocate blocks for thin provisioning"""
        if volume.id not in self.thin_provision_map:
            return False

        thin_map = self.thin_provision_map[volume.id]
        blocks_needed = (size + thin_map['block_size'] - 1) // thin_map['block_size']

        # Check if we have enough free blocks
        if len(thin_map['allocated_blocks']) + blocks_needed > thin_map['total_blocks']:
            # Handle out of space condition
            if not self._handle_out_of_space(volume, blocks_needed):
                return False

        # Allocate blocks
        new_blocks = set(range(
            max(thin_map['allocated_blocks']) + 1 if thin_map['allocated_blocks'] else 0,
            blocks_needed
        ))
        thin_map['allocated_blocks'].update(new_blocks)

        # Update thin provisioning state
        volume.thin_provisioning_state.used_size += size
        return True

    def _handle_out_of_space(self, volume: Volume, blocks_needed: int) -> bool:
        """Handle out of space condition for thin provisioning"""
        state = volume.thin_provisioning_state

        # Check if we can increase allocation within oversubscription ratio
        current_ratio = state.allocated_size / state.used_size
        if current_ratio < state.oversubscription_ratio:
            # Can grow the volume
            new_size = state.allocated_size * 1.5  # Grow by 50%
            state.allocated_size = new_size
            self.thin_provision_map[volume.id]['total_blocks'] = new_size // 4096
            return True

        return False

    def reclaim_space(self, volume: Volume) -> int:
        """Reclaim unused space from thin provisioned volume"""
        if volume.id not in self.thin_provision_map:
            return 0

        thin_map = self.thin_provision_map[volume.id]
        # Scan for unused blocks
        unused_blocks = set()
        for block in thin_map['allocated_blocks']:
            if not self._is_block_in_use(volume, block):
                unused_blocks.add(block)

        # Remove unused blocks
        thin_map['allocated_blocks'] -= unused_blocks
        reclaimed = len(unused_blocks) * thin_map['block_size']

        # Update thin provisioning state
        volume.thin_provisioning_state.used_size -= reclaimed
        return reclaimed

    def _is_block_in_use(self, volume: Volume, block: int) -> bool:
        """Check if a block is currently in use"""
        # Implementation would check actual block usage
        # For now, assume all allocated blocks are in use
        return True
