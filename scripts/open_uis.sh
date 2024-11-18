#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Opening DFS Web UIs...${NC}"

# Function to open URL and check if it's accessible
open_url() {
    local url=$1
    local name=$2
    if curl -s --head "$url" > /dev/null; then
        echo -e "${GREEN}✓${NC} Opening $name: $url"
        open "$url"
    else
        echo -e "⚠️  Warning: $name is not accessible at $url"
    fi
}

# Open Core Nodes
echo -e "\n${BLUE}Opening Core Nodes...${NC}"
open_url "http://localhost:8001" "Core Node 1"
open_url "http://localhost:8002" "Core Node 2"
open_url "http://localhost:8003" "Core Node 3"

# Open Edge Nodes
echo -e "\n${BLUE}Opening Edge Nodes...${NC}"
open_url "http://localhost:8011" "Edge Node 1"
open_url "http://localhost:8012" "Edge Node 2"

# Open Monitoring UIs
echo -e "\n${BLUE}Opening Monitoring UIs...${NC}"
open_url "http://localhost:3001" "Grafana Dashboard (login: admin/admin)"
open_url "http://localhost:9090" "Prometheus Metrics"
open_url "http://localhost:8089" "Locust Load Testing"

echo -e "\n${GREEN}All available UIs have been opened in your browser!${NC}"
