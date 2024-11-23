#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Exit on any error
set -e

echo -e "${BLUE}Starting DFS Setup...${NC}"

# Function to run a step and check its success
run_step() {
    local step_name=$1
    local command=$2
    
    echo -e "\n${BLUE}Running $step_name...${NC}"
    if eval "$command"; then
        echo -e "${GREEN}✓ $step_name completed successfully${NC}"
        return 0
    else
        echo -e "${RED}✗ $step_name failed${NC}"
        return 1
    fi
}

# 1. Setup credentials
run_step "Python Credentials Setup" "python3 setup-credentials.py"

# 2. Setup cloud secrets in Kubernetes
run_step "Cloud Secrets Setup" "./setup-cloud-secrets.sh"

# 3. Load environment variables to Kubernetes
run_step "Environment Variables Setup" "./load-env-to-k8s.sh"

# 4. Test cloud provider connections
echo -e "\n${BLUE}Testing cloud provider connections...${NC}"
if python3 test-cloud-providers.py; then
    echo -e "${GREEN}✓ Cloud provider tests passed${NC}"
else
    echo -e "${RED}✗ Some cloud provider tests failed${NC}"
    echo -e "${BLUE}Continue anyway? (y/n)${NC}"
    read -r continue_setup
    if [[ $continue_setup != "y" ]]; then
        echo -e "${RED}Setup aborted${NC}"
        exit 1
    fi
fi

# 5. Deploy CSI driver
run_step "CSI Driver Deployment" "./deploy-csi.sh"

echo -e "\n${GREEN}DFS Setup completed!${NC}"
echo -e "${BLUE}You can now start the development environment with:${NC}"
echo -e "  ./start_dev.sh"
