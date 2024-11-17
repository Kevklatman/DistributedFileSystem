#!/usr/bin/env python3
"""Test runner for the distributed file system."""
import unittest
import sys
import os

def run_tests():
    """Run all test cases."""
    # Get the directory containing this script
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests')
    
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.discover(test_dir)
    
    # Run the test suite
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return 0 if tests passed, 1 if any failed
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(run_tests())
