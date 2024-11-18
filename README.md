# Distributed File System

An S3-compatible distributed file system implemented in Python. Supports both local storage and AWS S3 backends.

## Features

- S3-compatible API
- Multiple storage backends (Local and AWS S3)
- Easy switching between backends via environment variables
- Docker support

## API Endpoints

### S3-Compatible Operations

#### Bucket Operations
- `GET /` - List all buckets
- `PUT /<bucket>` - Create a bucket
- `DELETE /<bucket>` - Delete a bucket
- `GET /<bucket>` - List objects in bucket
- `PUT /<bucket>?versioning` - Configure bucket versioning
- `GET /<bucket>?versioning` - Get bucket versioning status

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
- `GET /api/v1/health` - Health check endpoint
- `GET /api/v1/docs` - API documentation (Swagger UI)

#### Metrics and Monitoring
- `GET /api/v1/metrics/policy` - Get policy engine metrics
- `GET /api/v1/metrics/dashboard` - Get system dashboard metrics

### Response Formats
- Success responses are returned in XML format for S3-compatible endpoints
- Management API endpoints return JSON responses
- Error responses include:
  - Error Code
  - Error Message
  - Request ID

### Authentication
- API Key authentication via `X-Api-Key` header
- CORS enabled for web interface

## Setup

1. Clone the repository:
```bash
git clone https://github.com/Kevklatman/DistributedFileSystem.git
cd DistributedFileSystem
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Running

### Local Development
```bash
python -m flask run --host=0.0.0.0 --port=5555
```

### Docker
```bash
docker build -t dfs .
docker run -p 5555:5555 dfs
```

## Configuration

Set the following environment variables in `.env`:

```bash
# Storage backend ('local' or 'aws')
STORAGE_ENV=local

# AWS credentials (if using aws backend)
AWS_ACCESS_KEY=your-key
AWS_SECRET_KEY=your-secret
AWS_REGION=us-east-1

# API settings
API_HOST=0.0.0.0
API_PORT=5555
```

## Testing

```bash
# Create a bucket
curl -X PUT http://localhost:5555/my-bucket

# Upload a file
curl -X PUT -d "Hello World" http://localhost:5555/my-bucket/hello.txt

# Download a file
curl http://localhost:5555/my-bucket/hello.txt

# List buckets
curl http://localhost:5555/
```

## Project Structure

```
.
├── API/                    # S3-compatible API service
├── buckets/               # Local bucket storage directory
├── config/                # System configuration files
├── csi-driver/            # Container Storage Interface driver (Go)
│   ├── cmd/              # CSI driver commands
│   └── pkg/              # Driver implementation packages
├── data/                  # Persistent data storage
├── docs/                  # Architecture and design documentation
│   └── *.mermaid         # System architecture diagrams
├── examples/              # Usage examples and demos
│   ├── custom_policy_example.py
│   ├── dashboard_example.py
│   └── policy_scenarios.py
├── frontend/             # React-based web interface
│   ├── public/          # Static assets
│   └── src/             # Frontend source code
├── k8s/                  # Kubernetes configurations
│   ├── base/            # Base Kubernetes manifests
│   └── overlays/        # Environment-specific overlays
├── src/                  # Core Python source code
│   ├── api/             # API implementation and routes
│   ├── csi/             # CSI driver integration
│   ├── monitoring/      # Prometheus/Grafana integration
│   ├── storage/         # Storage backend implementations
│   └── web/             # Web service implementations
├── storage-node/        # Storage node service (Go)
│   ├── cmd/            # Storage node commands
│   └── pkg/            # Storage implementation
├── tests/               # Test suites and fixtures
├── docker-compose.yml   # Multi-service Docker composition
├── Dockerfile           # API service Dockerfile
├── Dockerfile.storage-node # Storage node Dockerfile
├── requirements.txt     # Production Python dependencies
└── requirements-test.txt # Testing dependencies
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
