#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="dfs-development"
REGISTRY="localhost:5000"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

if ! command_exists minikube; then
    echo -e "${RED}Error: minikube is not installed${NC}"
    exit 1
fi

if ! command_exists kubectl; then
    echo -e "${RED}Error: kubectl is not installed${NC}"
    exit 1
fi

if ! command_exists docker; then
    echo -e "${RED}Error: docker is not installed${NC}"
    exit 1
fi

# Start minikube if not running
if ! minikube status > /dev/null 2>&1; then
    echo -e "${BLUE}Starting minikube...${NC}"
    minikube start
fi

# Enable required addons
echo -e "${BLUE}Enabling required addons...${NC}"
minikube addons enable registry
minikube addons enable storage-provisioner
minikube addons enable metrics-server

# Point shell to minikube's Docker daemon
echo -e "${BLUE}Configuring Docker environment...${NC}"
eval $(minikube -p minikube docker-env)

# Build images
echo -e "${BLUE}Building Docker images...${NC}"
cd "$(dirname "$0")/../.."  # Move to project root

# Build API image
echo "Building API image..."
docker build -t ${REGISTRY}/dfs_core:latest -f Dockerfile .

# Build storage node image
echo "Building storage node image..."
docker build -t ${REGISTRY}/dfs_storage:latest -f Dockerfile.storage .

# Create namespace if it doesn't exist
echo -e "${BLUE}Creating namespace...${NC}"
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# Apply Kubernetes configurations
echo -e "${BLUE}Applying Kubernetes configurations...${NC}"
kubectl apply -k src/k8s/overlays/development/

# Wait for pods to be ready
echo -e "${BLUE}Waiting for pods to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=dfs-api -n ${NAMESPACE} --timeout=120s
kubectl wait --for=condition=ready pod -l app=dfs-storage-node -n ${NAMESPACE} --timeout=120s

# Get service URLs
MINIKUBE_IP=$(minikube ip)
API_PORT=$(kubectl get svc -n ${NAMESPACE} dfs-api -o jsonpath='{.spec.ports[0].nodePort}')
METRICS_PORT=$(kubectl get svc -n ${NAMESPACE} dfs-api -o jsonpath='{.spec.ports[1].nodePort}')

echo -e "\n${GREEN}Deployment complete!${NC}"
echo -e "Access your services at:"
echo -e "API: http://${MINIKUBE_IP}:${API_PORT}"
echo -e "Metrics: http://${MINIKUBE_IP}:${METRICS_PORT}"

# Show pod status
echo -e "\n${BLUE}Pod Status:${NC}"
kubectl get pods -n ${NAMESPACE}
