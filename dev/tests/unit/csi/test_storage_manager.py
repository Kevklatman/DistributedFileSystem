"""Unit tests for the CSI Storage Manager."""

import pytest
import os
import asyncio
from pathlib import Path
from typing import Dict, List

from src.csi.storage_manager import CSIStorageManager
from src.models.models import StorageLocation, Volume
from src.tests.common.test_utils import (
    create_test_volume,
    generate_test_data,
    create_test_storage_pool,
    simulate_network_latency
)

# Constants for testing
TEST_VOLUME_PREFIX = "test-"
GIGABYTE = 1024 * 1024 * 1024


@pytest.fixture
def csi_manager(tmp_path):
    """Create a CSI storage manager instance for testing."""
    manager = CSIStorageManager(root_path=str(tmp_path))
    yield manager
    # Cleanup any test volumes
    test_volumes = [
        v
        for v in manager.storage_manager.system.volumes.values()
        if v.name.startswith(TEST_VOLUME_PREFIX)
    ]
    for volume in test_volumes:
        asyncio.run(manager.delete_volume(volume.id))


@pytest.fixture
async def test_volume(csi_manager) -> Dict[str, str]:
    """Create a test volume and return its details."""
    volume_name = f"{TEST_VOLUME_PREFIX}volume-{os.urandom(4).hex()}"
    size_bytes = 2 * GIGABYTE
    volume_id = await csi_manager.create_volume(volume_name, size_bytes)
    return {"id": volume_id, "name": volume_name, "size": size_bytes}


@pytest.mark.asyncio
async def test_csi_pool_creation(csi_manager, tmp_path):
    """Test that CSI pool is automatically created with correct properties."""
    pools = csi_manager.storage_manager.system.storage_pools
    csi_pools = [p for p in pools.values() if p.name == "csi-pool"]
    assert len(csi_pools) == 1
    
    csi_pool = csi_pools[0]
    assert csi_pool.location.path == str(tmp_path / "csi")
    assert csi_pool.is_thin_provisioned
    assert csi_pool.available_capacity_gb >= 0
    assert csi_pool.total_capacity_gb > 0


@pytest.mark.asyncio
async def test_volume_creation_with_various_sizes(csi_manager):
    """Test creating volumes with different sizes and verify rounding behavior."""
    test_cases = [
        (500 * 1024 * 1024, 1),      # 500MB -> 1GB
        (1.5 * GIGABYTE, 2),         # 1.5GB -> 2GB
        (2 * GIGABYTE, 2),           # 2GB -> 2GB
        (2.1 * GIGABYTE, 3),         # 2.1GB -> 3GB
        (10.7 * GIGABYTE, 11)        # 10.7GB -> 11GB
    ]

    for size_bytes, expected_gb in test_cases:
        volume_name = f"{TEST_VOLUME_PREFIX}vol-{os.urandom(4).hex()}"
        volume_id = await csi_manager.create_volume(volume_name, size_bytes)
        
        volume = csi_manager.storage_manager.system.volumes.get(volume_id)
        assert volume is not None
        assert volume.name == volume_name
        assert volume.size_gb == expected_gb
        assert volume.size_bytes >= size_bytes


@pytest.mark.asyncio
async def test_volume_mounting_operations(csi_manager, tmp_path, test_volume):
    """Test comprehensive volume mounting operations including edge cases."""
    mount_path = tmp_path / "mount-point"
    volume_id = test_volume["id"]

    # Test basic mounting
    await csi_manager.mount_volume(volume_id, str(mount_path))
    assert mount_path.exists()
    assert mount_path.is_symlink() or mount_path.is_dir()

    # Test writing data to mounted volume
    test_file = mount_path / "test.txt"
    test_data = "Hello, CSI!"
    test_file.write_text(test_data)
    assert test_file.read_text() == test_data

    # Test unmounting
    await csi_manager.unmount_volume(str(mount_path))
    assert not mount_path.exists()

    # Test remounting at a different location
    new_mount_path = tmp_path / "new-mount-point"
    await csi_manager.mount_volume(volume_id, str(new_mount_path))
    assert new_mount_path.exists()
    
    # Verify data persistence
    assert (new_mount_path / "test.txt").read_text() == test_data
    
    # Cleanup
    await csi_manager.unmount_volume(str(new_mount_path))


@pytest.mark.asyncio
async def test_concurrent_volume_operations(csi_manager, tmp_path):
    """Test handling of concurrent volume operations."""
    volume_count = 5
    size_bytes = GIGABYTE
    
    # Create multiple volumes concurrently
    async def create_volume(index: int):
        name = f"{TEST_VOLUME_PREFIX}concurrent-{index}"
        return await csi_manager.create_volume(name, size_bytes)
    
    volume_ids = await asyncio.gather(
        *[create_volume(i) for i in range(volume_count)]
    )
    
    assert len(volume_ids) == volume_count
    assert len(set(volume_ids)) == volume_count  # All IDs should be unique
    
    # Mount volumes concurrently
    mount_paths = [tmp_path / f"mount-{i}" for i in range(volume_count)]
    await asyncio.gather(
        *[csi_manager.mount_volume(vid, str(path)) 
          for vid, path in zip(volume_ids, mount_paths)]
    )
    
    # Verify all mounts
    for path in mount_paths:
        assert path.exists()
    
    # Unmount volumes concurrently
    await asyncio.gather(
        *[csi_manager.unmount_volume(str(path)) for path in mount_paths]
    )
    
    # Verify all unmounts
    for path in mount_paths:
        assert not path.exists()


@pytest.mark.asyncio
async def test_invalid_volume_operations(csi_manager, tmp_path, test_volume):
    """Test error handling for invalid volume operations."""
    invalid_id = "invalid-id"
    mount_path = tmp_path / "invalid-mount"
    
    # Test invalid volume ID
    with pytest.raises(ValueError):
        await csi_manager.mount_volume(invalid_id, str(mount_path))
    
    # Test invalid mount path
    invalid_path = tmp_path / "nonexistent" / "path"
    with pytest.raises(ValueError):
        await csi_manager.mount_volume(test_volume["id"], str(invalid_path))
    
    # Test mounting same volume twice
    mount_path1 = tmp_path / "mount1"
    mount_path2 = tmp_path / "mount2"
    
    await csi_manager.mount_volume(test_volume["id"], str(mount_path1))
    with pytest.raises(ValueError):
        await csi_manager.mount_volume(test_volume["id"], str(mount_path2))
    
    # Cleanup
    await csi_manager.unmount_volume(str(mount_path1))


@pytest.mark.asyncio
async def test_volume_deletion(csi_manager, test_volume):
    """Test volume deletion and cleanup."""
    volume_id = test_volume["id"]
    
    # Verify volume exists
    assert volume_id in csi_manager.storage_manager.system.volumes
    
    # Delete volume
    await csi_manager.delete_volume(volume_id)
    
    # Verify volume is removed
    assert volume_id not in csi_manager.storage_manager.system.volumes
    
    # Verify deletion of non-existent volume raises error
    with pytest.raises(ValueError):
        await csi_manager.delete_volume(volume_id)


@pytest.mark.asyncio
async def test_volume_metadata(csi_manager):
    """Test volume metadata operations and persistence."""
    # Create volume with metadata
    volume_name = f"{TEST_VOLUME_PREFIX}metadata-test"
    size_bytes = GIGABYTE
    metadata = {
        "description": "Test volume",
        "owner": "test-user",
        "created": "2023-01-01"
    }
    
    volume_id = await csi_manager.create_volume(
        volume_name, 
        size_bytes,
        metadata=metadata
    )
    
    # Verify metadata
    volume = csi_manager.storage_manager.system.volumes.get(volume_id)
    assert volume is not None
    assert volume.metadata == metadata
    
    # Update metadata
    new_metadata = {**metadata, "updated": "2023-01-02"}
    await csi_manager.update_volume_metadata(volume_id, new_metadata)
    
    # Verify updated metadata
    volume = csi_manager.storage_manager.system.volumes.get(volume_id)
    assert volume.metadata == new_metadata
    
    # Test invalid metadata operations
    with pytest.raises(ValueError):
        await csi_manager.update_volume_metadata("invalid-id", {})
    
    # Test metadata persistence after mount/unmount
    mount_path = Path(csi_manager.storage_manager.root_path) / "metadata-test-mount"
    await csi_manager.mount_volume(volume_id, str(mount_path))
    await csi_manager.unmount_volume(str(mount_path))
    
    # Verify metadata still exists
    volume = csi_manager.storage_manager.system.volumes.get(volume_id)
    assert volume.metadata == new_metadata
