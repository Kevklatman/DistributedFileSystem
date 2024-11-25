"""Infrastructure manager for coordinating all system components."""

import logging
import asyncio
from typing import Dict, Optional, List
from pathlib import Path

from ..config.infrastructure_config import infrastructure_config
from ..storage.infrastructure.node import StorageNode
from ..storage.infrastructure.data.sync_manager import SyncManager
from ..storage.infrastructure.data.cache_store import CacheStore
from ..storage.infrastructure.data.consistency_manager import ConsistencyManager
from ..storage.infrastructure.data.replication_manager import ReplicationManager
from ..storage.infrastructure.data.data_protection import DataProtectionManager
from ..storage.infrastructure.load_manager import LoadManager
from ..storage.infrastructure.cluster_manager import StorageClusterManager
from ..storage.infrastructure.providers import AWSS3Provider, GCPStorageProvider, AzureBlobProvider

logger = logging.getLogger(__name__)

class InfrastructureManager:
    """Manages and coordinates all infrastructure components."""

    def __init__(self):
        """Initialize infrastructure manager."""
        self.config = infrastructure_config
        self._init_components()

    def _init_components(self):
        """Initialize all infrastructure components."""
        # Initialize core components
        self.cluster_manager = StorageClusterManager()
        self.load_manager = LoadManager()
        
        # Initialize cache store
        if self.config.cache.enabled:
            self.cache_store = CacheStore(
                max_size=self.config.cache.max_size_mb * 1024 * 1024,  # Convert to bytes
                ttl_seconds=self.config.cache.ttl_seconds
            )
        else:
            self.cache_store = None
        
        # Initialize data management
        self.sync_manager = SyncManager(cache=self.cache_store)
        self.consistency_manager = ConsistencyManager()
        self.replication_manager = ReplicationManager(
            min_replicas=self.config.storage.replication_factor
        )
        self.data_protection = DataProtectionManager(
            Path(self.config.storage.storage_root),
            self
        )

        # Initialize cloud providers
        self.cloud_providers = {}
        if self.config.cloud_providers['aws']['enabled']:
            self.cloud_providers['aws'] = AWSS3Provider(
                aws_access_key_id=self.config.cloud_providers['aws']['access_key'],
                aws_secret_access_key=self.config.cloud_providers['aws']['secret_key'],
                region_name=self.config.cloud_providers['aws']['region']
            )
        
        if self.config.cloud_providers['gcp']['enabled']:
            self.cloud_providers['gcp'] = GCPStorageProvider()
        
        if self.config.cloud_providers['azure']['enabled']:
            self.cloud_providers['azure'] = AzureBlobProvider(
                connection_string=self.config.cloud_providers['azure']['connection_string']
            )

    async def start(self):
        """Start all infrastructure components."""
        try:
            # Start cluster management
            await self.cluster_manager.start()
            
            # Start data management services
            self.sync_manager.start()
            
            # Start monitoring
            if self.config.metrics_enabled:
                self.load_manager.start_monitoring()

            logger.info("Infrastructure components started successfully")
        except Exception as e:
            logger.error(f"Failed to start infrastructure: {str(e)}")
            raise

    async def stop(self):
        """Stop all infrastructure components gracefully."""
        try:
            # Stop cluster management
            await self.cluster_manager.stop()
            
            # Stop data management services
            self.sync_manager.stop()
            
            # Stop monitoring
            if self.config.metrics_enabled:
                self.load_manager.stop_monitoring()

            logger.info("Infrastructure components stopped successfully")
        except Exception as e:
            logger.error(f"Failed to stop infrastructure: {str(e)}")
            raise

    async def handle_storage_operation(self, operation: str, **kwargs):
        """Handle a storage operation with proper infrastructure coordination."""
        try:
            # Check system health
            if not await self.cluster_manager.is_healthy():
                raise SystemError("System is not healthy")

            # Apply consistency rules
            consistency_level = kwargs.get('consistency_level', 'eventual')
            await self.consistency_manager.validate_operation(operation, consistency_level)

            # Check cache if enabled
            if self.cache_store and operation.startswith('get'):
                cache_key = kwargs.get('key')
                cached_data = self.cache_store.get(cache_key, consistency_level)
                if cached_data:
                    return cached_data

            # Get optimal node based on load
            target_node = await self.load_manager.get_optimal_node(operation)
            
            # Execute operation with protection
            async with self.data_protection.secure_operation():
                # Choose appropriate storage backend
                if kwargs.get('storage_class') == 'cloud':
                    provider = self.cloud_providers.get(kwargs.get('cloud_provider', 'aws'))
                    if not provider:
                        raise ValueError(f"Cloud provider {kwargs.get('cloud_provider')} not configured")
                    result = await provider.execute_operation(operation, **kwargs)
                else:
                    # Use local storage
                    result = await target_node.execute_operation(operation, **kwargs)

            # Handle replication if needed
            if operation.startswith(('put', 'delete')):
                await self.replication_manager.replicate_operation(operation, result, **kwargs)

            # Update cache if enabled
            if self.cache_store and operation.startswith('put'):
                self.cache_store.put(kwargs.get('key'), result)

            return result

        except Exception as e:
            logger.error(f"Failed to handle storage operation {operation}: {str(e)}")
            raise

    def get_system_status(self) -> Dict:
        """Get current status of all infrastructure components."""
        return {
            'cluster_status': self.cluster_manager.get_status(),
            'storage_nodes': self.cluster_manager.get_active_nodes(),
            'load_status': self.load_manager.get_current_metrics(),
            'cache_status': {
                'enabled': bool(self.cache_store),
                'size': self.cache_store.get_size() if self.cache_store else 0,
                'hit_rate': self.cache_store.get_hit_rate() if self.cache_store else 0
            } if self.config.cache.enabled else None,
            'cloud_providers': {
                provider: {'enabled': True} for provider in self.cloud_providers
            },
            'replication_status': self.replication_manager.get_status(),
            'protection_status': self.data_protection.get_status()
        }
