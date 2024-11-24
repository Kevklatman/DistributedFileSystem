#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
DEFAULT_NAMESPACE="dfs-development"
DEFAULT_REGISTRY="localhost:8000"

# Default ports
DEFAULT_API_PORT=8080
DEFAULT_API_METRICS_PORT=9090
DEFAULT_STORAGE_PORT=8081
DEFAULT_STORAGE_METRICS_PORT=9091
DEFAULT_NODE_PORT_API=30080
DEFAULT_NODE_PORT_METRICS=30090

# Port forwarding PID file
PORT_FORWARD_PID_FILE="/tmp/dfs-port-forward.pid"

# Function to show usage
show_usage() {
    echo "Usage: $0 <command> [options]"
    echo
    echo "Commands:"
    echo "  start         Start development environment"
    echo "  stop          Stop development environment"
    echo "  status        Show environment status"
    echo "  clean         Clean up environment"
    echo "  forward       Start port forwarding"
    echo "  unforward     Stop port forwarding"
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

# Function to start port forwarding
start_port_forward() {
    local namespace=$1
    local api_port=$2
    local api_metrics=$3

    # Kill any existing port forward processes
    if [ -f "$PORT_FORWARD_PID_FILE" ]; then
        kill $(cat "$PORT_FORWARD_PID_FILE") 2>/dev/null || true
        rm "$PORT_FORWARD_PID_FILE"
    fi

    echo -e "${BLUE}Starting port forwarding...${NC}"
    
    # Start port forwarding for API service
    kubectl port-forward -n ${namespace} service/dfs-api-service ${api_port}:${api_port} &
    echo $! > "$PORT_FORWARD_PID_FILE"
    
    # Start port forwarding for metrics
    kubectl port-forward -n ${namespace} service/dfs-api-service ${api_metrics}:${api_metrics} &
    echo $! >> "$PORT_FORWARD_PID_FILE"

    echo -e "${GREEN}Port forwarding started!${NC}"
    echo -e "Access services at:"
    echo -e "  - API: http://localhost:${api_port}"
    echo -e "  - API Metrics: http://localhost:${api_metrics}"
}

# Function to stop port forwarding
stop_port_forward() {
    if [ -f "$PORT_FORWARD_PID_FILE" ]; then
        echo -e "${BLUE}Stopping port forwarding...${NC}"
        kill $(cat "$PORT_FORWARD_PID_FILE") 2>/dev/null || true
        rm "$PORT_FORWARD_PID_FILE"
        echo -e "${GREEN}Port forwarding stopped${NC}"
    else
        echo -e "${BLUE}No port forwarding processes found${NC}"
    fi
}

# Function to update Kubernetes configurations with new ports
update_k8s_configs() {
    local api_port=$1
    local api_metrics=$2
    local storage_port=$3
    local storage_metrics=$4

    # Update API service configuration
    cat > src/k8s/base/api-service.yaml << EOF
apiVersion: v1
kind: Service
metadata:
  name: dfs-api-service
  labels:
    app: dfs-api
spec:
  selector:
    app: dfs-api
  ports:
    - name: http
      protocol: TCP
      port: ${api_port}
      targetPort: ${api_port}
    - name: metrics
      protocol: TCP
      port: ${api_metrics}
      targetPort: ${api_metrics}
  type: ClusterIP
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
    update_k8s_configs "$api_port" "$api_metrics" "$storage_port" "$storage_metrics"

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

    # Start port forwarding
    start_port_forward "$namespace" "$api_port" "$api_metrics"
    
    echo -e "${GREEN}Development environment is ready!${NC}"
}

# Function to stop development environment
stop_dev() {
    local namespace=$1
    echo -e "${BLUE}Stopping DFS development environment...${NC}"
    
    # Stop port forwarding
    stop_port_forward
    
    # Delete namespace
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
    
    # Check port forwarding
    echo -e "\nPort Forwarding Status:"
    if [ -f "$PORT_FORWARD_PID_FILE" ]; then
        echo "Port forwarding is active"
        echo "PIDs: $(cat "$PORT_FORWARD_PID_FILE")"
    else
        echo "Port forwarding is not active"
    fi
}

# Function to clean up environment
clean_env() {
    local namespace=$1
    echo -e "${BLUE}Cleaning up environment...${NC}"
    
    # Stop port forwarding
    stop_port_forward
    
    # Delete namespace and resources
    kubectl delete namespace ${namespace} --ignore-not-found
    
    echo -e "${GREEN}Environment cleaned${NC}"
}

# Main script logic
main() {
    local COMMAND=""
    local NAMESPACE="$DEFAULT_NAMESPACE"
    local REGISTRY="$DEFAULT_REGISTRY"
    local API_PORT="$DEFAULT_API_PORT"
    local API_METRICS="$DEFAULT_API_METRICS_PORT"
    local STORAGE_PORT="$DEFAULT_STORAGE_PORT"
    local STORAGE_METRICS="$DEFAULT_STORAGE_METRICS_PORT"

    # Parse command
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    COMMAND="$1"
    shift

    # Parse options
    while [ $# -gt 0 ]; do
        case "$1" in
            --namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            --registry)
                REGISTRY="$2"
                shift 2
                ;;
            --api-port)
                API_PORT="$2"
                shift 2
                ;;
            --api-metrics)
                API_METRICS="$2"
                shift 2
                ;;
            --storage-port)
                STORAGE_PORT="$2"
                shift 2
                ;;
            --storage-metrics)
                STORAGE_METRICS="$2"
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
    case "$COMMAND" in
        start)
            start_dev "$NAMESPACE" "$REGISTRY" "$API_PORT" "$API_METRICS" "$STORAGE_PORT" "$STORAGE_METRICS"
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
        forward)
            start_port_forward "$NAMESPACE" "$API_PORT" "$API_METRICS"
            ;;
        unforward)
            stop_port_forward
            ;;
        *)
            echo "Unknown command: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
