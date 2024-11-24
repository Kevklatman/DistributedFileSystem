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

## Development

### Requirements

#### System Requirements
- Python 3.8.13 or higher
- Docker 20.10.0 or higher
- Kubernetes 1.20.0 or higher
- 8GB RAM minimum (16GB recommended)
- 4 CPU cores minimum

#### Software Dependencies
- kubectl CLI tool
- aiohttp for async operations
- pytest and pytest-asyncio for testing
- kubernetes-client for K8s operations
- Cloud provider SDKs:
  - azure-storage-blob
  - google-cloud-storage

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/distributed-file-system.git
cd distributed-file-system
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r test-requirements.txt  # for development
```

4. Configure environment:
```bash
source ./src/scripts/dfs-env.sh
dfs-setup-env
```

### Management Scripts

#### Node Management
```bash
# Create new storage node
./src/scripts/node_management.py create --name node1 --size 100GB

# Monitor specific nodes
./src/scripts/node_management.py monitor --nodes node1,node2 --metrics cpu,memory,iops

# Deploy cluster
./src/scripts/node_management.py deploy --config cluster_config.yaml --replicas 3

# Scale cluster
./src/scripts/node_management.py scale --nodes 5 --storage-class ssd
```

#### Environment Management
```bash
# Initialize development environment
source ./src/scripts/dfs-env.sh

# Available commands
dfs-setup-env           # Initialize environment
dfs-deploy-cluster     # Deploy local cluster
dfs-run-tests         # Execute test suite
dfs-cleanup           # Clean environment
dfs-monitor          # Monitor cluster health
dfs-logs            # View system logs
```

#### Cloud Provider Testing
```bash
# Test all providers
./src/scripts/cloud_provider_tests.py --provider all

# Test specific provider
./src/scripts/cloud_provider_tests.py --provider azure --container test-container
./src/scripts/cloud_provider_tests.py --provider gcp --bucket test-bucket

# Run performance tests
./src/scripts/cloud_provider_tests.py --provider all --performance-test
```

### Running Tests

#### Unit Tests
```bash
# Run all unit tests
pytest src/tests/unit

# Run specific test module
pytest src/tests/unit/test_replication.py

# Run with coverage
pytest --cov=src src/tests/unit
```

#### Integration Tests
```bash
# Run all integration tests
pytest src/tests/integration

# Run specific integration test
pytest src/tests/integration/test_cluster_deployment.py

# Run with detailed logging
pytest -v --log-cli-level=INFO src/tests/integration
```

### Kubernetes Deployment

#### Local Development (Minikube)
```bash
# Start local cluster
minikube start --cpus 4 --memory 8192

# Deploy DFS
kubectl apply -k k8s/overlays/development

# Access dashboard
minikube dashboard
```

#### Production Deployment
```bash
# Deploy to production
kubectl apply -k k8s/overlays/production

# Scale deployment
kubectl scale deployment dfs-nodes --replicas=5

# Monitor deployment
kubectl get pods -w
```

### Configuration

#### Cluster Configuration
Edit `src/scripts/cluster_config.yaml`:
```yaml
cluster:
  name: dfs-cluster
  replicas: 3
  storage_class: ssd
  consistency_level: strong

nodes:
  resources:
    cpu: 2
    memory: 4Gi
    storage: 100Gi
  
monitoring:
  enabled: true
  metrics:
    - cpu
    - memory
    - iops
    - latency
```

#### Cloud Provider Configuration
Set up cloud provider credentials:
```bash
# Azure
export AZURE_STORAGE_ACCOUNT="your_account"
export AZURE_STORAGE_KEY="your_key"

# GCP
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
export GOOGLE_CLOUD_PROJECT="your_project"
```

## Contributing

1. Fork the repository
2. Create your feature branch:
```bash
git checkout -b feature/amazing-feature
```

3. Make your changes:
- Follow Python style guide (PEP 8)
- Add unit tests for new features
- Update documentation as needed

4. Commit your changes:
```bash
git commit -m 'Add amazing feature'
```

5. Push to the branch:
```bash
git push origin feature/amazing-feature
```

6. Open a Pull Request

### Development Guidelines
- Write clean, documented code
- Follow async/await patterns
- Include comprehensive tests
- Update README for significant changes
- Add type hints to all functions

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with modern Python async/await patterns
- Implements industry-standard consistency models
- Kubernetes-native deployment support
- Cloud provider integrations
- Community contributions welcome
