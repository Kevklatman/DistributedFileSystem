#!/bin/bash
# Main environment setup and management script for DFS

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
DEFAULT_NAMESPACE="dfs-development"
DEFAULT_STORAGE_CLASS="standard"
DEFAULT_REGISTRY="localhost:5000"

# Function to show usage
show_usage() {
    echo "Usage: $0 <command> [options]"
    echo
    echo "Commands:"
    echo "  start         Start development environment"
    echo "  stop          Stop development environment"
    echo "  deploy        Deploy DFS components"
    echo "  setup         Setup initial configuration"
    echo "  test          Run tests"
    echo "  clean         Clean up environment"
    echo "  status        Show environment status"
    echo
    echo "Options:"
    echo "  --namespace   Kubernetes namespace (default: $DEFAULT_NAMESPACE)"
    echo "  --registry    Container registry (default: $DEFAULT_REGISTRY)"
    echo "  --config      Path to config file"
    echo "  --help        Show this help message"
}

# Function to check prerequisites
check_prerequisites() {
    local missing_deps=false

    echo -e "${BLUE}Checking prerequisites...${NC}"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker is not installed${NC}"
        missing_deps=true
    elif ! docker info &> /dev/null; then
        echo -e "${RED}Docker is not running${NC}"
        missing_deps=true
    fi

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}kubectl is not installed${NC}"
        missing_deps=true
    fi

    # Check Kubernetes
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}Kubernetes is not running${NC}"
        missing_deps=true
    fi

    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is not installed${NC}"
        missing_deps=true
    fi

    if $missing_deps; then
        echo -e "${RED}Please install missing dependencies and try again${NC}"
        exit 1
    fi
}

# Function to start development environment
start_dev() {
    check_prerequisites

    echo -e "${BLUE}Starting DFS development environment...${NC}"
    
    # Start local registry if not running
    if ! docker ps | grep -q "registry:2"; then
        echo "Starting local Docker registry..."
        docker run -d -p 5000:5000 --restart=always --name registry registry:2
    fi

    # Build and push images
    echo "Building and pushing images..."
    docker build -t localhost:5000/dfs_core:dev -f Dockerfile .
    docker build -t localhost:5000/dfs_edge:dev -f Dockerfile .
    docker push localhost:5000/dfs_core:dev
    docker push localhost:5000/dfs_edge:dev

    # Apply Kubernetes configurations
    echo "Applying Kubernetes configurations..."
    kubectl apply -k src/k8s/overlays/development/

    # Wait for pods to be ready
    echo "Waiting for pods to be ready..."
    kubectl wait --for=condition=ready pod -l app=dfs-core -n dfs-development --timeout=120s
    kubectl wait --for=condition=ready pod -l app=dfs-edge -n dfs-development --timeout=120s

    echo -e "${GREEN}Development environment is ready!${NC}"
    echo -e "Access services at:"
    echo -e "  - Grafana: http://localhost:3000 (admin/admin)"
    echo -e "  - Prometheus: http://localhost:9090"
    echo -e "  - API Docs: http://localhost:8000/docs"
}

# Function to stop development environment
stop_dev() {
    echo -e "${BLUE}Stopping DFS development environment...${NC}"
    
    # Delete all resources in the dev namespace
    kubectl delete namespace dfs-development --ignore-not-found=true

    # Stop local registry
    docker stop registry && docker rm registry || true

    echo -e "${GREEN}Development environment stopped${NC}"
}

# Function to deploy DFS components
deploy_components() {
    local namespace=$1
    local config=$2

    echo -e "${BLUE}Deploying DFS components...${NC}"

    # Build and push images
    docker build -t ${DEFAULT_REGISTRY}/dfs_core:latest -f Dockerfile .
    docker build -t ${DEFAULT_REGISTRY}/dfs_edge:latest -f Dockerfile .
    docker push ${DEFAULT_REGISTRY}/dfs_core:latest
    docker push ${DEFAULT_REGISTRY}/dfs_edge:latest

    # Apply Kubernetes configurations
    kubectl apply -k src/k8s/base/

    # Wait for deployments
    kubectl wait --for=condition=available deployment -l app=dfs-core -n "$namespace" --timeout=300s
    kubectl wait --for=condition=available deployment -l app=dfs-edge -n "$namespace" --timeout=300s
}

# Function to run tests
run_tests() {
    echo -e "${BLUE}Running tests...${NC}"
    
    # Run unit tests
    python3 -m pytest tests/unit

    # Run integration tests if environment is ready
    if kubectl get pods -n dfs-development -l app=dfs-core | grep -q Running; then
        python3 -m pytest tests/integration
    else
        echo -e "${RED}Development environment is not running. Skipping integration tests.${NC}"
    fi

    # Run load tests
    if [ -f "tests/load/load_test.py" ]; then
        python3 tests/load/load_test.py
    fi
}

# Function to clean up environment
cleanup_env() {
    echo -e "${BLUE}Cleaning up environment...${NC}"
    
    # Delete development namespace
    kubectl delete namespace dfs-development --ignore-not-found=true
    
    # Delete production namespace if exists
    kubectl delete namespace dfs --ignore-not-found=true
    
    # Delete CRDs
    kubectl delete crd dfsnodes.dfs.codeium.com --ignore-not-found=true

    # Clean up local resources
    rm -rf data/* logs/*

    # Stop and remove local registry
    docker stop registry && docker rm registry || true
}

# Function to show status
show_status() {
    echo -e "${BLUE}DFS Environment Status${NC}"
    
    echo -e "\nKubernetes Pods:"
    kubectl get pods -n dfs-development

    echo -e "\nKubernetes Services:"
    kubectl get services -n dfs-development

    echo -e "\nKubernetes Deployments:"
    kubectl get deployments -n dfs-development
}

# Main script logic
main() {
    local COMMAND=""
    local NAMESPACE="$DEFAULT_NAMESPACE"
    local REGISTRY="$DEFAULT_REGISTRY"
    local CONFIG=""

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            start|stop|deploy|setup|test|clean|status)
                COMMAND="$1"
                shift
                ;;
            --namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            --registry)
                REGISTRY="$2"
                shift 2
                ;;
            --config)
                CONFIG="$2"
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
            start_dev
            ;;
        stop)
            stop_dev
            ;;
        deploy)
            deploy_components "$NAMESPACE" "$CONFIG"
            ;;
        setup)
            setup_env "$NAMESPACE" "$REGISTRY"
            ;;
        test)
            run_tests
            ;;
        clean)
            cleanup_env
            ;;
        status)
            show_status
            ;;
        *)
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
