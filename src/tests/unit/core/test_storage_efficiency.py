"""Unit tests for storage efficiency features"""
import pytest
from pathlib import Path
import os
import hashlib
from datetime import datetime
from unittest.mock import patch, mock_open, MagicMock

from src.storage.core.storage_efficiency import StorageEfficiencyManager
from src.storage.core.models import (
    Volume,
    DeduplicationState,
    CompressionState,
    ThinProvisioningState,
    StoragePool
)

@pytest.fixture
def test_data_path(tmp_path):
    """Create a temporary data path"""
    return tmp_path

@pytest.fixture
def efficiency_manager(test_data_path):
    """Create a storage efficiency manager instance"""
    return StorageEfficiencyManager(test_data_path)

@pytest.fixture
def test_volume():
    """Create a test volume"""
    return Volume(
        volume_id="test-vol-1",
        size_bytes=1024 * 1024 * 100,  # 100MB
        used_bytes=0,
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        locations=[],
        deduplication_enabled=True
    )

class TestDeduplication:
    def test_deduplicate_file_new_content(self, efficiency_manager, test_volume, tmp_path):
        """Test deduplication with new content"""
        # Create test file with unique content
        file_path = tmp_path / "pool-1" / test_volume.volume_id / "test.txt"
        file_path.parent.mkdir(parents=True)
        test_data = b"unique content" * 1000
        file_path.write_bytes(test_data)

        # Run deduplication
        original_size, new_size = efficiency_manager.deduplicate_file(test_volume, str(file_path))

        assert original_size == len(test_data)
        assert new_size == original_size  # First time, no deduplication
        assert len(efficiency_manager.dedup_index) > 0

    def test_deduplicate_file_duplicate_content(self, efficiency_manager, test_volume, tmp_path):
        """Test deduplication with duplicate content"""
        # Create two files with same content
        file1_path = tmp_path / "pool-1" / test_volume.volume_id / "test1.txt"
        file2_path = tmp_path / "pool-1" / test_volume.volume_id / "test2.txt"
        file1_path.parent.mkdir(parents=True)
        test_data = b"duplicate content" * 1000

        file1_path.write_bytes(test_data)
        file2_path.write_bytes(test_data)

        # Deduplicate first file
        efficiency_manager.deduplicate_file(test_volume, str(file1_path))

        # Deduplicate second file
        original_size, new_size = efficiency_manager.deduplicate_file(test_volume, str(file2_path))

        assert original_size == len(test_data)
        assert new_size < original_size  # Should be deduped
        assert test_volume.deduplication_state is not None
        assert test_volume.deduplication_state.total_savings > 0

class TestCompression:
    def test_compress_data_zlib(self, efficiency_manager):
        """Test zlib compression"""
        test_data = b"compress me" * 1000
        compressed, ratio = efficiency_manager.compress_data(test_data, 'zlib')

        assert len(compressed) < len(test_data)
        assert ratio < 1.0

    def test_compress_data_lz4(self, efficiency_manager):
        """Test lz4 compression"""
        test_data = b"compress me" * 1000
        compressed, ratio = efficiency_manager.compress_data(test_data, 'lz4')

        assert len(compressed) < len(test_data)
        assert ratio < 1.0

    def test_compress_data_snappy(self, efficiency_manager):
        """Test snappy compression"""
        test_data = b"compress me" * 1000
        compressed, ratio = efficiency_manager.compress_data(test_data, 'snappy')

        assert len(compressed) < len(test_data)
        assert ratio < 1.0

    def test_invalid_compression_algorithm(self, efficiency_manager):
        """Test invalid compression algorithm"""
        test_data = b"compress me"
        with pytest.raises(ValueError):
            efficiency_manager.compress_data(test_data, 'invalid')

    def test_adaptive_compression(self, efficiency_manager):
        """Test adaptive compression algorithm selection"""
        # Test with highly compressible data
        test_data = b"a" * 10000
        compressed, algo, ratio = efficiency_manager.adaptive_compression(test_data)

        assert len(compressed) < len(test_data)
        assert algo in ['zlib', 'lz4', 'snappy']
        assert ratio < 1.0

class TestThinProvisioning:
    def test_setup_thin_provisioning(self, efficiency_manager, test_volume):
        """Test thin provisioning setup"""
        requested_size = 1024 * 1024 * 1000  # 1GB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)

        assert test_volume.thin_provisioning_state is not None
        assert test_volume.thin_provisioning_state.allocated_size == requested_size
        assert test_volume.volume_id in efficiency_manager.thin_provision_map
        assert efficiency_manager.thin_provision_map[test_volume.volume_id]['block_size'] == 4096

    def test_allocate_blocks_success(self, efficiency_manager, test_volume):
        """Test successful block allocation"""
        requested_size = 1024 * 1024 * 100  # 100MB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)

        # Allocate 10MB
        success = efficiency_manager.allocate_blocks(test_volume, 1024 * 1024 * 10)
        assert success
        assert test_volume.thin_provisioning_state.used_size == 1024 * 1024 * 10

    def test_allocate_blocks_over_limit(self, efficiency_manager, test_volume):
        """Test block allocation beyond limit"""
        requested_size = 1024 * 1024 * 100  # 100MB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)

        # Try to allocate 200MB (over the limit)
        success = efficiency_manager.allocate_blocks(test_volume, 1024 * 1024 * 200)
        assert not success

    def test_reclaim_space(self, efficiency_manager, test_volume):
        """Test space reclamation"""
        requested_size = 1024 * 1024 * 100  # 100MB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)

        # Allocate some blocks
        efficiency_manager.allocate_blocks(test_volume, 1024 * 1024 * 50)

        # Mock _is_block_in_use to return False for some blocks
        with patch.object(efficiency_manager, '_is_block_in_use', return_value=False):
            reclaimed = efficiency_manager.reclaim_space(test_volume)
            assert reclaimed > 0
            assert test_volume.thin_provisioning_state.used_size < 1024 * 1024 * 50

if __name__ == '__main__':
    pytest.main(['-v', __file__])
