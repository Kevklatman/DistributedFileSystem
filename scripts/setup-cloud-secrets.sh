#!/bin/bash

# Exit on any error
set -e

# Check if required environment variables are set
check_env_var() {
    if [ -z "${!1}" ]; then
        echo "Error: $1 is not set"
        exit 1
    fi
}

# AWS Credentials
check_env_var "AWS_ACCESS_KEY_ID"
check_env_var "AWS_SECRET_ACCESS_KEY"
AWS_REGION=${AWS_REGION:-us-east-2}

# GCP Credentials
check_env_var "GOOGLE_APPLICATION_CREDENTIALS"
check_env_var "GOOGLE_CLOUD_PROJECT"

# Azure Credentials
check_env_var "AZURE_STORAGE_CONNECTION_STRING"
check_env_var "AZURE_STORAGE_ACCOUNT"
check_env_var "AZURE_STORAGE_KEY"

# Create or update secrets
kubectl apply -f k8s/base/cloud-credentials.yaml

echo "Cloud credentials have been successfully configured in Kubernetes!"
