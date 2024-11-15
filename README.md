# Distributed File System

A high-performance distributed file system with enterprise features.

## Prerequisites

### Required packages:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libprotobuf-dev \
    protobuf-compiler \
    libgrpc++-dev \
    protobuf-compiler-grpc \
    libssl-dev \
    zlib1g-dev \
    libzookeeper-mt-dev

# MacOS
brew install \
    cmake \
    protobuf \
    grpc \
    openssl \
    zookeeper
```

## Command Reference

### Building the Project

1. Create and enter build directory:
```bash
mkdir build && cd build
```

2. Configure with CMake:
```bash
cmake ..
```

3. Build all targets:
```bash
# On Linux/Mac with make
make -j$(nproc)
# OR on Mac
make -j$(sysctl -n hw.ncpu)
```

4. Run tests:
```bash
make test
# Or run individual tests:
./build/storage_test
./build/manager_test
```

### Running the System

1. Start the Storage Server:
```bash
# Start a storage node on port 50051
./build/storage_server --host localhost --port 50051

# Start additional nodes on different ports
./build/storage_server --host localhost --port 50052
./build/storage_server --host localhost --port 50053
```

2. Run the Main DFS Service:
```bash
./build/dfs_main
```

3. Use the CLI:
```bash
# General usage
./build/dfs_cli [command] [options]

# Common commands
./build/dfs_cli list                    # List all files
./build/dfs_cli upload <file>           # Upload a file
./build/dfs_cli download <file>         # Download a file
./build/dfs_cli delete <file>           # Delete a file
```

### S3-Compatible API Server

1. Install Python dependencies:
```bash
cd api
pip install -r requirements.txt
```

2. Run the API server:
```bash
python app.py
# Server will start on http://localhost:5000
```

3. Test S3 API endpoints:
```bash
# Create a bucket
curl -X PUT http://localhost:5000/my-bucket

# Upload an object
echo "Hello World" | curl -X PUT -d @- http://localhost:5000/my-bucket/hello.txt

# List buckets
curl http://localhost:5000/

# List objects in bucket
curl http://localhost:5000/my-bucket

# Get object
curl http://localhost:5000/my-bucket/hello.txt
```

### Docker Support

1. Build the Docker image:
```bash
docker build -t distributed-fs .
```

2. Run the container:
```bash
# Run the main service
docker run -p 50051:50051 distributed-fs

# Run a storage node
docker run -p 50052:50051 distributed-fs --node --host 0.0.0.0 --port 50051
```

### Kubernetes Deployment

1. Create namespace and apply base configurations:
```bash
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/aws-ebs-csi-driver.yaml
kubectl apply -f k8s/base/aws-iam-role.yaml
```

2. Deploy the application:
```bash
kubectl apply -f k8s/base/deployment.yaml
```

3. Check deployment status:
```bash
kubectl get pods -n distributed-fs
kubectl logs -f deployment/dfs-main -n distributed-fs
```

### Development Commands

1. Generate Protocol Buffers:
```bash
# Manually generate protobufs (usually handled by CMake)
protoc --grpc_out=generated \
       --cpp_out=generated \
       --proto_path=proto \
       --plugin=protoc-gen-grpc=`which grpc_cpp_plugin` \
       proto/storage.proto
```

2. Format code (if clang-format is installed):
```bash
find . -name '*.cpp' -o -name '*.h' | xargs clang-format -i
```

3. Run with debug logging:
```bash
RUST_LOG=debug ./build/dfs_main
```

## Project Structure

```
.
├── CMakeLists.txt           # Main CMake configuration
├── cmake/                   # CMake modules
├── include/                 # Header files
│   ├── manager/            # FileSystem manager headers
│   └── storage/            # Storage node headers
├── proto/                  # Protocol buffer definitions
├── src/                    # Source files
│   ├── manager/           # FileSystem manager implementation
│   └── storage/           # Storage node implementation
├── tests/                 # Test files
├── api/                   # S3-compatible API
└── k8s/                   # Kubernetes configurations
```

## Configuration

The system can be configured through `config.json` or environment variables:

```json
{
    "cluster": {
        "name": "production-dfs",
        "zookeeper_connection": "localhost:2181",
        "replication_factor": 3
    }
}
```

## Troubleshooting

If you encounter build errors:

1. Ensure all dependencies are installed
2. Check CMake configuration
3. Verify include paths in VSCode settings
4. Run `cmake --build . --verbose` for detailed output

For more detailed information, check the documentation in the `docs/` directory.
