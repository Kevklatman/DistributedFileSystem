"""Global test configuration and fixtures."""
import pytest
from pathlib import Path
import os

from .common.test_helpers import TestDirectoryManager, PROJECT_ROOT

# Add project root to Python path for imports
import sys
sys.path.insert(0, str(PROJECT_ROOT))

# Test environment configuration
os.environ.setdefault('STORAGE_ENV', 'test')
os.environ.setdefault('NODE_ID', 'test-node-1')
os.environ.setdefault('POD_IP', '127.0.0.1')

@pytest.fixture(scope="session")
def test_storage():
    """Create a session-wide test storage directory."""
    with TestDirectoryManager() as storage_dir:
        os.environ['TEST_STORAGE_DIR'] = str(storage_dir)
        yield storage_dir

@pytest.fixture
def volume_dir(test_storage):
    """Get the volumes directory."""
    return test_storage / "volumes"

@pytest.fixture
def metadata_dir(test_storage):
    """Get the metadata directory."""
    return test_storage / "metadata"

@pytest.fixture
def cache_dir(test_storage):
    """Get the cache directory."""
    return test_storage / "cache"

@pytest.fixture
def mount_dir(test_storage):
    """Get the mounts directory."""
    return test_storage / "mounts"
