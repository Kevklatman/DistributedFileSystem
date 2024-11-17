import os
import sys
import pytest

# Set environment variables before any imports
os.environ['STORAGE_ENV'] = 'local'
os.environ['API_PORT'] = '8001'
os.environ['API_HOST'] = '0.0.0.0'

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/api')))

from storage_backend import LocalStorageBackend
from fs_manager import FileSystemManager
import app

@pytest.fixture(autouse=True)
def setup_test_storage():
    """Set up and clean up test storage directory"""
    test_storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_storage'))
    os.environ['LOCAL_STORAGE_DIR'] = test_storage_dir
    
    # Create test storage directory
    os.makedirs(test_storage_dir, exist_ok=True)
    
    yield
    
    # Clean up test storage directory
    if os.path.exists(test_storage_dir):
        for root, dirs, files in os.walk(test_storage_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(test_storage_dir)

@pytest.fixture
def fs_manager():
    """Create a fresh FileSystemManager for each test"""
    manager = FileSystemManager()
    yield manager

@pytest.fixture
def storage_backend(fs_manager):
    """Create a fresh LocalStorageBackend for each test"""
    backend = LocalStorageBackend(fs_manager)
    yield backend

@pytest.fixture
def test_app():
    """Create a fresh Flask app for each test"""
    yield app.app

@pytest.fixture
def client(test_app):
    """Create a test client"""
    return test_app.test_client()

@pytest.fixture
def runner(test_app):
    """Create a CLI test runner"""
    return test_app.test_cli_runner()
