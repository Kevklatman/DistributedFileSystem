# Kubernetes Configuration

This directory contains Kubernetes configurations for the Distributed File System (DFS).

## Directory Structure

```
k8s/
├── base/                  # Base configurations shared across environments
│   ├── deployment.yaml
│   ├── service.yaml
│   └── storage-class.yaml
└── overlays/             # Environment-specific configurations
    ├── development/      # Local development (Minikube) settings
    │   ├── kustomization.yaml
    │   ├── service-patch.yaml
    │   └── storage-class-patch.yaml
    └── production/       # Production environment settings
        ├── kustomization.yaml
        ├── service-patch.yaml
        └── storage-class-patch.yaml
```

## Local Development Setup

### Prerequisites
1. Docker Desktop with Kubernetes enabled
2. Skaffold CLI installed (`brew install skaffold`)

### Building Images Locally
The project uses Skaffold for local development workflow. Images are built locally and deployed to your local Kubernetes cluster.

```bash
# Start local development with hot reload
skaffold dev --profile=dev

# Build images once
skaffold build --profile=dev

# Deploy to local cluster
skaffold run --profile=dev
```

### Manual Deployment
If you prefer to build and deploy manually:

1. Build the images:
```bash
# From project root
docker build -t dfs-storage-node:latest src/storage-node/
docker build -t dfs-csi-driver:latest src/csi/
```

2. Apply Kubernetes configurations:
```bash
kubectl apply -k overlays/development
```

## Production Deployment

### Prerequisites
1. Access to container registry
2. Kubernetes cluster access
3. Required cloud credentials

### Deployment Steps
```bash
# Build and push images
skaffold run --profile=prod

# Or apply configurations directly if images are already pushed
kubectl apply -k overlays/production
```

## Key Differences

### Development Environment
- Uses NodePort service type with fixed ports (30080, 30090)
- Minikube-specific storage configuration
- WaitForFirstConsumer volume binding mode
- Local storage path configuration
- Images built locally with IfNotPresent pull policy

### Production Environment
- Uses LoadBalancer service type
- Cloud-native storage configuration
- WaitForFirstConsumer volume binding mode
- Cloud credentials integration
- Images pulled from container registry
