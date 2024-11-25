"""System service for managing DFS infrastructure components."""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional
from src.storage.infrastructure.hybrid_storage import HybridStorageManager
from src.storage.infrastructure.cluster_manager import StorageClusterManager
from src.storage.infrastructure.active_node import ActiveNode
from src.storage.infrastructure.load_manager import LoadManager
from src.storage.infrastructure.data.consistency_manager import ConsistencyManager
from src.storage.infrastructure.data.replication_manager import ReplicationManager
from src.storage.infrastructure.data.data_protection import DataProtectionManager
from src.storage.infrastructure.models import HybridStorageSystem
from src.api.services.config import current_config

logger = logging.getLogger(__name__)

class SystemService:
    """Manages the DFS system components and their lifecycle."""
    
    def __init__(self, storage_root: str):
        """Initialize the system service."""
        self.storage_root = storage_root
        self.hybrid_storage = HybridStorageManager(storage_root)
        self.cluster_manager = StorageClusterManager()
        # Generate a unique node ID for this instance
        node_id = str(uuid.uuid4())
        self.active_node = ActiveNode(node_id=node_id, data_dir=storage_root)
        self.load_manager = LoadManager()
        self.consistency_manager = ConsistencyManager()
        self.replication_manager = ReplicationManager()
        self.data_protection = DataProtectionManager()
        
        # Initialize system components
        self._init_system()
    
    def _init_system(self):
        """Initialize all system components."""
        try:
            # Register with cluster
            self.cluster_manager.register_node(self.active_node.id)
            
            # Initialize storage system
            self.hybrid_storage.initialize()
            
            # Set up data protection
            self.data_protection.initialize(
                encryption_enabled=current_config.get('encryption_enabled', True),
                key_rotation_days=current_config.get('key_rotation_days', 30)
            )
            
            # Configure replication
            self.replication_manager.initialize(
                replication_factor=current_config.get('replication_factor', 3)
            )
            
            logger.info("System initialization complete")
        except Exception as e:
            logger.error(f"Failed to initialize system: {str(e)}")
            raise
    
    def get_system_status(self) -> dict:
        """Get the current system status."""
        return {
            'node_status': self.active_node.get_status(),
            'cluster_status': self.cluster_manager.get_status(),
            'storage_status': self.hybrid_storage.get_status(),
            'load_status': self.load_manager.get_metrics(),
            'replication_status': self.replication_manager.get_status(),
            'protection_status': self.data_protection.get_status()
        }
    
    def handle_request(self, operation: str, **kwargs) -> Optional[dict]:
        """Handle a storage request with proper consistency and protection."""
        try:
            # Check system health
            if not self.active_node.is_healthy():
                raise SystemError("Node is not healthy")
                
            # Apply consistency rules
            consistency_level = kwargs.get('consistency_level', 'eventual')
            self.consistency_manager.validate_operation(operation, consistency_level)
            
            # Check load and get optimal node
            target_node = self.load_manager.get_optimal_node(operation)
            if target_node != self.active_node.id:
                return self.cluster_manager.forward_request(target_node, operation, **kwargs)
            
            # Execute operation with protection
            with self.data_protection.secure_operation():
                result = self.hybrid_storage.execute_operation(operation, **kwargs)
            
            # Handle replication
            self.replication_manager.replicate_operation(operation, result, **kwargs)
            
            return result
        except Exception as e:
            logger.error(f"Failed to handle request {operation}: {str(e)}")
            raise

    def shutdown(self):
        """Gracefully shutdown the system."""
        try:
            self.active_node.deregister()
            self.cluster_manager.deregister_node(self.active_node.id)
            self.hybrid_storage.shutdown()
            logger.info("System shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
            raise
