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

## Usage

### Development (Minikube)
```bash
kubectl apply -k overlays/development
```

### Production
```bash
kubectl apply -k overlays/production
```

## Key Differences

### Development Environment
- Uses NodePort service type with fixed ports (30080, 30090)
- Minikube-specific storage configuration
- WaitForFirstConsumer volume binding mode
- Local storage path configuration

### Production Environment
- Uses LoadBalancer service type
- Cloud-native storage configuration
- Immediate volume binding mode
- Cloud credentials integration
