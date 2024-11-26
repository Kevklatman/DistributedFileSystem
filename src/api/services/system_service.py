"""System service for managing DFS infrastructure components."""

import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any

from src.storage.infrastructure.hybrid_storage import HybridStorageManager
from src.storage.infrastructure.cluster_manager import StorageClusterManager
from src.storage.infrastructure.data.data_protection import DataProtectionManager
from src.storage.infrastructure.data.replication_manager import ReplicationManager
from src.storage.infrastructure.data.consistency_manager import ConsistencyManager
from src.storage.infrastructure.load_manager import LoadManager
from src.storage.infrastructure.active_node import ActiveNode

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "replication_factor": 3,
    "backup_retention_days": 30,
    "snapshot_retention_days": 7,
    "auto_backup_enabled": True,
}


class SystemService:
    """Manages the DFS system components and their lifecycle."""

    def __init__(self, storage_root: str):
        """Initialize the system service."""
        self.storage_root = Path(storage_root)

        # Initialize storage components first
        self.hybrid_storage = HybridStorageManager(str(self.storage_root))

        # Initialize cluster management
        self.cluster_manager = StorageClusterManager()
        node_id = str(uuid.uuid4())
        self.active_node = ActiveNode(
            node_id=node_id,
            data_dir=str(self.storage_root),
            quorum_size=DEFAULT_CONFIG["replication_factor"],
        )

        # Initialize data management components
        self.load_manager = LoadManager()
        self.consistency_manager = ConsistencyManager()
        self.replication_manager = ReplicationManager()

        # Initialize data protection with required parameters
        data_protection_path = self.storage_root / "protection"
        self.data_protection = DataProtectionManager(
            data_path=data_protection_path, storage_manager=self.hybrid_storage
        )

        # Initialize system components
        self._init_system()

    def _init_system(self):
        """Initialize all system components."""
        try:
            # Create necessary directories
            self.storage_root.mkdir(parents=True, exist_ok=True)
            data_protection_dir = self.data_protection.data_path
            data_protection_dir.mkdir(parents=True, exist_ok=True)

            # Register with cluster
            if not self.cluster_manager.register_node(self.active_node.node_id):
                logger.warning(
                    "Failed to register node with cluster, continuing in standalone mode"
                )

            # Initialize storage system
            if not self.hybrid_storage.initialize():
                raise RuntimeError("Failed to initialize hybrid storage")

            # Configure replication
            if not self.replication_manager.initialize(
                replication_factor=DEFAULT_CONFIG["replication_factor"]
            ):
                raise RuntimeError("Failed to initialize replication manager")

            # Initialize data protection with default settings
            if not self.data_protection.initialize(
                backup_retention_days=DEFAULT_CONFIG["backup_retention_days"],
                snapshot_retention_days=DEFAULT_CONFIG["snapshot_retention_days"],
                auto_backup_enabled=DEFAULT_CONFIG["auto_backup_enabled"],
            ):
                raise RuntimeError("Failed to initialize data protection")

            logger.info("System initialization complete")
        except Exception as e:
            logger.error(f"Failed to initialize system: {str(e)}")
            raise

    def get_system_status(self) -> dict:
        """Get the current system status."""
        return {
            "node_status": self.active_node.get_status(),
            "cluster_status": self.cluster_manager.get_status(),
            "storage_status": self.hybrid_storage.get_status(),
            "load_status": self.load_manager.get_metrics(),
            "replication_status": self.replication_manager.get_status(),
            "protection_status": self.data_protection.get_status(),
        }

    def handle_request(self, operation: str, **kwargs) -> Optional[dict]:
        """Handle a storage request with proper consistency and protection."""
        try:
            # Check system health
            if not self.active_node.is_healthy():
                raise SystemError("Node is not healthy")

            # Apply consistency rules
            consistency_level = kwargs.get("consistency_level", "eventual")
            self.consistency_manager.validate_operation(operation, consistency_level)

            # Check load and get optimal node
            target_node = self.load_manager.get_optimal_node(operation)
            if target_node != self.active_node.id:
                return self.cluster_manager.forward_request(
                    target_node, operation, **kwargs
                )

            # Execute operation with protection
            with self.data_protection.secure_operation():
                result = self.hybrid_storage.execute_operation(operation, **kwargs)

            # Handle replication
            self.replication_manager.replicate_operation(operation, result, **kwargs)

            return result
        except Exception as e:
            logger.error(f"Failed to handle request {operation}: {str(e)}")
            raise

    async def shutdown(self):
        """Gracefully shutdown the system."""
        try:
            await self.active_node.deregister()
            self.cluster_manager.deregister_node(self.active_node.node_id)
            await self.hybrid_storage.shutdown()
            logger.info("System shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
            raise
