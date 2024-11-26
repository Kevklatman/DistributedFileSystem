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


=

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


## Key Differences

### Development Environment
- Uses NodePort service type with fixed ports (30080, 30090)
- Minikube-specific storage configuration
- WaitForFirstConsumer volume binding mode
- Local storage path configuration
- Images built locally with IfNotPresent pull policy


