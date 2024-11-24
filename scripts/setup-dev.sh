#!/bin/bash

# Enable Kubernetes in Docker Desktop if not already enabled
echo "Please ensure Kubernetes is enabled in Docker Desktop"
echo "Settings -> Kubernetes -> Enable Kubernetes"
echo

# Start local registry if not running
if ! docker ps | grep -q "registry:2"; then
    echo "Starting local Docker registry..."
    docker run -d -p 5000:5000 --restart=always --name registry registry:2
fi

# Build and push images to local registry
echo "Building and pushing images to local registry..."
docker build -t localhost:5000/dfs_core:dev -f Dockerfile .
docker build -t localhost:5000/dfs_edge:dev -f Dockerfile .
docker push localhost:5000/dfs_core:dev
docker push localhost:5000/dfs_edge:dev

# Apply development configuration
echo "Applying Kubernetes development configuration..."
kubectl apply -k src/k8s/dev/

# Wait for pods to be ready
echo "Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app=dfs-core -n dfs-dev --timeout=120s
kubectl wait --for=condition=ready pod -l app=dfs-edge -n dfs-dev --timeout=120s

echo
echo "Development environment is ready!"
echo "Access the services:"
echo "- Grafana: http://localhost:3000 (admin/admin)"
echo "- Prometheus: http://localhost:9090"
echo
echo "To view pods: kubectl get pods -n dfs-dev"
echo "To view logs: kubectl logs -n dfs-dev <pod-name>"
