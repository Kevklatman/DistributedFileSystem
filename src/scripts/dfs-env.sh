#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
DEFAULT_NAMESPACE="dfs-development"
DEFAULT_REGISTRY="localhost:5000"

# Default ports
DEFAULT_API_PORT=8080
DEFAULT_API_METRICS_PORT=9090
DEFAULT_STORAGE_PORT=8081
DEFAULT_STORAGE_METRICS_PORT=9091
DEFAULT_NODE_PORT_API=30080
DEFAULT_NODE_PORT_METRICS=30090

# Function to show usage
show_usage() {
    echo "Usage: $0 <command> [options]"
    echo
    echo "Commands:"
    echo "  start         Start development environment"
    echo "  stop          Stop development environment"
    echo "  status        Show environment status"
    echo "  clean         Clean up environment"
    echo
    echo "Options:"
    echo "  --namespace     Kubernetes namespace (default: $DEFAULT_NAMESPACE)"
    echo "  --registry      Container registry (default: $DEFAULT_REGISTRY)"
    echo "  --api-port      API service port (default: $DEFAULT_API_PORT)"
    echo "  --api-metrics   API metrics port (default: $DEFAULT_API_METRICS_PORT)"
    echo "  --storage-port  Storage node port (default: $DEFAULT_STORAGE_PORT)"
    echo "  --storage-metrics Storage metrics port (default: $DEFAULT_STORAGE_METRICS_PORT)"
    echo "  --nodeport-api  Kubernetes NodePort for API (default: $DEFAULT_NODE_PORT_API)"
    echo "  --nodeport-metrics Kubernetes NodePort for metrics (default: $DEFAULT_NODE_PORT_METRICS)"
    echo "  --help         Show this help message"
}

# Function to check prerequisites
check_prerequisites() {
    local missing_deps=false
    echo -e "${BLUE}Checking prerequisites...${NC}"

    # Check required commands
    local commands=("docker" "kubectl" "minikube")
    for cmd in "${commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            echo -e "${RED}$cmd is not installed${NC}"
            missing_deps=true
        fi
    done

    # Check Docker daemon
    if ! docker info &> /dev/null; then
        echo -e "${RED}Docker daemon is not running${NC}"
        missing_deps=true
    fi

    if $missing_deps; then
        echo -e "${RED}Please install missing dependencies and try again${NC}"
        exit 1
    fi
}

# Function to update Kubernetes configurations with new ports
update_k8s_configs() {
    local api_port=$1
    local api_metrics=$2
    local storage_port=$3
    local storage_metrics=$4
    local nodeport_api=$5
    local nodeport_metrics=$6

    # Update service patch for development
    cat > src/k8s/overlays/development/service-patch.yaml << EOF
apiVersion: v1
kind: Service
metadata:
  name: dfs-api
spec:
  type: NodePort
  ports:
  - port: ${api_port}
    targetPort: ${api_port}
    nodePort: ${nodeport_api}
  - port: ${api_metrics}
    targetPort: ${api_metrics}
    nodePort: ${nodeport_metrics}
EOF

    # Update storage service configuration
    cat > src/k8s/base/service.yaml << EOF
apiVersion: v1
kind: Service
metadata:
  name: dfs-storage-service
  labels:
    app: dfs-storage-node
spec:
  selector:
    app: dfs-storage-node
  ports:
    - name: http
      protocol: TCP
      port: ${storage_port}
      targetPort: ${storage_port}
    - name: metrics
      protocol: TCP
      port: ${storage_metrics}
      targetPort: ${storage_metrics}
  type: ClusterIP
EOF
}

# Function to start development environment
start_dev() {
    local namespace=$1
    local registry=$2
    local api_port=$3
    local api_metrics=$4
    local storage_port=$5
    local storage_metrics=$6
    local nodeport_api=$7
    local nodeport_metrics=$8

    check_prerequisites

    echo -e "${BLUE}Starting DFS development environment...${NC}"
    
    # Ensure minikube is running
    if ! minikube status &> /dev/null; then
        echo "Starting minikube..."
        minikube start
    fi

    # Enable required addons
    echo "Enabling minikube addons..."
    minikube addons enable registry
    minikube addons enable storage-provisioner
    minikube addons enable metrics-server

    # Point shell to minikube's Docker daemon
    echo "Configuring Docker environment..."
    eval $(minikube -p minikube docker-env)

    # Update Kubernetes configurations with new ports
    echo "Updating Kubernetes configurations..."
    update_k8s_configs "$api_port" "$api_metrics" "$storage_port" "$storage_metrics" "$nodeport_api" "$nodeport_metrics"

    # Build images directly in minikube
    echo "Building images in minikube..."
    cd "$(dirname "$0")/../.."  # Move to project root
    docker build -t ${registry}/dfs_core:latest .
    docker build -f Dockerfile.storage -t ${registry}/dfs_storage:latest .

    # Apply Kubernetes configurations
    echo "Applying Kubernetes configurations..."
    kubectl create namespace ${namespace} --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -k src/k8s/overlays/development/

    # Wait for pods to be ready
    echo "Waiting for pods to be ready..."
    kubectl wait --for=condition=ready pod -l app=dfs-api -n ${namespace} --timeout=120s
    kubectl wait --for=condition=ready pod -l app=dfs-storage-node -n ${namespace} --timeout=120s

    # Get minikube IP
    MINIKUBE_IP=$(minikube ip)
    
    echo -e "${GREEN}Development environment is ready!${NC}"
    echo -e "Access services at:"
    echo -e "  - API: http://${MINIKUBE_IP}:${nodeport_api}"
    echo -e "  - API Metrics: http://${MINIKUBE_IP}:${nodeport_metrics}"
    echo -e "  - Storage Nodes: Accessible through API"
}

# Function to stop development environment
stop_dev() {
    local namespace=$1
    echo -e "${BLUE}Stopping DFS development environment...${NC}"
    kubectl delete namespace ${namespace} --ignore-not-found
    echo -e "${GREEN}Environment stopped${NC}"
}

# Function to show status
show_status() {
    local namespace=$1
    echo -e "${BLUE}DFS Environment Status:${NC}"
    
    # Check minikube status
    echo "Minikube Status:"
    minikube status
    
    # Check pods
    echo -e "\nPod Status:"
    kubectl get pods -n ${namespace}
    
    # Check services
    echo -e "\nService Status:"
    kubectl get services -n ${namespace}
    
    # Show URLs if environment is running
    if MINIKUBE_IP=$(minikube ip 2>/dev/null); then
        echo -e "\nService URLs:"
        echo "API: http://${MINIKUBE_IP}:${DEFAULT_NODE_PORT_API}"
        echo "Metrics: http://${MINIKUBE_IP}:${DEFAULT_NODE_PORT_METRICS}"
    fi
}

# Function to clean up environment
clean_env() {
    local namespace=$1
    echo -e "${BLUE}Cleaning up DFS environment...${NC}"
    
    # Delete namespace and all resources
    kubectl delete namespace ${namespace} --ignore-not-found
    
    # Clean up Docker images
    echo "Cleaning up Docker images..."
    docker rmi $(docker images -q 'localhost:5000/dfs_*') 2>/dev/null || true
    
    echo -e "${GREEN}Cleanup complete${NC}"
}

# Main script logic
main() {
    local NAMESPACE=$DEFAULT_NAMESPACE
    local REGISTRY=$DEFAULT_REGISTRY
    local API_PORT=$DEFAULT_API_PORT
    local API_METRICS_PORT=$DEFAULT_API_METRICS_PORT
    local STORAGE_PORT=$DEFAULT_STORAGE_PORT
    local STORAGE_METRICS_PORT=$DEFAULT_STORAGE_METRICS_PORT
    local NODE_PORT_API=$DEFAULT_NODE_PORT_API
    local NODE_PORT_METRICS=$DEFAULT_NODE_PORT_METRICS

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            start|stop|status|clean)
                COMMAND=$1
                shift
                ;;
            --namespace)
                NAMESPACE=$2
                shift 2
                ;;
            --registry)
                REGISTRY=$2
                shift 2
                ;;
            --api-port)
                API_PORT=$2
                shift 2
                ;;
            --api-metrics)
                API_METRICS_PORT=$2
                shift 2
                ;;
            --storage-port)
                STORAGE_PORT=$2
                shift 2
                ;;
            --storage-metrics)
                STORAGE_METRICS_PORT=$2
                shift 2
                ;;
            --nodeport-api)
                NODE_PORT_API=$2
                shift 2
                ;;
            --nodeport-metrics)
                NODE_PORT_METRICS=$2
                shift 2
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Execute command
    case $COMMAND in
        start)
            start_dev "$NAMESPACE" "$REGISTRY" "$API_PORT" "$API_METRICS_PORT" \
                     "$STORAGE_PORT" "$STORAGE_METRICS_PORT" \
                     "$NODE_PORT_API" "$NODE_PORT_METRICS"
            ;;
        stop)
            stop_dev "$NAMESPACE"
            ;;
        status)
            show_status "$NAMESPACE"
            ;;
        clean)
            clean_env "$NAMESPACE"
            ;;
        *)
            echo "No command specified"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
