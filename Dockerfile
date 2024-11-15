# Use slim version of Ubuntu for smaller base image
FROM ubuntu:22.04

# Combine RUN commands and clean up in the same layer to reduce image size
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libssl-dev \
    python3 \
    python3-pip \
    libgrpc++-dev \
    libgrpc-dev \
    protobuf-compiler \
    protobuf-compiler-grpc \
    libprotobuf-dev \
    pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Flask for the Python API component
RUN pip3 install Flask

# Set working directory
WORKDIR /app

# Copy only necessary files first
COPY CMakeLists.txt ./
COPY proto/ ./proto/
COPY include/ ./include/
COPY src/ ./src/
COPY tests/ ./tests/

# Locate gRPC installation
RUN echo "set(gRPC_DIR /usr/lib/x86_64-linux-gnu/cmake/grpc)" >> CMakeLists.txt

# Build the application
RUN mkdir build && \
    cd build && \
    cmake .. && \
    make -j$(nproc)

# Expose gRPC and Flask ports
EXPOSE 50051 5000

# Run the main DFS executable
CMD ["./build/dfs_main"]
