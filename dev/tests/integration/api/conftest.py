"""Common test fixtures for API integration tests."""

import pytest
import os
import shutil
from flask import Flask
from src.api.services.fs_manager import FileSystemManager
from src.infrastructure.manager import InfrastructureManager

@pytest.fixture
def test_storage_root():
    """Get test storage root directory."""
    return "/tmp/dfs_test"

@pytest.fixture
def fs_manager(test_storage_root):
    """Create FileSystemManager instance."""
    return FileSystemManager(storage_root=test_storage_root)

@pytest.fixture
def infrastructure():
    """Create InfrastructureManager instance."""
    return InfrastructureManager()

@pytest.fixture(autouse=True)
async def setup_teardown(test_storage_root):
    """Setup and teardown test environment."""
    # Setup
    os.makedirs(test_storage_root, exist_ok=True)
    
    yield
    
    # Teardown
    if os.path.exists(test_storage_root):
        shutil.rmtree(test_storage_root)

@pytest.fixture
def base_app():
    """Create base Flask app."""
    app = Flask(__name__)
    return app
