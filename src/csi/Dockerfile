FROM python:3.8-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install gRPC and protobuf tools
RUN pip install --no-cache-dir \
    "protobuf>=4.21.6,<5.0" \
    grpcio==1.59.3 \
    grpcio-tools==1.59.3

# Copy source code
COPY src/csi /app/csi
COPY src/api /app/api
COPY src/models /app/models
COPY src/storage /app/storage

# Generate gRPC code from proto files
RUN python -m grpc_tools.protoc \
    --proto_path=/app/csi/proto \
    --python_out=/app/csi \
    --grpc_python_out=/app/csi \
    /app/csi/proto/csi.proto

# Create necessary directories
RUN mkdir -p /csi /data/dfs

WORKDIR /app

ENV PYTHONPATH=/app

# Add entrypoint script
COPY src/csi/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
