"""Unit tests for storage efficiency functionality."""

import pytest
from unittest.mock import MagicMock, patch

from src.storage.infrastructure.storage_efficiency import StorageEfficiencyManager
from src.models.models import (
    Volume,
    DeduplicationState,
    CompressionState,
    ThinProvisioningState,
    StoragePool,
)

class TestDeduplication:
    @pytest.fixture
    def efficiency_manager(self):
        return StorageEfficiencyManager(
            dedup_enabled=True,
            compression_enabled=True,
        )

    @pytest.fixture
    def test_volume(self):
        return Volume(
            name="test-volume",
            size_gb=100,
        )

    def test_deduplicate_file_new_content(self, efficiency_manager, test_volume):
        """Test deduplication with new content."""
        content = b"new test content"
        result = efficiency_manager.deduplicate_data(test_volume, content)
        assert result.is_duplicate == False
        assert result.content == content

    def test_deduplicate_file_duplicate_content(self, efficiency_manager, test_volume):
        """Test deduplication with duplicate content."""
        content = b"test content"
        # First write
        efficiency_manager.deduplicate_data(test_volume, content)
        # Second write of same content
        result = efficiency_manager.deduplicate_data(test_volume, content)
        assert result.is_duplicate == True

class TestCompression:
    @pytest.fixture
    def efficiency_manager(self):
        return StorageEfficiencyManager(
            dedup_enabled=True,
            compression_enabled=True,
        )

    def test_compress_data_zlib(self, efficiency_manager):
        """Test compression using zlib."""
        data = b"test data" * 100
        compressed = efficiency_manager.compress_data(data, algorithm="zlib")
        assert len(compressed) < len(data)

    def test_compress_data_lz4(self, efficiency_manager):
        """Test compression using lz4."""
        data = b"test data" * 100
        compressed = efficiency_manager.compress_data(data, algorithm="lz4")
        assert len(compressed) < len(data)

    def test_compress_data_snappy(self, efficiency_manager):
        """Test compression using snappy."""
        data = b"test data" * 100
        compressed = efficiency_manager.compress_data(data, algorithm="snappy")
        assert len(compressed) < len(data)

    def test_invalid_compression_algorithm(self, efficiency_manager):
        """Test handling of invalid compression algorithm."""
        data = b"test data"
        with pytest.raises(ValueError):
            efficiency_manager.compress_data(data, algorithm="invalid")

    def test_adaptive_compression(self, efficiency_manager):
        """Test adaptive compression algorithm selection."""
        data = b"test data" * 100
        algorithm = efficiency_manager.select_compression_algorithm(data)
        assert algorithm in ["zlib", "lz4", "snappy"]

class TestThinProvisioning:
    @pytest.fixture
    def efficiency_manager(self):
        return StorageEfficiencyManager(
            dedup_enabled=True,
            compression_enabled=True,
        )

    @pytest.fixture
    def test_volume(self):
        return Volume(
            name="test-volume",
            size_gb=100,
        )

    def test_setup_thin_provisioning(self, efficiency_manager, test_volume):
        """Test thin provisioning setup."""
        requested_size = 1000  # GB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)
        assert test_volume.thin_provisioning.enabled
        assert test_volume.thin_provisioning.requested_size == requested_size

    def test_allocate_blocks_success(self, efficiency_manager, test_volume):
        """Test successful block allocation."""
        requested_size = 1000  # GB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)
        allocated = efficiency_manager.allocate_blocks(test_volume, 100)
        assert allocated == True

    def test_allocate_blocks_over_limit(self, efficiency_manager, test_volume):
        """Test block allocation beyond limit."""
        requested_size = 100  # GB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)
        with pytest.raises(ValueError):
            efficiency_manager.allocate_blocks(test_volume, requested_size * 2)

    def test_reclaim_space(self, efficiency_manager, test_volume):
        """Test space reclamation."""
        requested_size = 1000  # GB
        efficiency_manager.setup_thin_provisioning(test_volume, requested_size)
        efficiency_manager.allocate_blocks(test_volume, 100)
        reclaimed = efficiency_manager.reclaim_space(test_volume, 50)
        assert reclaimed == 50

if __name__ == "__main__":
    pytest.main(["-v", __file__])
