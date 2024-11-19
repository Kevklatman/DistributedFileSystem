# Distributed File System

An S3-compatible distributed file system with support for edge computing, implemented in Python. Supports local storage, AWS S3, and distributed node backends.

## Features

- S3-compatible API
- Multiple storage backends:
  - Local filesystem
  - AWS S3
  - Distributed node storage
- Edge computing support
- Policy-based data placement
- Versioning support
- Multipart uploads
- Monitoring and metrics
- Container Storage Interface (CSI) driver
- Kubernetes integration

## API Endpoints

### S3-Compatible Operations (Port 8001)

All S3-compatible operations are available at `http://localhost:8001`

#### Bucket Operations
- `GET /buckets` - List all buckets
  * Optional header: `X-Consistency-Level` (values: `eventual` or `strong`, default: `eventual`)
- `PUT /<bucket>` - Create a bucket
- `DELETE /<bucket>` - Delete a bucket
- `GET /<bucket>` - List objects in bucket
- `PUT /<bucket>?versioning` - Configure bucket versioning
- `GET /<bucket>?versioning` - Get bucket versioning status

#### Example Bucket Listing
```bash
# List buckets with eventual consistency (default)
curl -H "Accept: application/json" http://localhost:8001/buckets

# List buckets with strong consistency
curl -H "Accept: application/json" \
     -H "X-Consistency-Level: strong" \
     http://localhost:8001/buckets
```

#### Object Operations
- `PUT /<bucket>/<key>` - Upload an object
- `GET /<bucket>/<key>` - Download an object
- `DELETE /<bucket>/<key>` - Delete an object
- `HEAD /<bucket>/<key>` - Get object metadata

#### Multipart Upload Operations
- `POST /<bucket>/<key>?uploads` - Initiate multipart upload
- `PUT /<bucket>/<key>?partNumber=<number>&uploadId=<id>` - Upload part
- `POST /<bucket>/<key>?uploadId=<id>` - Complete multipart upload
- `DELETE /<bucket>/<key>?uploadId=<id>` - Abort multipart upload
- `GET /<bucket>?uploads` - List multipart uploads

#### Versioning Operations
- `GET /<bucket>/<key>?versionId=<id>` - Get specific object version
- `DELETE /<bucket>/<key>?versionId=<id>` - Delete specific version
- `GET /<bucket>?versions` - List all object versions

### Management API

#### System Operations
- `GET /health` - Health check endpoint
  - Returns system health status and component availability
  - Includes storage backend connectivity
  - Reports API service status
  - Provides edge node health information

- `GET /api/v1/docs` - Interactive API documentation (Swagger UI)
  - Complete OpenAPI/Swagger specification
  - Interactive endpoint testing
  - Request/response schemas and examples

#### Metrics and Monitoring
- `GET /metrics` - Prometheus metrics endpoint
  - Raw metrics in Prometheus format
  - System performance metrics
  - Request throughput and latency
  - Error rates and types
  - Storage utilization metrics
  - Node health status

- `GET /api/dashboard/metrics` - Dashboard metrics
  - Formatted JSON metrics for dashboard UI
  - System performance metrics
  - Storage utilization
  - Request throughput and latency
  - Node health status
  - Edge node performance metrics

### Response Formats

#### S3-Compatible Endpoints
- XML format responses (S3-compatible)
- Standard S3 response headers
- Versioning metadata support
- Error response format matches S3 spec

Example bucket listing:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<ListAllMyBucketsResult>
    <Buckets>
        <Bucket>
            <Name>my-bucket</Name>
            <CreationDate>2023-01-01T00:00:00.000Z</CreationDate>
        </Bucket>
    </Buckets>
    <Owner>
        <ID>DFSOwner</ID>
        <DisplayName>DFS System</DisplayName>
    </Owner>
</ListAllMyBucketsResult>
```

#### Management API Endpoints
- JSON format responses
- Request correlation IDs
- Detailed error information
- Pagination support for list operations

Example health check response:
```json
{
    "status": "healthy",
    "components": {
        "storage": "operational",
        "api": "operational",
        "policy_engine": "operational",
        "edge_nodes": {
            "edge1": "operational",
            "edge2": "operational"
        }
    },
    "metrics": {
        "uptime": "10d 4h 30m",
        "requests_per_second": 150.5,
        "error_rate_percent": 0.01,
        "edge_node_count": 2,
        "storage_nodes": 3
    }
}
```

#### Error Responses
All error responses include:
- Error Code: Unique error identifier
- Message: Human-readable description
- RequestId: Request correlation ID
- Resource: Affected resource identifier
- TimeStamp: Error occurrence time (ISO 8601)

Example error response:
```json
{
    "error": {
        "code": "NoSuchBucket",
        "message": "The specified bucket does not exist",
        "requestId": "5FF5C0C1-5484-4D41-9C08-C47F3CE1175E",
        "resource": "/my-bucket",
        "timestamp": "2023-12-25T12:00:00Z"
    }
}
```

### Service Ports

The system runs several services on different ports:

- `8001`: S3-compatible API (bucket and object operations)
- `5001`: Monitoring and metrics API
- `8089`: Locust load testing UI
- `9090`: Prometheus metrics visualization
- `3000`: Grafana dashboards

### Authentication

#### API Key Authentication
- Required for all non-public endpoints
- Passed via `X-Api-Key` header
- Configurable via environment variables
- Role-based access control
- Support for multiple API keys with different permissions

Example:
```bash
curl -H "X-Api-Key: your-api-key" http://localhost:5001/health
```

#### CORS Support
- Web interface compatibility
- Configurable allowed origins
- Preflight request handling
- Secure credential handling

Supported configurations:
- Origins: Configurable via CORS_ORIGINS env var
- Methods: GET, POST, PUT, DELETE, HEAD, OPTIONS
- Headers: Content-Type, Accept, Authorization, X-Api-Key
- Exposed Headers: ETag, X-Request-Id
- Credentials: Supported with secure handling
- Max Age: 3600 seconds

## Setup

### Prerequisites

1. System Requirements:
   - 4GB RAM minimum (8GB recommended)
   - 20GB free disk space
   - x86_64 or ARM64 architecture
   - Network bandwidth: 100Mbps minimum

2. Software Requirements:
   - Python 3.8+
   - Docker 20.10+ and Docker Compose v2.0+
   - Git
   - Kubernetes 1.20+ (for distributed deployment)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/DistributedFileSystem.git
cd DistributedFileSystem
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Quick Start

To start the entire development environment with one command:
```bash
./scripts/start_dev.sh
```

This script will:
1. Check if Docker is running
2. Create necessary data directories
3. Start all core and edge nodes
4. Start monitoring services (Prometheus, Grafana)
5. Start load testing UI
6. Display access URLs for all services

To open all web interfaces in your default browser:
```bash
./scripts/open_uis.sh
```

### Available Web Interfaces

#### Core API Nodes
- Node 1: http://localhost:8001
- Node 2: http://localhost:8002
- Node 3: http://localhost:8003

#### Edge Computing Nodes
- Edge 1: http://localhost:8011
- Edge 2: http://localhost:8012

#### Monitoring & Testing
- Grafana Dashboard: http://localhost:3001 (default login: admin/admin)
- Prometheus Metrics: http://localhost:9090
- Load Testing UI: http://localhost:8089

### Management Commands

Stop all services:
```bash
docker-compose down
```

View logs:
```bash
docker-compose logs -f          # All services
docker-compose logs -f node1    # Specific service
```

### Deployment Options

#### Single Node Deployment

1. Local Development:
```bash
# Start the API server
flask run --host=0.0.0.0 --port=5555 --debug

# Access the API at http://localhost:5555
# Access Swagger UI at http://localhost:5555/api/v1/docs
```

2. Production Deployment:
```bash
# Start with Gunicorn
gunicorn --bind 0.0.0.0:5555 \
    --workers 4 \
    --threads 2 \
    --worker-class gthread \
    --log-level info \
    'src.api.app:create_app()'
```

#### Distributed Deployment

1. Using Docker Compose:
```bash
# Start the entire distributed system
docker-compose up -d

# Start specific components
docker-compose up -d node1 node2 node3  # Core nodes
docker-compose up -d edge1 edge2        # Edge nodes
docker-compose up -d monitoring         # Monitoring stack
```

2. Kubernetes Deployment:
```bash
# Apply base configuration
kubectl apply -f k8s/base/

# Apply environment-specific overlay
kubectl apply -k k8s/overlays/dev/  # or prod, staging
```

3. Accessing Components:
- Core Nodes:
  - Node 1: http://localhost:8001
  - Node 2: http://localhost:8002
  - Node 3: http://localhost:8003
- Edge Nodes:
  - Edge 1: http://localhost:8011
  - Edge 2: http://localhost:8012
- Monitoring:
  - Prometheus: http://localhost:9090
  - Grafana: http://localhost:3001 (default: admin/admin)
  - Load Testing UI: http://localhost:8089

### Configuration

#### Environment Variables

1. Basic Configuration:
```bash
# API Settings
API_HOST=0.0.0.0
API_PORT=5555
DEBUG=True

# Storage Backend
STORAGE_ENV=local  # Options: local, aws, distributed
STORAGE_PATH=/path/to/storage

# Authentication
API_KEY=your-api-key
CORS_ORIGINS=http://localhost:3000,http://localhost:5000
```

2. Distributed Settings:
```bash
# Node Configuration
NODE_ID=node1
NODE_TYPE=core  # Options: core, edge
QUORUM_SIZE=2

# Edge Node Settings
DEVICE_TYPE=mobile  # Options: mobile, iot
PROCESSING_POWER=0.7  # Range: 0.0-1.0
BATTERY_LEVEL=80     # Range: 0-100
BANDWIDTH_LIMIT=1000  # KB/s
```

3. Cloud Provider Settings:
```bash
# AWS Configuration
AWS_ACCESS_KEY=your-access-key
AWS_SECRET_KEY=your-secret-key
AWS_REGION=us-west-2

# Optional: GCP Configuration
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Optional: Azure Configuration
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
```

## Testing

### Unit Tests

1. Run all tests:
```bash
pytest
```

2. Run specific test categories:
```bash
pytest tests/unit                # Unit tests
pytest tests/integration        # Integration tests
pytest tests/api               # API tests
pytest tests/edge             # Edge node tests
```

3. Test options:
```bash
pytest -v                      # Verbose output
pytest -k "test_pattern"      # Run tests matching pattern
pytest --cov=src              # Run with coverage
pytest --cov-report=html      # Generate coverage report
```

### Load Testing

1. Start the Locust load testing UI:
```bash
docker-compose up -d locust
```

2. Access the Locust UI at http://localhost:8089:
   - Set number of users
   - Set spawn rate
   - Choose test scenario
   - Monitor real-time metrics

3. Available test scenarios:
   - Basic operations (upload/download)
   - Mixed workload
   - Edge node stress test
   - Consistency test
   - Network partition simulation
   - Recovery testing

4. Custom test scenarios:
```bash
# Run custom test script
locust -f tests/load/custom_scenario.py

# Headless mode
locust -f tests/load/custom_scenario.py --headless -u 100 -r 10
```

### Monitoring

1. Start monitoring stack:
```bash
docker-compose up -d prometheus grafana
```

2. Access monitoring:
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3001 (default: admin/admin)

3. Available dashboards:
   - System Overview
     - Request rates and latencies
     - Error rates and types
     - Storage utilization
   - Node Performance
     - CPU and memory usage
     - Network I/O
     - Disk operations
   - Edge Computing
     - Edge node status
     - Processing metrics
     - Battery levels
     - Network conditions
   - Storage Metrics
     - Object counts
     - Bucket sizes
     - Backend performance
   - API Metrics
     - Endpoint usage
     - Response times
     - Error distribution
   - Policy Engine
     - Policy evaluations
     - Cache performance
     - Override statistics

## Project Structure

```
.
├── API/                 # S3-compatible API service
├── buckets/            # Local bucket storage directory
├── config/             # System configuration files
├── csi-driver/         # Container Storage Interface driver
│   ├── cmd/           # CSI driver commands
│   └── pkg/           # Driver implementation
├── data/              # Persistent data storage
├── docs/              # Documentation
│   └── diagrams/     # Architecture diagrams
├── examples/          # Usage examples
├── frontend/          # Web interface
│   ├── public/       # Static assets
│   └── src/          # Frontend source
├── k8s/               # Kubernetes configs
│   ├── base/         # Base manifests
│   └── overlays/     # Environment overlays
├── src/               # Core source code
│   ├── api/          # API implementation
│   ├── edge/         # Edge computing
│   ├── monitoring/   # Metrics collection
│   ├── policy/       # Policy engine
│   └── storage/      # Storage backends
├── tests/             # Test suites
│   ├── unit/         # Unit tests
│   ├── integration/  # Integration tests
│   ├── edge/         # Edge tests
│   └── load/         # Load tests
├── docker-compose.yml # Docker composition
├── Dockerfile        # Main Dockerfile
└── requirements.txt  # Dependencies
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
