#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting DFS Load Testing Environment...${NC}"

# Check if development environment is running
if ! docker ps | grep -q "distributedfilesystem-dfs_core"; then
    echo -e "${RED}Error: Development environment is not running.${NC}"
    echo -e "Please start the development environment first with:"
    echo -e "  ./scripts/start_dev.sh"
    exit 1
fi

# Change to load testing directory
cd "$(dirname "$0")/../tests/load" || exit

# Start load testing environment
echo -e "${BLUE}Starting Locust...${NC}"
docker-compose -f docker-compose.load.yml up -d

# Get the allocated port for Locust UI
LOCUST_PORT=$(docker-compose -f docker-compose.load.yml ps -q locust | xargs docker port | grep 8089 | cut -d: -f2)

echo -e "${GREEN}Load testing environment is ready!${NC}"
echo -e "Access the Locust UI at: http://localhost:${LOCUST_PORT}"
echo -e "View metrics at: http://localhost:9100/metrics"
echo -e "\nTo stop the load testing environment:"
echo -e "  cd tests/load && docker-compose -f docker-compose.load.yml down"
