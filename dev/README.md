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

```

## Testing Infrastructure

The distributed file system uses a comprehensive testing framework built on pytest. The testing infrastructure supports various test categories, parallel execution, benchmarking, and detailed reporting.

### Test Categories

- **Unit Tests**: Test individual components in isolation
  ```bash
  python tests/run_tests.py --unit
  ```

- **Integration Tests**: Test component interactions
  ```bash
  python tests/run_tests.py --integration
  ```

- **Performance Tests**: Benchmark and performance analysis
  ```bash
  python tests/run_tests.py --performance
  ```

### Common Test Commands

```bash
# Run all tests
python tests/run_tests.py --all

# Run tests with HTML report
python tests/run_tests.py --all --html

# Run performance benchmarks
python tests/run_tests.py --performance --benchmark-only

# Compare against previous benchmark
python tests/run_tests.py --performance --benchmark-compare

# Run tests in parallel
python tests/run_tests.py --all --workers auto

# Run specific test pattern
python tests/run_tests.py --all --filter "test_storage"

# Run tests with increased verbosity
python tests/run_tests.py --all --verbose
```

### Test Reports

Test results can be generated in multiple formats:

- **HTML Reports**: `--html` flag generates detailed HTML reports in `test-reports/`
- **JSON Reports**: `--json` flag generates machine-readable reports
- **Coverage Reports**: Automatically generated unless `--no-cov` is specified
- **Benchmark Reports**: Generated for performance tests in JSON format

### Test Configuration

The testing framework can be configured through:

1. **Command Line Arguments**:
   - `--verbose`: Increase output detail
   - `--workers N`: Run N parallel workers
   - `--filter PATTERN`: Run tests matching pattern
   - `--markers MARKER`: Run tests with specific markers
   - `--slow`: Include slow tests
   - `--output-dir DIR`: Specify report directory

2. **Environment Variables**:
   - `PYTHONPATH`: Automatically set to project root
   - `TEST_ENV`: Set to 'true' during test runs

3. **pytest.ini Configuration**:
   - Test discovery patterns
   - Logging settings
   - Timeout limits
   - Benchmark configurations

### Adding New Tests

1. **File Naming**:
   - Unit tests: `test_*_unit.py`
   - Integration tests: `test_*_integration.py`
   - Performance tests: `test_*_performance.py`

2. **Test Markers**:
   ```python
   @pytest.mark.unit
   def test_unit_feature():
       pass

   @pytest.mark.integration
   def test_integration_feature():
       pass

   @pytest.mark.performance
   def test_performance_feature():
       pass

   @pytest.mark.slow
   def test_slow_feature():
       pass
   ```

3. **Async Tests**:
   ```python
   @pytest.mark.asyncio
   async def test_async_feature():
       await async_operation()
   ```

4. **Performance Tests**:
   ```python
   def test_performance(benchmark):
       benchmark(performance_critical_function)
   ```

### Test Dependencies

Required packages are listed in `tests/requirements.txt`. Install using:
```bash
pip install -r tests/requirements.txt
```

### Test Output Directory Structure

```
test-reports/
├── coverage/          # Coverage reports
├── benchmark/         # Benchmark results
├── report.html       # HTML test report
├── report.json       # JSON test report
└── test_metadata.json # Test run metadata
```

### Best Practices

1. **Test Categories**:
   - Unit tests should be fast and isolated
   - Integration tests can involve multiple components
   - Performance tests should be benchmarked against baselines

2. **Test Organization**:
   - Group related tests in test classes
   - Use descriptive test names
   - Add appropriate markers for categorization

3. **Performance Testing**:
   - Use benchmark fixtures for consistent measurements
   - Compare results against previous runs
   - Document performance expectations

4. **Test Data**:
   - Use fixtures for test data setup
   - Clean up test data after tests
   - Use appropriate file sizes for performance tests

### Troubleshooting

1. **Common Issues**:
   - Test discovery issues: Check file naming
   - Import errors: Verify PYTHONPATH
   - Timeout errors: Adjust timeout in pytest.ini

2. **Debug Options**:
   - Use `--verbose` for detailed output
   - Enable logging with appropriate level
   - Use pytest's `-pdb` flag for debugging
