# Storage Infrastructure

This directory contains the fundamental storage infrastructure components of the distributed file system.

## Components

- `interfaces.py`: Core storage interfaces for cloud providers, storage operations, caching, and CSI
- `active_node.py`: Active node management and health monitoring
- `cluster_manager.py`: Cluster management and coordination
- `hybrid_storage.py`: Hybrid storage implementation for local and cloud storage
- `providers.py`: Cloud provider implementations
- `node.py`: Node-level storage operations
- `storage_efficiency.py`: Storage optimization features
- `load_manager.py`: Load balancing and distribution
- `models.py`: Storage-related data models

## Architecture

This layer provides the low-level storage infrastructure that powers the distributed file system:

1. **Storage Operations**: Basic read/write operations, data management
2. **Cluster Management**: Node coordination, health monitoring
3. **Cloud Integration**: Provider interfaces, hybrid storage capabilities
4. **Performance**: Load balancing, storage efficiency

## Integration

The storage infrastructure layer is used by the API services layer (`/src/api/services/`) to implement 
high-level APIs like S3-compatible storage. This separation allows for:

- Clear separation of concerns
- Independent testing and development
- Flexibility in implementing different APIs
- Better maintainability
