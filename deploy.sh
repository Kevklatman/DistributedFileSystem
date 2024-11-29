#!/bin/bash
set -e

# Build Docker image
echo "Building Docker image..."
docker build -t dfs-storage-node:latest .

# Apply Kubernetes configurations
echo "Applying Kubernetes configurations..."

# Create namespace if it doesn't exist
kubectl create namespace distributed-fs --dry-run=client -o yaml | kubectl apply -f -

# Apply base configurations
kubectl apply -k src/k8s/base/

# Wait for deployments to be ready
echo "Waiting for deployments to be ready..."
kubectl -n distributed-fs rollout status statefulset/dfs-storage-node
kubectl -n distributed-fs rollout status deployment/dfs-haproxy

# Get service URL
echo "Getting service URL..."
EXTERNAL_IP=$(kubectl -n distributed-fs get service dfs-haproxy -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
if [ -z "$EXTERNAL_IP" ]; then
    EXTERNAL_IP=$(kubectl -n distributed-fs get service dfs-haproxy -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
fi

echo "Deployment complete!"
echo "Service available at: http://$EXTERNAL_IP:8000"
echo "Metrics available at: http://$EXTERNAL_IP:9091/metrics"
echo "HAProxy stats available at: http://$EXTERNAL_IP:8404"
