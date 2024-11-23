#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting DFS Development Environment...${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Function to check if port is in use
check_port() {
    lsof -i :$1 > /dev/null 2>&1
    return $?
}

# Check and cleanup ports
check_and_cleanup_ports() {
    # Only check ports that are actually used in docker-compose.yml
    local ports=(8001 8002 8003 8011 8012 9091 3001 8089 5001)
    local has_conflict=false

    echo -e "${BLUE}Checking ports...${NC}"
    for port in "${ports[@]}"; do
        if check_port $port; then
            echo -e "${RED}Port $port is in use${NC}"
            has_conflict=true
        fi
    done

    if $has_conflict; then
        echo -e "${BLUE}Attempting to clean up existing containers...${NC}"
        # First try graceful shutdown
        docker-compose down --remove-orphans
        sleep 2

        # If ports are still in use, force remove containers
        for port in "${ports[@]}"; do
            if check_port $port; then
                echo -e "${RED}Port $port is still in use. Attempting force cleanup...${NC}"
                container_id=$(docker ps -a | grep ":$port->" | awk '{print $1}')
                if [ ! -z "$container_id" ]; then
                    docker rm -f $container_id
                fi
            fi
        done

        # Final port check
        for port in "${ports[@]}"; do
            if check_port $port; then
                echo -e "${RED}Port $port is still in use by another process. Please free this port before continuing.${NC}"
                exit 1
            fi
        done
    fi
}

# Check and cleanup ports
check_and_cleanup_ports

# Start the distributed system
echo -e "${BLUE}Starting distributed system...${NC}"
docker-compose up -d

# Function to check if a service is healthy
check_service_health() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=1

    echo -n "Waiting for $service to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:$port" > /dev/null 2>&1; then
            echo -e "${GREEN}ready${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e "${RED}failed${NC}"
    return 1
}

# Wait for core services
echo -e "${BLUE}Waiting for services to be ready...${NC}"
check_service_health "Node 1" 8001
check_service_health "Node 2" 8002
check_service_health "Node 3" 8003
check_service_health "Prometheus" 9091
check_service_health "Grafana" 3001

# Print access information
echo -e "${GREEN}DFS Development Environment is ready!${NC}"
echo -e "${GREEN}Access points:${NC}"
echo -e "Core Nodes:"
echo -e "  - Node 1: http://localhost:8001"
echo -e "  - Node 2: http://localhost:8002"
echo -e "  - Node 3: http://localhost:8003"
echo -e "Edge Nodes:"
echo -e "  - Edge 1: http://localhost:8011"
echo -e "  - Edge 2: http://localhost:8012"
echo -e "Monitoring:"
echo -e "  - Monitoring UI: http://localhost:5001"
echo -e "  - Prometheus: http://localhost:9091"
echo -e "  - Grafana: http://localhost:3001 (default: admin/admin)"
echo -e "  - Load Testing UI: http://localhost:8089"

# Check if services are running
echo -e "\n${BLUE}Checking service status...${NC}"
docker-compose ps

echo -e "\n${GREEN}Development environment is ready!${NC}"
echo -e "Use 'docker-compose logs -f' to view logs"
echo -e "Use 'docker-compose down' to stop all services"
