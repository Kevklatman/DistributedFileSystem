# Development Environment

This directory contains all development-related files and tools for the Distributed File System project.

## Directory Structure

- `config/` - Development configuration files
  - `docker-compose.dev.yml` - Development container configuration
  - `haproxy.cfg` - Load balancer configuration

- `docs/` - Development documentation
  - `dfs-architecture.mermaid` - Architecture diagram

- `env/` - Environment configuration templates
  - `.env.example` - Example environment variables
  - `env.template` - Environment template
  - `.flaskenv` - Flask development settings

- `examples/` - Example code and usage scenarios
  - `custom_policy_example.py` - Custom policy implementation examples
  - `dashboard_example.py` - Dashboard setup examples
  - `distributed_metrics_example.py` - Distributed metrics usage
  - `policy_scenarios.py` - Policy testing scenarios
  - `s3_metrics_example.py` - S3 metrics integration
  - `simulation_example.py` - Simulation usage examples

- `scripts/` - Development and maintenance scripts
  - `cluster_config.yaml` - Cluster configuration for development
  - `node_management.py` - Node management utilities
  - `setup-credentials.py` - Credential setup script
  - `test_file_ops.py` - File operation testing utilities
  - `update_imports.py` - Import statement updater

- `simulation/` - Simulation environment for testing distributed scenarios
  - `data_store.py` - Simulated data store
  - `network_simulator.py` - Network condition simulator
  - `scenario_config.py` - Simulation scenario configurations
  - `scenario_simulator.py` - Scenario execution engine
  - `simulated_collector.py` - Metrics collection for simulations

- `tests/` - Test suites and testing utilities
  - `test-requirements.txt` - Testing dependencies
  - Unit tests, integration tests, and performance tests

## Development Container

The development environment is containerized for consistency and isolation. Use the following files:

- `Dockerfile.dev` - Development container configuration
- `run_tests.sh` - Script to run tests in a clean container environment

## Usage

1. Build the development container:
```bash
cd dev
docker build -t dfs-dev -f Dockerfile.dev ..
```

2. Start the development environment:
```bash
cd dev/config
docker-compose -f docker-compose.dev.yml up -d
```

3. Run tests in a clean environment:
```bash
cd dev
./run_tests.sh
```

4. Start an interactive development session:
```bash
docker run --rm -it \
    -v "$(pwd)/..:/app" \
    -v "dfs-dev-cache:/data" \
    --network host \
    dfs-dev
