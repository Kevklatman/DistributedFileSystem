# Dockerfile
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libgrpc++-dev \
    protobuf-compiler-grpc \
    libssl-dev \
    git

# Set working directory
WORKDIR /app

# Copy source code
COPY . .

# Build the application
RUN mkdir build && cd build && \
    cmake .. && \
    make

# Expose gRPC port
EXPOSE 50051

# Command to run the server
CMD ["./build/storage_server"]
