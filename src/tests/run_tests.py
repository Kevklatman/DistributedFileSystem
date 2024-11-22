#!/usr/bin/env python3
"""Test runner for the distributed file system."""
import pytest
import sys
from pathlib import Path
import argparse
import os

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
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
        "-v", "--verbose", action="store_true",
        help="Increase verbosity"
    )
    parser.add_argument(
        "-k", "--filter",
        help="Only run tests which match the given substring expression"
    )
    return parser.parse_args()

def main():
    """Main entry point for test runner."""
    args = parse_args()
    
    # Set up pytest arguments
    pytest_args = []
    
    # Add test directories based on arguments
    if args.unit:
        pytest_args.append(str(PROJECT_ROOT / "src/tests/unit"))
    elif args.integration:
        pytest_args.append(str(PROJECT_ROOT / "src/tests/integration"))
    else:
        # Run all tests by default
        pytest_args.append(str(PROJECT_ROOT / "src/tests"))
    
    # Add verbosity
    if args.verbose:
        pytest_args.append("-v")
        pytest_args.append("-s")  # Show print statements
    
    # Add test filter if specified
    if args.filter:
        pytest_args.extend(["-k", args.filter])
    
    # Always show test summary
    pytest_args.append("-ra")
    
    # Run tests with pytest
    exit_code = pytest.main(pytest_args)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
