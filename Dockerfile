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
    protobuf-compiler-grpc \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Flask
RUN pip3 install Flask

# Set working directory
WORKDIR /app

# Copy source code
COPY . .

# Create build directory
RUN mkdir -p build

# Build the application
WORKDIR /app/build
RUN cmake -DCMAKE_BUILD_TYPE=Debug .. && \
    make -j$(nproc)

WORKDIR /app

# Expose gRPC and Flask ports
EXPOSE 50051 5000

# Run the Flask app from api directory
CMD ["python3", "api/app.py"]
