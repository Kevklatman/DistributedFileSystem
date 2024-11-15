# Dockerfile
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libssl-dev \
    python3 \
    python3-pip \
    git \
    autoconf \
    automake \
    libtool \
    curl \
    make \
    g++ \
    libgrpc++-dev \
    protobuf-compiler-grpc

# Install Flask
RUN pip3 install Flask

# Set working directory
WORKDIR /app

# Copy source code
COPY . .

# Ensure a clean build directory
RUN rm -rf build && mkdir build

# Build the application with verbose output
RUN cd build && \
    cmake -DCMAKE_BUILD_TYPE=Debug .. && \
    make VERBOSE=1 -j$(nproc)

# Expose gRPC and Flask ports
EXPOSE 50051 5000

# Run the main DFS executable
CMD ["python3", "app.py"]
