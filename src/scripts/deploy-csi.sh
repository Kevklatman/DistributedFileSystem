#!/bin/bash

# Exit on any error
set -e

echo "Building CSI driver container..."
docker build -t dfs-csi-driver:latest -f src/csi/Dockerfile .

echo "Building storage node container..."
docker build -t dfs-storage-node:latest -f src/storage/Dockerfile .

# If using kind or minikube, load the images
if command -v kind &> /dev/null; then
    echo "Loading images into kind cluster..."
    kind load docker-image dfs-csi-driver:latest
    kind load docker-image dfs-storage-node:latest
elif command -v minikube &> /dev/null; then
    echo "Loading images into minikube..."
    minikube image load dfs-csi-driver:latest
    minikube image load dfs-storage-node:latest
fi

echo "Applying CSI driver and related resources..."
kubectl apply -k k8s/base/

echo "Waiting for CSI driver deployment to be ready..."
kubectl wait --for=condition=ready pod -l app=dfs-csi-driver -n dfs-system --timeout=120s || true

echo "Waiting for storage nodes to be ready..."
kubectl wait --for=condition=ready pod -l app=dfs-node -n default --timeout=120s || true

echo "Waiting for test PVC to be bound..."
kubectl wait --for=condition=bound pvc/test-dfs-pvc -n default --timeout=60s || true

echo "Waiting for test pod to be ready..."
kubectl wait --for=condition=ready pod/test-dfs-pod -n default --timeout=60s || true

echo "Checking pod statuses..."
kubectl get pods -n default
kubectl get pods -n dfs-system

echo "Checking test pod logs (if ready)..."
kubectl logs test-dfs-pod -n default || true

echo "CSI driver deployment completed. Check the pod statuses above for any issues."
