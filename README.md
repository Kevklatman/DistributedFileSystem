# Distributed File System

A scalable and resilient distributed file system implementation in Python, featuring advanced storage management, data replication, and consistency control.

## Features

- **Distributed Storage**: Scalable file storage across multiple nodes
- **Data Consistency**: Configurable consistency levels (Strong, Eventual, Quorum)
- **Replication**: Automatic data replication and synchronization
- **Load Balancing**: Dynamic load distribution across nodes
- **Health Monitoring**: Continuous node health and performance tracking
- **Storage Efficiency**: Support for deduplication, compression, and thin provisioning
- **Cloud Integration**: Cloud tiering policies for hybrid storage solutions
- **Data Protection**: Snapshot management and retention policies

## Architecture

### Core Components

- **Active Node**: Central component managing node operations and coordination
- **Load Manager**: Monitors and balances system load across nodes
- **Consistency Manager**: Ensures data consistency across replicas
- **Replication Manager**: Handles data replication and synchronization
- **Storage Infrastructure**: Manages physical storage and data placement

### Models

- `NodeState`: Represents node status and health metrics
- `Volume`: Defines storage volume properties and configuration
- `CloudTieringPolicy`: Controls data movement between local and cloud storage
- `DataProtection`: Manages backup and recovery policies
- `DeduplicationState`: Controls data deduplication settings
- `CompressionState`: Manages data compression
- `ThinProvisioningState`: Controls storage allocation
- `SnapshotState`: Manages point-in-time snapshots
- `RetentionPolicy`: Defines data retention rules

## Project Structure

```
src/
├── api/
│   └── services/          # S3-compatible storage interfaces
├── k8s/                   # Kubernetes configurations
│   ├── base/             # Base configurations
│   └── overlays/         # Environment-specific configs
├── models/
│   └── models.py         # Data models and types
├── storage/
│   └── infrastructure/
│       ├── active_node.py # Node management
│       ├── load_manager.py # Load balancing
│       └── data/
│           ├── cache_store.py
│           ├── consistency_manager.py
│           ├── data_protection.py
│           ├── replication_manager.py
│           └── sync_manager.py
└── tests/
    ├── conftest.py       # Test fixtures and configuration
    └── run_tests.py      # Test runner
```

## Development

### Requirements

- Python 3.8.13 or higher
- aiohttp for async HTTP operations
- pytest and related packages for testing

### Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r test-requirements.txt  # for development
```

### Running Tests

The project uses pytest for testing. Run tests using:

```bash
python src/tests/run_tests.py [options]
```

Available options:
- `--unit`: Run unit tests
- `--integration`: Run integration tests
- `--coverage`: Generate coverage report
- `-v`: Verbose output

### Kubernetes Deployment

For development (Minikube):
```bash
kubectl apply -k k8s/overlays/development
```

For production:
```bash
kubectl apply -k k8s/overlays/production
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with modern Python async/await patterns
- Implements industry-standard consistency models
- Kubernetes-native deployment support
