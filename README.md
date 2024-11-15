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

### Building from source

1. Clone the repository:
```bash
git clone https://github.com/yourusername/distributed-fs.git
cd distributed-fs
```

2. Create build directory:
```bash
mkdir build && cd build
```

3. Configure with CMake:
```bash
cmake ..
```

4. Build:
```bash
make -j$(nproc)
```

5. Run tests:
```bash
make test
```

## VSCode Configuration

Add the following to your `.vscode/c_cpp_properties.json`:

```json
{
    "configurations": [
        {
            "name": "Linux",
            "includePath": [
                "${workspaceFolder}/**",
                "${workspaceFolder}/include",
                "${workspaceFolder}/build",
                "/usr/local/include",
                "/usr/include/zookeeper"
            ],
            "defines": [],
            "compilerPath": "/usr/bin/g++",
            "cStandard": "c11",
            "cppStandard": "c++17",
            "intelliSenseMode": "gcc-x64",
            "compileCommands": "${workspaceFolder}/build/compile_commands.json"
        }
    ],
    "version": 4
}
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
└── tests/                 # Test files
```

## Usage

1. Start ZooKeeper:
```bash
zkServer.sh start
```

2. Run the filesystem:
```bash
./build/DistributedFileSystem
```

3. Add storage nodes:
```bash
# In separate terminals
./build/DistributedFileSystem --node --host localhost --port 50051
./build/DistributedFileSystem --node --host localhost --port 50052
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