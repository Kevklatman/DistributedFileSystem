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
    grpcio \
    grpcio-tools \
    protobuf

# Copy source code
COPY src/csi /app/csi
COPY src/api /app/api

# Generate gRPC code from proto files
RUN python -m grpc_tools.protoc \
    --proto_path=/app/csi/proto \
    --python_out=/app/csi \
    --grpc_python_out=/app/csi \
    /app/csi/proto/csi.proto

WORKDIR /app/csi

# Create socket directory
RUN mkdir -p /csi

# Set environment variables
ENV PYTHONPATH=/app
ENV CSI_ENDPOINT=unix:///csi/csi.sock

# Run the CSI driver
CMD ["python", "driver.py"]
