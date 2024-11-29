# Distributed File System

A scalable and resilient distributed file system implementation in Python, featuring advanced storage management, data replication, and consistency control. Built with modern async/await patterns and Kubernetes-native deployment support.

## Features

### Core Functionality
- **Distributed Storage**
  - Scalable file storage across multiple nodes
  - Dynamic node discovery and registration
  - Automatic storage pool management
  - Support for multiple storage backends

- **Data Consistency**
  - Configurable consistency levels:
    - Strong consistency for critical data
    - Eventual consistency for better performance
    - Quorum-based consistency for balanced approach
  - Transaction logging and rollback support
  - Conflict resolution mechanisms

- **Replication & Synchronization**
  - Automatic data replication across nodes
  - Configurable replication factors
  - Intelligent replica placement
  - Background synchronization
  - Delta-based updates

- **Load Balancing**
  - Dynamic load distribution
  - Resource usage monitoring
  - Automatic node scaling
  - Traffic shaping
  - Hot-spot detection and mitigation

### Advanced Features

- **Health Monitoring**
  - Real-time node health tracking
  - Performance metrics collection
  - Automated failure detection
  - Self-healing capabilities
  - Detailed system analytics

- **Storage Efficiency**
  - Inline deduplication
  - Compression (configurable algorithms)
  - Thin provisioning
  - Space reclamation
  - Garbage collection

- **Cloud Integration**
  - Multi-cloud support (Azure, GCP)
  - Intelligent tiering policies
  - Hybrid storage optimization
  - Cloud-native scalability
  - Cross-cloud replication

- **Data Protection**
  - Point-in-time snapshots
  - Configurable retention policies
  - Incremental backups
  - Quick recovery options
  - Data encryption at rest and in transit

## Recent Updates

### S3-Compatible API Improvements
- Enhanced async operation handling in S3 routes
- Improved error handling and response formatting
- Added proper event loop management
- Implemented S3-compatible response headers
- Added support for basic S3 operations (PUT, GET, DELETE)

### System Infrastructure
- Improved cluster manager initialization
- Enhanced async/sync compatibility across components
- Added development mode support
- Implemented proper leader election in non-Kubernetes environments
- Added robust error handling and logging

### Development Tools
- Added `start_dfs.sh` script for easy system startup
  - Manages both Flask app and Kubernetes cluster
  - Handles environment variables
  - Provides proper cleanup on exit
  - Includes color-coded status messages
  - Automatic dependency checking

### Environment Configuration
- Standardized environment variables:
  - `STORAGE_ROOT`: Data storage location
  - `NODE_ID`: Node identification
  - `CLOUD_PROVIDER_TYPE`: Cloud provider selection
  - `FLASK_APP`: Flask application path
  - `FLASK_ENV`: Flask environment setting

### Testing and Debugging
- Enhanced test script compatibility
- Added comprehensive error logging
- Improved async operation testing
- Added S3 operation test cases

## System Architecture and Data Flow

### Overview
The distributed file system implements a layered architecture with clear separation of concerns:

```
Client Request → API Layer → Service Layer → Storage Backend → Infrastructure
```

### Component Layers

1. **API Layer**:
   - Entry point through Flask app (`app.py`)
   - Three API interfaces:
     - S3-compatible API (`/s3`)
     - AWS S3-compatible API (`/aws-s3`)
     - Advanced storage API (`/storage`)

2. **Service Layer**:
   - `FileSystemManager`: Coordinates storage operations
   - `SystemService`: Handles system-level operations
   - `AdvancedStorageService`: Manages advanced storage features

3. **Storage Backend**:
   - Abstract `StorageBackend` base class
   - Implementations:
     - `LocalStorageBackend`: Local file system storage
     - `AWSStorageBackend`: AWS S3 storage
   - Factory pattern for backend selection

4. **Infrastructure Layer**:
   ```
   ActiveNode → LoadManager → StorageNode
       ↓            ↓            ↓
   Consistency   Replication   Cache
   Manager      Manager       Store
   ```

### Data Flow and Operations

1. **Data Consistency**:
   - Three consistency levels:
     - Strong: All nodes must be in sync
     - Quorum: Majority of nodes must agree
     - Eventual: Updates propagate over time
   - Version tracking for conflict resolution

2. **Caching System**:
   ```
   Edge Cache → Node Cache → Storage Cache
   ```
   - Cache coherency maintained by ConsistencyManager
   - TTL-based invalidation

3. **Load Management**:
   - Metrics tracked:
     - CPU usage
     - Memory usage
     - Disk I/O
     - Network I/O
     - Request rate
   - Dynamic load balancing
   - Resource optimization

4. **Replication Flow**:
   ```
   Write Request → Primary Node → Replication Manager → Secondary Nodes (async) → Consistency Check
   ```

### Monitoring & Error Handling
- Prometheus metrics collection
- Health checks and performance monitoring
- Cascading error propagation
- Automatic retry mechanisms
- Fallback strategies
- Comprehensive error logging

## API Endpoints

### S3-Compatible API (`/s3`)

#### Bucket Operations
```
GET    /s3/                     # List all buckets
PUT    /s3/{bucket}            # Create bucket
DELETE /s3/{bucket}            # Delete bucket
GET    /s3/{bucket}            # List bucket contents
```

#### Object Operations
```
PUT    /s3/{bucket}/{key}      # Upload object
GET    /s3/{bucket}/{key}      # Download object
DELETE /s3/{bucket}/{key}      # Delete object
HEAD   /s3/{bucket}/{key}      # Get object metadata
```

#### Advanced Operations
```
POST   /s3/{bucket}/{key}?uploads            # Initiate multipart upload
PUT    /s3/{bucket}/{key}?partNumber={num}   # Upload part
POST   /s3/{bucket}/{key}?complete           # Complete multipart upload
```

### AWS S3-Compatible API (`/aws-s3`)

#### Standard Operations
```
GET    /aws-s3/                          # List all buckets
PUT    /aws-s3/{bucket}                 # Create bucket
DELETE /aws-s3/{bucket}                 # Delete bucket
GET    /aws-s3/{bucket}                 # List bucket contents
PUT    /aws-s3/{bucket}/{key}           # Upload object
GET    /aws-s3/{bucket}/{key}           # Download object
DELETE /aws-s3/{bucket}/{key}           # Delete object
HEAD   /aws-s3/{bucket}/{key}           # Get object metadata
```

### Advanced Storage API (`/storage`)

#### Volume Management
```
GET    /storage/volumes                  # List volumes
POST   /storage/volumes                  # Create volume
DELETE /storage/volumes/{id}             # Delete volume
GET    /storage/volumes/{id}             # Get volume info
PUT    /storage/volumes/{id}             # Update volume
```

#### Node Management
```
GET    /storage/nodes                    # List nodes
POST   /storage/nodes                    # Register node
DELETE /storage/nodes/{id}               # Remove node
GET    /storage/nodes/{id}               # Get node info
PUT    /storage/nodes/{id}               # Update node
```

#### System Operations
```
GET    /storage/health                   # System health check
GET    /storage/metrics                  # System metrics
POST   /storage/snapshot                 # Create system snapshot
GET    /storage/config                   # Get system configuration
PUT    /storage/config                   # Update system configuration
```

All endpoints support proper error handling and return appropriate HTTP status codes. Authentication is required for all operations.

## Deployment Guide

### Pre-deployment Checklist

1. AWS Credentials
   - [ ] Generate new AWS credentials
   - [ ] Update `.env` file with new credentials
   - [ ] Verify AWS region is correct (currently us-east-2)

2. Environment Configuration
   - [ ] Verify STORAGE_ENV setting (aws/local)
   - [ ] Check STORAGE_ROOT path exists
   - [ ] Confirm STORAGE_TYPE is set correctly (hybrid)

3. Kubernetes Requirements
   - [ ] Kubernetes cluster is running
   - [ ] kubectl configured with correct context
   - [ ] Prometheus operator installed (for metrics)
   - [ ] Storage class available for PVCs

4. Resource Requirements
   - [ ] Minimum 3 nodes available for storage StatefulSet
   - [ ] Each node has at least:
     - 2Gi memory
     - 1 CPU core
     - 10Gi storage

### Deployment Steps

1. Configure AWS Credentials:
   ```bash
   export AWS_ACCESS_KEY=<your_access_key>
   export AWS_SECRET_KEY=<your_secret_key>
   ```

2. Run the deployment script:
   ```bash
   ./deploy.sh
   ```

3. Verify deployment:
   ```bash
   # Check pods
   kubectl -n distributed-fs get pods

   # Check services
   kubectl -n distributed-fs get services

   # Check metrics
   curl http://<EXTERNAL_IP>:9091/metrics
   ```

### Monitoring

- Service endpoints:
  - Main API: http://<EXTERNAL_IP>:8000
  - Metrics: http://<EXTERNAL_IP>:9091/metrics
  - HAProxy Stats: http://<EXTERNAL_IP>:8404

- Prometheus metrics:
  - Request queue length
  - Node status
  - Storage utilization
  - Operation latencies

### Troubleshooting

1. Pod not starting:
   - Check pod logs: `kubectl -n distributed-fs logs <pod-name>`
   - Verify resource limits
   - Check PVC status

2. Service unavailable:
   - Verify LoadBalancer service status
   - Check HAProxy configuration
   - Ensure firewall rules allow traffic

3. Metrics not showing:
   - Verify ServiceMonitor configuration
   - Check Prometheus operator status
   - Confirm metrics port (9091) is accessible

## Architecture

### Core Components

#### Active Node
- Central coordination component
- Manages node lifecycle
- Handles service discovery
- Coordinates distributed operations
- Maintains system metadata

#### Load Manager
- Real-time load monitoring
- Resource allocation
- Performance optimization
- Scaling decisions
- Traffic routing

#### Consistency Manager
- Transaction coordination
- Conflict detection and resolution
- Version control
- Lock management
- Consistency level enforcement

#### Replication Manager
- Replica placement strategy
- Synchronization scheduling
- Failure recovery
- Data migration
- Consistency verification

#### Storage Infrastructure
- Physical storage management
- I/O optimization
- Storage pool management
- Volume management
- Storage driver integration

### Models

```python
# Core Models
NodeState:
  - status: str
  - health_metrics: Dict[str, float]
  - resources: ResourceMetrics
  - last_heartbeat: datetime

Volume:
  - id: str
  - size: int
  - replicas: int
  - consistency_level: ConsistencyLevel
  - storage_class: str
  - metadata: Dict[str, Any]

# Policy Models
CloudTieringPolicy:
  - hot_tier_threshold: float
  - cold_tier_threshold: float
  - migration_schedule: CronExpression
  - providers: List[CloudProvider]

DataProtection:
  - backup_schedule: CronExpression
  - retention_period: timedelta
  - encryption_config: EncryptionConfig
  - snapshot_config: SnapshotConfig

# Storage Efficiency Models
DeduplicationState:
  - enabled: bool
  - chunk_size: int
  - hash_algorithm: str
  - inline: bool

CompressionState:
  - enabled: bool
  - algorithm: str
  - min_size: int
  - exclude_types: List[str]

ThinProvisioningState:
  - enabled: bool
  - overcommit_ratio: float
  - warning_threshold: float
```

## Project Structure

```
src/
├── api/                  # API Layer
│   ├── handlers/        # Request handlers
│   │   ├── volume.py
│   │   ├── node.py
│   │   └── metrics.py
│   └── services/        # S3-compatible interfaces
│       ├── s3.py
│       └── rest.py
├── k8s/                 # Kubernetes Configurations
│   ├── base/           # Base configurations
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   └── overlays/       # Environment-specific configs
│       ├── development/
│       └── production/
├── models/             # Data Models
│   ├── models.py      # Core data models
│   ├── policies.py    # Policy definitions
│   └── metrics.py     # Metrics models
├── scripts/           # Management Scripts
│   ├── node_management.py  # Node operations
│   ├── cloud_provider_tests.py  # Cloud testing
│   ├── dfs-env.sh    # Environment management
│   ├── setup-credentials.py  # Credential setup
│   └── cluster_config.yaml  # Cluster config
├── storage/          # Storage Layer
│   ├── cloud/       # Cloud providers
│   │   ├── azure.py
│   │   └── gcp.py
│   └── infrastructure/
│       ├── active_node.py
│       ├── load_manager.py
│       └── data/
│           ├── cache_store.py
│           ├── consistency_manager.py
│           ├── data_protection.py
│           ├── replication_manager.py
│           └── sync_manager.py
└── tests/           # Test Suite
    ├── unit/       # Unit tests
    ├── integration/  # Integration tests
    ├── conftest.py  # Test fixtures
    └── run_tests.py  # Test runner
```

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/DistributedFileSystem.git
cd DistributedFileSystem
```

2. Set up the environment:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Start the system:
```bash
./src/scripts/start_dfs.sh
```

The system will:
- Start Minikube if not running
- Apply Kubernetes configurations
- Start the Flask application
- Set up necessary environment variables

Access the services:
- Flask API: http://localhost:8001
- Kubernetes dashboard: Use `minikube dashboard`

## Development Setup

### Prerequisites
- Python 3.8.13 or higher
- Minikube
- kubectl
- Virtual environment

### Environment Variables
```bash
export STORAGE_ROOT="/path/to/data/dfs"
export NODE_ID="test-node-1"
export CLOUD_PROVIDER_TYPE="aws"
export FLASK_APP="src/api/app.py"
export FLASK_ENV="development"
```

### Running Tests
```bash
pytest tests/
```

## Contributing

Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
