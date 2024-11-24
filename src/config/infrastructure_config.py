"""Infrastructure configuration management."""

import os
from dataclasses import dataclass
from typing import Dict, Optional, List
from pathlib import Path

@dataclass
class StorageConfig:
    storage_root: str
    replication_factor: int
    min_nodes: int
    max_volume_size: int
    compression_enabled: bool
    deduplication_enabled: bool
    encryption_enabled: bool

@dataclass
class NetworkConfig:
    bind_address: str
    port: int
    max_connections: int
    timeout: int

@dataclass
class CacheConfig:
    enabled: bool
    max_size_mb: int
    ttl_seconds: int
    eviction_policy: str

@dataclass
class InfrastructureConfig:
    storage: StorageConfig
    network: NetworkConfig
    cache: CacheConfig
    cloud_providers: Dict[str, Dict]
    metrics_enabled: bool
    debug_mode: bool

def load_infrastructure_config() -> InfrastructureConfig:
    """Load infrastructure configuration from environment variables."""
    storage_config = StorageConfig(
        storage_root=os.getenv('STORAGE_ROOT', '/data/dfs'),
        replication_factor=int(os.getenv('REPLICATION_FACTOR', '3')),
        min_nodes=int(os.getenv('MIN_NODES', '1')),
        max_volume_size=int(os.getenv('MAX_VOLUME_SIZE', str(1024 * 1024 * 1024 * 1024))),  # 1TB
        compression_enabled=os.getenv('COMPRESSION_ENABLED', 'true').lower() == 'true',
        deduplication_enabled=os.getenv('DEDUPLICATION_ENABLED', 'true').lower() == 'true',
        encryption_enabled=os.getenv('ENCRYPTION_ENABLED', 'true').lower() == 'true'
    )

    network_config = NetworkConfig(
        bind_address=os.getenv('BIND_ADDRESS', '0.0.0.0'),
        port=int(os.getenv('PORT', '8080')),
        max_connections=int(os.getenv('MAX_CONNECTIONS', '1000')),
        timeout=int(os.getenv('TIMEOUT', '30'))
    )

    cache_config = CacheConfig(
        enabled=os.getenv('CACHE_ENABLED', 'true').lower() == 'true',
        max_size_mb=int(os.getenv('CACHE_MAX_SIZE_MB', '1024')),
        ttl_seconds=int(os.getenv('CACHE_TTL_SECONDS', '3600')),
        eviction_policy=os.getenv('CACHE_EVICTION_POLICY', 'lru')
    )

    # Cloud provider configurations
    cloud_providers = {
        'aws': {
            'enabled': os.getenv('AWS_ENABLED', 'false').lower() == 'true',
            'access_key': os.getenv('AWS_ACCESS_KEY'),
            'secret_key': os.getenv('AWS_SECRET_KEY'),
            'region': os.getenv('AWS_REGION', 'us-east-2'),
            'bucket': os.getenv('AWS_BUCKET')
        },
        'gcp': {
            'enabled': os.getenv('GCP_ENABLED', 'false').lower() == 'true',
            'project_id': os.getenv('GCP_PROJECT_ID'),
            'credentials_file': os.getenv('GCP_CREDENTIALS_FILE'),
            'bucket': os.getenv('GCP_BUCKET')
        },
        'azure': {
            'enabled': os.getenv('AZURE_ENABLED', 'false').lower() == 'true',
            'connection_string': os.getenv('AZURE_CONNECTION_STRING'),
            'container': os.getenv('AZURE_CONTAINER')
        }
    }

    return InfrastructureConfig(
        storage=storage_config,
        network=network_config,
        cache=cache_config,
        cloud_providers=cloud_providers,
        metrics_enabled=os.getenv('METRICS_ENABLED', 'true').lower() == 'true',
        debug_mode=os.getenv('DEBUG', 'false').lower() == 'true'
    )

# Global configuration instance
infrastructure_config = load_infrastructure_config()
