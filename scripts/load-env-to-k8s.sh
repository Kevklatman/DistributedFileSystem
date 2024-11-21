#!/bin/bash

# Exit on any error
set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Create namespace if it doesn't exist
kubectl create namespace ${K8S_NAMESPACE:-distributed-fs} --dry-run=client -o yaml | kubectl apply -f -

# Create AWS credentials secret
kubectl create secret generic aws-credentials \
    --namespace=${K8S_NAMESPACE:-distributed-fs} \
    --from-literal=AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
    --from-literal=AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
    --from-literal=AWS_REGION="${AWS_REGION}" \
    --dry-run=client -o yaml | kubectl apply -f -

# Create GCP credentials secret
if [ -f "${GOOGLE_APPLICATION_CREDENTIALS}" ]; then
    kubectl create secret generic gcp-credentials \
        --namespace=${K8S_NAMESPACE:-distributed-fs} \
        --from-file=google-credentials.json="${GOOGLE_APPLICATION_CREDENTIALS}" \
        --from-literal=GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}" \
        --dry-run=client -o yaml | kubectl apply -f -
else
    echo "Warning: GCP credentials file not found at ${GOOGLE_APPLICATION_CREDENTIALS}"
fi

# Create Azure credentials secret
kubectl create secret generic azure-credentials \
    --namespace=${K8S_NAMESPACE:-distributed-fs} \
    --from-literal=AZURE_STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT}" \
    --from-literal=AZURE_STORAGE_KEY="${AZURE_STORAGE_KEY}" \
    --from-literal=AZURE_STORAGE_CONNECTION_STRING="${AZURE_STORAGE_CONNECTION_STRING}" \
    --dry-run=client -o yaml | kubectl apply -f -

# Create hybrid cloud configuration
kubectl create configmap hybrid-cloud-config \
    --namespace=${K8S_NAMESPACE:-distributed-fs} \
    --from-literal=STORAGE_ENV="${STORAGE_ENV}" \
    --from-literal=AWS_PRIORITY="${AWS_PRIORITY}" \
    --from-literal=GCP_PRIORITY="${GCP_PRIORITY}" \
    --from-literal=AZURE_PRIORITY="${AZURE_PRIORITY}" \
    --from-literal=ROUTING_STRATEGY="${ROUTING_STRATEGY}" \
    --from-literal=ENABLE_REPLICATION="${ENABLE_REPLICATION}" \
    --from-literal=REPLICATION_FACTOR="${REPLICATION_FACTOR}" \
    --dry-run=client -o yaml | kubectl apply -f -

echo "Successfully loaded environment variables into Kubernetes secrets and configmaps!"
