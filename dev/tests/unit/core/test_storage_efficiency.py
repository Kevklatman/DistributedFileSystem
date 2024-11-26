"""Unit tests for storage efficiency functionality."""

import pytest
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path
import uuid

from src.storage.infrastructure.storage_efficiency import StorageEfficiencyManager
from src.models.models import (
    Volume,
    DeduplicationState,
    CompressionState,
    ThinProvisioningState,
    StoragePool,
)

@pytest.fixture
def test_data_path():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def test_volume():
    """Create a test volume with efficiency features enabled."""
    return Volume(
        volume_id=str(uuid.uuid4()),
        size_bytes=100 * 1024 * 1024 * 1024,  # 100GB
        deduplication_enabled=True,
        compression_state=CompressionState(
            enabled=True,
            algorithm="zstd"
        ),
        thin_provisioning_state=ThinProvisioningState(
            allocated_size=100 * 1024 * 1024 * 1024,
            used_size=0
        )
    )

class TestDeduplication:
    @pytest.fixture
    def efficiency_manager(self, test_data_path):
        return StorageEfficiencyManager(data_path=test_data_path)

    def test_deduplicate_file_new_content(self, efficiency_manager, test_volume, test_data_path):
        """Test deduplication with new content."""
        test_file = test_data_path / "test1.txt"
        content = b"new test content"
        test_file.write_bytes(content)
        
        original_size, new_size = efficiency_manager.deduplicate_file(test_volume, str(test_file))
        assert original_size > 0
        assert new_size == original_size  # First write should not be deduplicated

    def test_deduplicate_file_duplicate_content(self, efficiency_manager, test_volume, test_data_path):
        """Test deduplication with duplicate content."""
        test_file1 = test_data_path / "test1.txt"
        test_file2 = test_data_path / "test2.txt"
        content = b"test content"
        
        # Write same content to both files
        test_file1.write_bytes(content)
        test_file2.write_bytes(content)
        
        # First file
        original_size1, new_size1 = efficiency_manager.deduplicate_file(test_volume, str(test_file1))
        # Second file with same content
        original_size2, new_size2 = efficiency_manager.deduplicate_file(test_volume, str(test_file2))
        
        assert original_size2 > 0
        assert new_size2 < original_size2  # Should be deduplicated

class TestCompression:
    @pytest.fixture
    def efficiency_manager(self, test_data_path):
        return StorageEfficiencyManager(data_path=test_data_path)

    def test_compress_data_zlib(self, efficiency_manager, test_volume):
        """Test zlib compression."""
        data = b"test data" * 1000
        compressed, ratio = efficiency_manager.compress_data(test_volume, data, algorithm="zlib")
        assert len(compressed) < len(data)
        assert ratio < 1.0

    def test_compress_data_lz4(self, efficiency_manager, test_volume):
        """Test lz4 compression."""
        data = b"test data" * 1000
        compressed, ratio = efficiency_manager.compress_data(test_volume, data, algorithm="lz4")
        assert len(compressed) < len(data)
        assert ratio < 1.0

    def test_compress_data_snappy(self, efficiency_manager, test_volume):
        """Test snappy compression."""
        data = b"test data" * 1000
        compressed, ratio = efficiency_manager.compress_data(test_volume, data, algorithm="snappy")
        assert len(compressed) < len(data)
        assert ratio < 1.0

    def test_invalid_compression_algorithm(self, efficiency_manager, test_volume):
        """Test invalid compression algorithm."""
        data = b"test data"
        with pytest.raises(ValueError):
            efficiency_manager.compress_data(test_volume, data, algorithm="invalid")

    def test_adaptive_compression(self, efficiency_manager, test_volume):
        """Test adaptive compression based on data type."""
        compressible_data = b"test data" * 1000
        compressed, ratio = efficiency_manager.compress_data(test_volume, compressible_data)
        assert len(compressed) < len(compressible_data)
        assert ratio < 1.0


class TestThinProvisioning:
    @pytest.fixture
    def efficiency_manager(self, test_data_path):
        return StorageEfficiencyManager(data_path=test_data_path)

    def test_setup_thin_provisioning(self, efficiency_manager, test_volume):
        """Test thin provisioning setup."""
        requested_size = 1024 * 1024 * 1024  # 1GB
        success = efficiency_manager.setup_thin_provisioning(test_volume, requested_size)
        assert success
        assert test_volume.volume_id in efficiency_manager.thin_provision_map

    def test_allocate_blocks_success(self, efficiency_manager, test_volume):
        """Test successful block allocation."""
        requested_size = 1024 * 1024 * 1024  # 1GB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)
        
        # Try to allocate 100MB
        success = efficiency_manager.allocate_blocks(test_volume, 100 * 1024 * 1024)
        assert success
        assert efficiency_manager.get_used_size(test_volume) > 0

    def test_allocate_blocks_over_limit(self, efficiency_manager, test_volume):
        """Test block allocation beyond limit."""
        requested_size = 1024 * 1024 * 1024  # 1GB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)
        
        # Try to allocate more than available
        success = efficiency_manager.allocate_blocks(test_volume, 2 * 1024 * 1024 * 1024)
        assert not success

    def test_reclaim_space(self, efficiency_manager, test_volume):
        """Test space reclamation."""
        requested_size = 1024 * 1024 * 1024  # 1GB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)
        
        # Allocate some blocks
        efficiency_manager.allocate_blocks(test_volume, 100 * 1024 * 1024)
        initial_used = efficiency_manager.get_used_size(test_volume)
        
        # Reclaim space
        reclaimed = efficiency_manager.reclaim_space(test_volume)
        assert reclaimed > 0
        assert efficiency_manager.get_used_size(test_volume) < initial_used

if __name__ == "__main__":
    pytest.main(["-v", __file__])
