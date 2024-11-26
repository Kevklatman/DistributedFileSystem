"""Storage interfaces for the distributed file system."""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict, Union, BinaryIO, Tuple
from datetime import datetime


class BaseCloudProvider(ABC):
    """Base interface for cloud storage providers."""

    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file to cloud storage."""
        pass

    @abstractmethod
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from cloud storage."""
        pass

    @abstractmethod
    def delete_file(self, remote_path: str) -> bool:
        """Delete a file from cloud storage."""
        pass

    @abstractmethod
    def list_files(self, prefix: str = "") -> List[str]:
        """List files in cloud storage with optional prefix."""
        pass

    @abstractmethod
    def get_file_metadata(self, remote_path: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a file in cloud storage."""
        pass


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
    def clear(self) -> bool:
        """Clear all values from cache."""
        pass


class CSINodeInterface(ABC):
    """Interface for CSI node service operations."""

    @abstractmethod
    def node_stage_volume(
        self,
        volume_id: str,
        staging_target_path: str,
        volume_context: Dict[str, str],
        secrets: Dict[str, str],
    ) -> bool:
        """Stage a volume on the node."""
        pass

    @abstractmethod
    def node_unstage_volume(self, volume_id: str, staging_target_path: str) -> bool:
        """Unstage a volume from the node."""
        pass

    @abstractmethod
    def node_publish_volume(
        self,
        volume_id: str,
        target_path: str,
        staging_target_path: str,
        volume_capability: Dict[str, Any],
    ) -> bool:
        """Publish a volume on the node."""
        pass

    @abstractmethod
    def node_unpublish_volume(self, volume_id: str, target_path: str) -> bool:
        """Unpublish a volume from the node."""
        pass

    @abstractmethod
    def node_get_capabilities(self) -> List[str]:
        """Get the capabilities of the node plugin."""
        pass

    @abstractmethod
    def node_get_info(self) -> Dict[str, str]:
        """Get information about the node."""
        pass


class CSIControllerInterface(ABC):
    """Interface for CSI controller service operations."""

    @abstractmethod
    def create_volume(
        self,
        name: str,
        capacity_bytes: int,
        volume_capabilities: List[Dict[str, Any]],
        parameters: Dict[str, str],
        secrets: Dict[str, str],
    ) -> Dict[str, Any]:
        """Create a new volume."""
        pass

    @abstractmethod
    def delete_volume(self, volume_id: str, secrets: Dict[str, str]) -> bool:
        """Delete a volume."""
        pass

    @abstractmethod
    def controller_publish_volume(
        self,
        volume_id: str,
        node_id: str,
        volume_capability: Dict[str, Any],
        readonly: bool,
        secrets: Dict[str, str],
    ) -> Dict[str, str]:
        """Publish a volume to a node."""
        pass

    @abstractmethod
    def controller_unpublish_volume(
        self, volume_id: str, node_id: str, secrets: Dict[str, str]
    ) -> bool:
        """Unpublish a volume from a node."""
        pass

    @abstractmethod
    def validate_volume_capabilities(
        self,
        volume_id: str,
        volume_capabilities: List[Dict[str, Any]],
        parameters: Dict[str, str],
    ) -> bool:
        """Validate volume capabilities."""
        pass

    @abstractmethod
    def get_capacity(
        self, volume_capabilities: List[Dict[str, Any]], parameters: Dict[str, str]
    ) -> int:
        """Get the capacity of the storage pool."""
        pass

    @abstractmethod
    def controller_get_capabilities(self) -> List[str]:
        """Get the capabilities of the controller plugin."""
        pass


class MetricsCollector(ABC):
    """Base interface for metrics collection."""

    @abstractmethod
    def record_operation_latency(self, operation: str, duration: float) -> None:
        """Record the latency of an operation."""
        pass

    @abstractmethod
    def record_resource_usage(
        self, cpu: float, memory: float, disk_io: float, network_io: float
    ) -> None:
        """Record system resource usage."""
        pass

    @abstractmethod
    def record_volume_operation(
        self, operation: str, volume_id: str, success: bool, duration: float
    ) -> None:
        """Record volume operation metrics."""
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        pass
