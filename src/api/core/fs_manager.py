import os
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class FileSystemManager:
    """Manages file system operations for the distributed file system"""

    def __init__(self):
        self.directories: Dict[str, Dict] = {}
        self.files: Dict[str, Dict] = {}

        # Get storage directory from environment variable or use default
        storage_dir = os.environ.get('LOCAL_STORAGE_DIR', os.path.abspath('./storage'))
        self.root_dir = os.path.join(storage_dir, 'buckets')

        # Ensure root directory exists
        os.makedirs(self.root_dir, exist_ok=True)

    def createDirectory(self, path: str) -> bool:
        """Create a directory at the specified path"""
        try:
            # Normalize path
            path = os.path.normpath(path)

            # Check if directory already exists
            if path in self.directories:
                logger.warning(f"Directory already exists: {path}")
                return False

            # Create physical directory
            os.makedirs(path, exist_ok=True)

            # Add to in-memory tracking
            self.directories[path] = {
                'path': path,
                'files': [],
                'subdirs': []
            }

            # Update parent directory
            parent_dir = os.path.dirname(path)
            if parent_dir in self.directories:
                if path not in self.directories[parent_dir]['subdirs']:
                    self.directories[parent_dir]['subdirs'].append(path)

            logger.info(f"Created directory: {path}")
            return True

        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            return False

    def listDirectory(self, path: str) -> Tuple[List[str], List[str]]:
        """List contents of a directory"""
        try:
            # Normalize path
            path = os.path.normpath(path)

            if path not in self.directories:
                logger.error(f"Directory does not exist: {path}")
                return [], []

            return (
                self.directories[path]['files'],
                self.directories[path]['subdirs']
            )

        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return [], []

    def deleteDirectory(self, path: str) -> bool:
        """Delete a directory and all its contents"""
        try:
            # Normalize path
            path = os.path.normpath(path)

            if path not in self.directories:
                logger.error(f"Directory does not exist: {path}")
                return False

            # Remove physical directory
            os.rmdir(path)

            # Update parent directory
            parent_dir = os.path.dirname(path)
            if parent_dir in self.directories:
                if path in self.directories[parent_dir]['subdirs']:
                    self.directories[parent_dir]['subdirs'].remove(path)

            # Remove from in-memory tracking
            del self.directories[path]

            logger.info(f"Deleted directory: {path}")
            return True

        except Exception as e:
            logger.error(f"Error deleting directory {path}: {e}")
            return False

    def createFile(self, path: str, content: bytes = b'') -> bool:
        """Create a file at the specified path"""
        try:
            # Normalize path
            path = os.path.normpath(path)

            # Check if file already exists
            if path in self.files:
                logger.warning(f"File already exists: {path}")
                return False

            # Create parent directories if they don't exist
            parent_dir = os.path.dirname(path)
            if not os.path.exists(parent_dir):
                self.createDirectory(parent_dir)

            # Write file
            with open(path, 'wb') as f:
                f.write(content)

            # Add to in-memory tracking
            self.files[path] = {
                'path': path,
                'size': len(content)
            }

            # Update parent directory
            if parent_dir in self.directories:
                if path not in self.directories[parent_dir]['files']:
                    self.directories[parent_dir]['files'].append(path)

            logger.info(f"Created file: {path}")
            return True

        except Exception as e:
            logger.error(f"Error creating file {path}: {e}")
            return False
