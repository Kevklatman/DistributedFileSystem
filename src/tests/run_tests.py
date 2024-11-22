#!/usr/bin/env python3
"""Test runner for the distributed file system."""
import unittest
from pathlib import Path
import sys

def run_tests():
    """Run all test cases."""
    # Get the directory containing this script
    test_dir = Path(__file__).parent / 'tests'

    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.discover(str(test_dir))

    # Run the test suite
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return 0 if tests passed, 1 if any failed
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests())
