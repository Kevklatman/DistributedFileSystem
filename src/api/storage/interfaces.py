from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict, Union, BinaryIO, Tuple
from datetime import datetime

class StorageInterface(ABC):
    """Base interface for all storage operations."""
    
    @abstractmethod
    def write_file(self, path: str, content: Union[bytes, BinaryIO]) -> bool:
        """Write content to a file at the specified path."""
        pass
        
    @abstractmethod
    def read_file(self, path: str) -> Optional[bytes]:
        """Read content from a file at the specified path."""
        pass
        
    @abstractmethod
    def delete_file(self, path: str) -> bool:
        """Delete a file at the specified path."""
        pass
        
    @abstractmethod
    def list_files(self, path: str) -> List[str]:
        """List all files in the specified path."""
        pass
        
    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a file exists at the specified path."""
        pass

class CacheInterface(ABC):
    """Base interface for all caching operations."""
    
    @abstractmethod
    def get(self, key: str, consistency_level: Optional[str] = None) -> Optional[Any]:
        """Get a value from cache."""
        pass
        
    @abstractmethod
    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Put a value in cache."""
        pass
        
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        pass
        
    @abstractmethod
    def clear(self) -> None:
        """Clear all entries from cache."""
        pass

class CloudStorageInterface(StorageInterface):
    """Base interface for cloud storage providers."""
    
    @abstractmethod
    def upload_file(self, file_data: Union[bytes, BinaryIO], object_key: str, bucket: str, **kwargs) -> bool:
        """Upload a file to cloud storage."""
        pass
        
    @abstractmethod
    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        """Download a file from cloud storage."""
        pass
        
    @abstractmethod
    def delete_object(self, object_key: str, bucket: str) -> bool:
        """Delete an object from cloud storage."""
        pass
        
    @abstractmethod
    def list_objects(self, bucket: str, prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        """List objects in a bucket."""
        pass

class MetricsCollector(ABC):
    """Base interface for metrics collection."""
    
    @abstractmethod
    def record_operation_latency(self, operation: str, duration: float) -> None:
        """Record the latency of an operation."""
        pass
        
    @abstractmethod
    def record_resource_usage(self, cpu: float, memory: float, disk_io: float, network_io: float) -> None:
        """Record system resource usage."""
        pass
        
    @abstractmethod
    def record_cache_operation(self, operation: str, hit: bool) -> None:
        """Record cache operation (hit/miss)."""
        pass
        
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        pass

class BaseCloudProvider(CloudStorageInterface):
    """Base implementation for cloud providers with common functionality."""
    
    def delete_file(self, path: str) -> bool:
        """Implementation of StorageInterface.delete_file."""
        bucket, object_key = self._parse_path(path)
        return self.delete_object(object_key, bucket)
    
    def read_file(self, path: str) -> Optional[bytes]:
        """Implementation of StorageInterface.read_file."""
        bucket, object_key = self._parse_path(path)
        return self.download_file(object_key, bucket)
    
    def write_file(self, path: str, content: Union[bytes, BinaryIO]) -> bool:
        """Implementation of StorageInterface.write_file."""
        bucket, object_key = self._parse_path(path)
        return self.upload_file(content, object_key, bucket)
    
    def list_files(self, path: str) -> List[str]:
        """Implementation of StorageInterface.list_files."""
        bucket, prefix = self._parse_path(path)
        objects = self.list_objects(bucket, prefix)
        return [obj['Key'] for obj in objects if 'Key' in obj]
    
    def exists(self, path: str) -> bool:
        """Implementation of StorageInterface.exists."""
        try:
            bucket, object_key = self._parse_path(path)
            return self.download_file(object_key, bucket) is not None
        except:
            return False
    
    def _parse_path(self, path: str) -> Tuple[str, str]:
        """Parse a path into bucket and object key."""
        parts = path.lstrip('/').split('/', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid path format: {path}")
        return parts[0], parts[1]
