#!/usr/bin/env python3
"""Test runner for the distributed file system."""
import pytest
import sys
from pathlib import Path
import argparse
import os

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
TESTS_ROOT = PROJECT_ROOT / "src/tests"
sys.path.insert(0, str(PROJECT_ROOT))

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run distributed file system tests")
    parser.add_argument(
        "--unit", action="store_true",
        help="Run only unit tests"
    )
    parser.add_argument(
        "--integration", action="store_true",
        help="Run only integration tests"
    )
    parser.add_argument(
        "--performance", action="store_true",
        help="Run only performance tests"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Increase verbosity"
    )
    parser.add_argument(
        "-k", "--filter",
        help="Only run tests which match the given substring expression"
    )
    parser.add_argument(
        "--no-cov", action="store_true",
        help="Disable coverage reporting"
    )
    parser.add_argument(
        "-n", "--workers",
        type=int, default=0,
        help="Number of workers for parallel execution. Use 'auto' for automatic"
    )
    parser.add_argument(
        "--slow", action="store_true",
        help="Include slow tests"
    )
    return parser.parse_args()

def main():
    """Main entry point for test runner."""
    args = parse_args()
    
    # Set up pytest arguments
    pytest_args = [
        "--asyncio-mode=auto",  # Enable async test support
        "-W", "ignore::DeprecationWarning"  # Ignore deprecation warnings
    ]
    
    # Add test directories based on arguments
    if args.unit:
        pytest_args.append(str(TESTS_ROOT / "unit"))
    elif args.integration:
        pytest_args.append(str(TESTS_ROOT / "integration"))
    elif args.performance:
        pytest_args.append(str(TESTS_ROOT / "performance"))
    else:
        # Run all tests by default
        pytest_args.append(str(TESTS_ROOT))
    
    # Add verbosity
    if args.verbose:
        pytest_args.append("-v")
        pytest_args.append("--log-cli-level=INFO")
    
    # Add test filter if specified
    if args.filter:
        pytest_args.extend(["-k", args.filter])
    
    # Add coverage reporting unless disabled
    if not args.no_cov:
        pytest_args.extend([
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=html:coverage_report"
        ])
    
    # Configure parallel execution
    if args.workers:
        pytest_args.extend(["-n", str(args.workers)])
    
    # Skip slow tests unless explicitly included
    if not args.slow:
        pytest_args.append("-m not slow")
    
    # Always show test summary
    pytest_args.append("-ra")
    
    # Run pytest with configured arguments
    sys.exit(pytest.main(pytest_args))

if __name__ == "__main__":
    main()
