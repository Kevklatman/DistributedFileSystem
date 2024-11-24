#!/bin/bash
# Main environment setup and management script for DFS

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
DEFAULT_NAMESPACE="dfs"
DEFAULT_STORAGE_CLASS="standard"
DEFAULT_REGISTRY="docker.io"

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

# Function to check and cleanup ports
check_and_cleanup_ports() {
    local ports=(8001 8002 8003 8011 8012 9091 3001 8089 5001)
    local has_conflict=false

    echo -e "${BLUE}Checking ports...${NC}"
    for port in "${ports[@]}"; do
        if lsof -i :$port > /dev/null 2>&1; then
            echo -e "${RED}Port $port is in use${NC}"
            has_conflict=true
        fi
    done

    if $has_conflict; then
        echo -e "${BLUE}Attempting to clean up existing containers...${NC}"
        docker-compose down --remove-orphans
        sleep 2

        for port in "${ports[@]}"; do
            if lsof -i :$port > /dev/null 2>&1; then
                container_id=$(docker ps -a | grep ":$port->" | awk '{print $1}')
                if [ ! -z "$container_id" ]; then
                    docker rm -f $container_id
                fi
            fi
        done
    fi
}

# Function to start development environment
start_dev() {
    check_prerequisites
    check_and_cleanup_ports

    echo -e "${BLUE}Starting DFS development environment...${NC}"
    
    # Start infrastructure services
    docker-compose up -d

    # Wait for services to be ready
    local services=(
        "Node-1:8001"
        "Node-2:8002"
        "Node-3:8003"
        "Prometheus:9091"
        "Grafana:3001"
    )

    for service in "${services[@]}"; do
        IFS=':' read -r name port <<< "$service"
        echo -n "Waiting for $name to be ready..."
        local attempts=0
        while ! curl -s "http://localhost:$port" > /dev/null && [ $attempts -lt 30 ]; do
            echo -n "."
            sleep 1
            ((attempts++))
        done
        if [ $attempts -lt 30 ]; then
            echo -e "${GREEN}ready${NC}"
        else
            echo -e "${RED}failed${NC}"
        fi
    done

    echo -e "${GREEN}Development environment is ready!${NC}"
    echo -e "Access services at:"
    echo -e "  - Management UI: http://localhost:3001"
    echo -e "  - Metrics: http://localhost:9091"
    echo -e "  - API Docs: http://localhost:8001/docs"
}

# Function to deploy DFS components
deploy_components() {
    local namespace=$1
    local config=$2

    echo -e "${BLUE}Deploying DFS components...${NC}"

    # Deploy CSI driver
    echo "Building and deploying CSI driver..."
    docker build -t dfs-csi-driver:latest -f src/csi/Dockerfile .
    docker build -t dfs-storage-node:latest -f src/storage/Dockerfile .

    # Load images into local cluster if using kind/minikube
    if command -v kind &> /dev/null; then
        kind load docker-image dfs-csi-driver:latest
        kind load docker-image dfs-storage-node:latest
    elif command -v minikube &> /dev/null; then
        minikube image load dfs-csi-driver:latest
        minikube image load dfs-storage-node:latest
    fi

    # Deploy using node_management.py
    python3 src/scripts/node_management.py deploy \
        --namespace "$namespace" \
        --config "$config"
}

# Function to run tests
run_tests() {
    echo -e "${BLUE}Running tests...${NC}"
    
    # Run unit tests
    python3 -m pytest tests/unit

    # Run integration tests if environment is ready
    if curl -s "http://localhost:8001/health" > /dev/null; then
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
    
    # Stop all containers
    docker-compose down --remove-orphans

    # Clean up Kubernetes resources
    kubectl delete namespace dfs --ignore-not-found
    kubectl delete crd dfsnodes.dfs.codeium.com --ignore-not-found

    # Clean up local resources
    rm -rf data/* logs/*
}

# Main script logic
main() {
    if [ $# -eq 0 ] || [ "$1" == "--help" ]; then
        show_usage
        exit 0
    fi

    local command=$1
    shift

    # Parse options
    local namespace=$DEFAULT_NAMESPACE
    local registry=$DEFAULT_REGISTRY
    local config="src/scripts/cluster_config.yaml"

    while [ $# -gt 0 ]; do
        case "$1" in
            --namespace)
                namespace="$2"
                shift 2
                ;;
            --registry)
                registry="$2"
                shift 2
                ;;
            --config)
                config="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    case "$command" in
        start)
            start_dev
            ;;
        stop)
            docker-compose down
            ;;
        deploy)
            deploy_components "$namespace" "$config"
            ;;
        setup)
            python3 src/scripts/setup-credentials.py
            ;;
        test)
            run_tests
            ;;
        clean)
            cleanup_env
            ;;
        status)
            python3 src/scripts/node_management.py monitor --namespace "$namespace"
            ;;
        *)
            echo "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
