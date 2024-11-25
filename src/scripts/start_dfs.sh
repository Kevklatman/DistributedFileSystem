#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default environment variables
export STORAGE_ROOT="/Users/kevinklatman/Development/Code/DistributedFileSystem/data/dfs"
export NODE_ID="test-node-1"
export CLOUD_PROVIDER_TYPE="aws"
export FLASK_APP="/Users/kevinklatman/Development/Code/DistributedFileSystem/src/api/app.py"
export FLASK_ENV="development"
export PYTHONPATH="/Users/kevinklatman/Development/Code/DistributedFileSystem"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if minikube is running
minikube_status() {
    minikube status | grep -q "Running"
}

# Function to print status messages
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[-]${NC} $1"
}

# Check for required commands
for cmd in python3 minikube kubectl; do
    if ! command_exists $cmd; then
        print_error "$cmd is not installed. Please install it first."
        exit 1
    fi
done

# Create necessary directories
mkdir -p "$STORAGE_ROOT"
print_status "Created storage directory at $STORAGE_ROOT"

# Start Minikube if it's not running
if ! minikube_status; then
    print_status "Starting Minikube..."
    minikube start
    if [ $? -ne 0 ]; then
        print_error "Failed to start Minikube"
        exit 1
    fi
else
    print_status "Minikube is already running"
fi

# Apply Kubernetes configurations
print_status "Applying Kubernetes configurations..."
kubectl apply -f /Users/kevinklatman/Development/Code/DistributedFileSystem/kubernetes/config/ || {
    print_error "Failed to apply Kubernetes configurations"
    exit 1
}

# Start Flask app in the background
print_status "Starting Flask application..."
python3 -m flask run --host=0.0.0.0 --port=8001 &
FLASK_PID=$!

# Function to cleanup on script exit
cleanup() {
    print_status "Cleaning up..."
    if [ ! -z "$FLASK_PID" ]; then
        kill $FLASK_PID 2>/dev/null
    fi
    print_status "Cleanup complete"
}

# Register cleanup function
trap cleanup EXIT

# Print startup complete message
print_status "DFS startup complete!"
print_status "Flask app running on http://localhost:8001"
print_status "Kubernetes dashboard can be accessed with: minikube dashboard"
print_warning "Press Ctrl+C to shutdown all services"

# Wait for user interrupt
wait $FLASK_PID
