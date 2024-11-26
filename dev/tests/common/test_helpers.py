"""Common test utilities for path and directory handling."""

import tempfile
from pathlib import Path
import pytest
import shutil

# Project root is 3 levels up from this file
PROJECT_ROOT = Path(__file__).parent.parent.parent


def get_test_path(*paths):
    """Get a path relative to project root."""
    return PROJECT_ROOT.joinpath(*paths)


class TestDirectoryManager:
    """Context manager for test directories with standard structure."""

    def __init__(self, base_path=None):
        self.base_path = base_path
        self.temp_dir = None

    def __enter__(self):
        if self.base_path:
            self.temp_dir = Path(self.base_path)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.temp_dir = Path(tempfile.mkdtemp())

        # Create standard test directory structure
        (self.temp_dir / "volumes").mkdir(exist_ok=True)
        (self.temp_dir / "metadata").mkdir(exist_ok=True)
        (self.temp_dir / "cache").mkdir(exist_ok=True)
        (self.temp_dir / "mounts").mkdir(exist_ok=True)
        return self.temp_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.base_path and self.temp_dir:
            shutil.rmtree(self.temp_dir)


@pytest.fixture
def test_dir():
    """Fixture providing a temporary test directory with standard structure."""
    with TestDirectoryManager() as temp_dir:
        yield temp_dir


@pytest.fixture
def persistent_test_dir(tmp_path):
    """Fixture providing a persistent test directory that survives test session."""
    with TestDirectoryManager(tmp_path) as test_dir:
        yield test_dir
