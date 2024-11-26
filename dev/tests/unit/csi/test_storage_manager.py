import pytest
import os
import asyncio
from pathlib import Path
from src.csi.storage_manager import CSIStorageManager
from src.models.models import StorageLocation, Volume


@pytest.fixture
def csi_manager(tmp_path):
    manager = CSIStorageManager(root_path=str(tmp_path))
    yield manager
    # Cleanup any test volumes
    test_volumes = [
        v
        for v in manager.storage_manager.system.volumes.values()
        if v.name.startswith("test-")
    ]
    for volume in test_volumes:
        asyncio.run(manager.delete_volume(volume.id))


@pytest.mark.asyncio
async def test_csi_pool_creation(csi_manager, tmp_path):
    """Test that CSI pool is automatically created"""
    pools = csi_manager.storage_manager.system.pools
    csi_pools = [p for p in pools.values() if p.name == "csi-pool"]
    assert len(csi_pools) == 1
    assert csi_pools[0].location.path == str(tmp_path / "csi")


@pytest.mark.asyncio
async def test_volume_creation(csi_manager):
    """Test creating a new volume"""
    volume_name = "test-volume-1"
    size_bytes = 2 * 1024 * 1024 * 1024  # 2GB

    volume_id = await csi_manager.create_volume(volume_name, size_bytes)
    assert volume_id is not None

    # Verify volume exists in system
    volume = csi_manager.storage_manager.system.volumes.get(volume_id)
    assert volume is not None
    assert volume.name == volume_name
    assert volume.size_gb == 2  # Should round up to nearest GB


@pytest.mark.asyncio
async def test_volume_mounting(csi_manager, tmp_path):
    """Test mounting and unmounting volumes"""
    # Create a test volume
    volume_id = await csi_manager.create_volume(
        "test-mount-volume", 1 * 1024 * 1024 * 1024
    )
    mount_path = tmp_path / "mount-point"

    # Test mounting
    await csi_manager.mount_volume(volume_id, str(mount_path))
    assert mount_path.exists()
    assert mount_path.is_symlink() or mount_path.is_dir()

    # Test unmounting
    await csi_manager.unmount_volume(str(mount_path))
    assert not mount_path.exists()


@pytest.mark.asyncio
async def test_invalid_volume_operations(csi_manager, tmp_path):
    """Test error handling for invalid volume operations"""
    with pytest.raises(ValueError):
        await csi_manager.mount_volume("invalid-id", str(tmp_path / "invalid"))


@pytest.mark.asyncio
async def test_volume_size_rounding(csi_manager):
    """Test that volume sizes are properly rounded up to GB"""
    # Test various sizes
    test_sizes = [
        (500 * 1024 * 1024, 1),  # 500MB -> 1GB
        (1.5 * 1024 * 1024 * 1024, 2),  # 1.5GB -> 2GB
        (2 * 1024 * 1024 * 1024, 2),  # 2GB -> 2GB
    ]

    for size_bytes, expected_gb in test_sizes:
        volume_id = await csi_manager.create_volume("test-size", size_bytes)
        volume = csi_manager.storage_manager.system.volumes.get(volume_id)
        assert volume.size_gb == expected_gb
