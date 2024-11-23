# API Services

This directory contains the high-level API services that provide S3-compatible storage interfaces.

## Components

- `storage_backend.py`: S3-compatible storage backend implementation
- `fs_manager.py`: File system management and operations
- `config.py`: API configuration management
- `utils/`: API-specific utilities
  - Response formatting
  - XML parsing and generation
  - Error handling
  - Common utilities

## Architecture

This layer builds on top of the storage infrastructure layer (`/src/storage/infrastructure/`) to provide:

1. **S3-Compatible API**: 
   - Basic operations (GET, PUT, DELETE)
   - Bucket management
   - Object versioning
   - Multipart uploads

2. **File System Management**:
   - Directory operations
   - File handling
   - Path management

3. **Configuration**:
   - API settings
   - Storage backend configuration
   - Environment management

4. **Utilities**:
   - Response formatting
   - Error handling
   - XML processing
   - Common helper functions

## Integration

The API services layer uses the storage infrastructure layer to implement high-level storage APIs:

1. **Storage Operations**: Uses storage interfaces for data operations
2. **Cloud Integration**: Leverages cloud provider implementations
3. **Cluster Management**: Utilizes cluster management for distributed operations

This layered architecture provides:
- Clean API implementation
- Consistent interfaces
- Reusable components
- Easy maintenance
