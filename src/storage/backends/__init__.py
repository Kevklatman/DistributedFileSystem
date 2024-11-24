"""
Storage backend initialization module.
"""

from typing import Optional
from core.fs_manager import FileSystemManager
from core.config import STORAGE_ENV
from .base import StorageBackend
from .local_backend import LocalStorageBackend
from .aws_backend import AWSStorageBackend

def get_storage_backend(fs_manager: Optional[FileSystemManager] = None) -> StorageBackend:
    """Factory function to get the appropriate storage backend"""
    if STORAGE_ENV == 'aws':
        return AWSStorageBackend()
    else:
        if fs_manager is None:
            raise ValueError("FileSystemManager is required for local storage backend")
        return LocalStorageBackend(fs_manager)

__all__ = [
    'StorageBackend',
    'LocalStorageBackend',
    'AWSStorageBackend',
    'get_storage_backend'
]