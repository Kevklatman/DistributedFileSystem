#!/bin/bash

# Build the Docker image
echo "Building Docker image..."
docker build -t dfs-api:latest ./src/api

# Apply Kubernetes configurations
echo "Applying Kubernetes configurations..."
kubectl apply -f k8s/api-deployment.yaml

# Wait for deployment to be ready
echo "Waiting for deployment to be ready..."
kubectl rollout status deployment/dfs-api

# Get service URL
echo "Getting service URL..."
kubectl get service dfs-api-service

echo "Deployment complete! You can access the API through the LoadBalancer external IP."
