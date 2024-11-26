#!/usr/bin/env python3
"""Test runner for the distributed file system."""
import pytest
import sys
from pathlib import Path
import argparse
import os
import json
import logging
from datetime import datetime

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
TESTS_ROOT = PROJECT_ROOT / "dev/tests"
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run distributed file system tests")

    # Test categories
    test_group = parser.add_argument_group("Test Categories")
    test_group.add_argument("--unit", action="store_true", help="Run only unit tests")
    test_group.add_argument(
        "--integration", action="store_true", help="Run only integration tests"
    )
    test_group.add_argument(
        "--performance", action="store_true", help="Run only performance tests"
    )
    test_group.add_argument("--all", action="store_true", help="Run all tests")

    # Test filtering and execution
    filter_group = parser.add_argument_group("Test Filtering")
    filter_group.add_argument(
        "-k",
        "--filter",
        help="Only run tests which match the given substring expression",
    )
    filter_group.add_argument(
        "--markers", help="Only run tests with specific pytest markers"
    )
    filter_group.add_argument("--slow", action="store_true", help="Include slow tests")

    # Execution options
    exec_group = parser.add_argument_group("Execution Options")
    exec_group.add_argument(
        "-v", "--verbose", action="store_true", help="Increase verbosity"
    )
    exec_group.add_argument(
        "-n",
        "--workers",
        type=int,
        default=0,
        help="Number of workers for parallel execution. Use 'auto' for automatic",
    )
    exec_group.add_argument(
        "--no-cov", action="store_true", help="Disable coverage reporting"
    )

    # Performance testing options
    perf_group = parser.add_argument_group("Performance Options")
    perf_group.add_argument(
        "--benchmark-only", action="store_true", help="Run only benchmark tests"
    )
    perf_group.add_argument(
        "--benchmark-compare", help="Compare benchmarks against previous results"
    )
    perf_group.add_argument(
        "--benchmark-autosave",
        action="store_true",
        help="Automatically save benchmark results",
    )

    # Reporting options
    report_group = parser.add_argument_group("Reporting Options")
    report_group.add_argument(
        "--html", action="store_true", help="Generate HTML test report"
    )
    report_group.add_argument(
        "--json", action="store_true", help="Generate JSON test report"
    )
    report_group.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "test-reports"),
        help="Directory for test reports",
    )

    return parser.parse_args()


def get_pytest_args(args):
    """Convert parsed arguments to pytest arguments."""
    pytest_args = []

    # Verbosity
    if args.verbose:
        pytest_args.append("-v")

    # Test selection
    if args.unit:
        pytest_args.extend(["-m", "unit"])
    if args.integration:
        pytest_args.extend(["-m", "integration"])
    if args.performance:
        pytest_args.extend(["-m", "performance"])
    if args.filter:
        pytest_args.extend(["-k", args.filter])
    if args.markers:
        pytest_args.extend(["-m", args.markers])

    # Coverage
    if not args.no_cov:
        pytest_args.extend(
            [
                "--cov=src",
                "--cov-report=term-missing",
                "--cov-report=html:test-reports/coverage",
            ]
        )

    # Parallel execution
    if args.workers:
        pytest_args.extend(["-n", str(args.workers)])

    # Benchmark options
    if args.benchmark_only:
        pytest_args.append("--benchmark-only")
    if args.benchmark_compare:
        pytest_args.extend(["--benchmark-compare", args.benchmark_compare])
    if args.benchmark_autosave:
        pytest_args.append("--benchmark-autosave")

    # Reporting
    if args.html:
        pytest_args.append(f"--html={args.output_dir}/report.html")
    if args.json:
        pytest_args.append(f"--json={args.output_dir}/report.json")

    return pytest_args


def setup_test_environment():
    """Set up the test environment."""
    # Create output directory
    reports_dir = PROJECT_ROOT / "test-reports"
    reports_dir.mkdir(exist_ok=True)

    # Set up environment variables
    os.environ["PYTHONPATH"] = str(PROJECT_ROOT)
    os.environ["TEST_ENV"] = "true"

    return reports_dir


def save_test_metadata(reports_dir: Path, args):
    """Save test run metadata."""
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "args": vars(args),
        "python_version": sys.version,
        "platform": sys.platform,
    }

    with open(reports_dir / "test_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)


def main():
    """Main entry point for test runner."""
    args = parse_args()
    reports_dir = setup_test_environment()

    # Convert args to pytest arguments
    pytest_args = get_pytest_args(args)

    # Add test directories based on selected categories
    test_dirs = []
    if args.unit or args.all:
        test_dirs.append(str(TESTS_ROOT / "unit"))
    if args.integration or args.all:
        test_dirs.append(str(TESTS_ROOT / "integration"))
    if args.performance or args.all:
        test_dirs.append(str(TESTS_ROOT / "performance"))

    if not test_dirs:  # If no specific category selected, run all tests
        test_dirs = [str(TESTS_ROOT)]

    # Add test directories to pytest args
    pytest_args.extend(test_dirs)

    # Log test configuration
    logger.info("Starting test run with configuration:")
    logger.info(f"Test directories: {test_dirs}")
    logger.info(f"Pytest arguments: {pytest_args}")

    # Save test metadata
    save_test_metadata(reports_dir, args)

    # Run tests
    try:
        result = pytest.main(pytest_args)
        sys.exit(result)
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
