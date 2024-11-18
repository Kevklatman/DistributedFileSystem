#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting DFS Development Environment...${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker first."
    exit 1
fi

# Create necessary directories if they don't exist
echo -e "${BLUE}Setting up directories...${NC}"
mkdir -p data/node{1,2,3} data/edge{1,2}

# Stop any existing containers
echo -e "${BLUE}Cleaning up existing containers...${NC}"
docker-compose down

# Start the distributed system
echo -e "${BLUE}Starting distributed system...${NC}"
docker-compose up -d node1 node2 node3 edge1 edge2 monitoring prometheus grafana locust

# Wait for services to be ready
echo -e "${BLUE}Waiting for services to be ready...${NC}"
sleep 10

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
echo -e "  - Prometheus: http://localhost:9090"
echo -e "  - Grafana: http://localhost:3001 (default: admin/admin)"
echo -e "  - Load Testing UI: http://localhost:8089"

# Check if services are running
echo -e "\n${BLUE}Checking service status...${NC}"
docker-compose ps

echo -e "\n${GREEN}Development environment is ready!${NC}"
echo -e "Use 'docker-compose logs -f' to view logs"
echo -e "Use 'docker-compose down' to stop all services"
