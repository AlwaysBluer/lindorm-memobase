#!/usr/bin/env python3
"""
Lindorm Search Tests Runner

This script runs all the search-related tests for the Lindorm MemoBase system.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest


def main():
    """Run all search tests."""
    test_files = [
        "tests/test_search_events.py",
        "tests/test_search_user_profiles.py", 
        "tests/test_search_context.py"
    ]
    
    # Check if test files exist
    missing_files = []
    for test_file in test_files:
        if not os.path.exists(test_file):
            missing_files.append(test_file)
    
    if missing_files:
        print(f"❌ Missing test files: {missing_files}")
        return 1
    
    # Run pytest with verbose output
    pytest_args = [
        "-v",                    # Verbose output
        "-s",                    # Don't capture output
        "--tb=short",            # Short traceback format
        "--disable-warnings",    # Disable warnings for cleaner output
        "-x",                   # Stop on first failure
    ] + test_files
    
    print("🧪 Running Lindorm Search Integration Tests...")
    print("=" * 60)
    
    # Run the tests
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0:
        print("\n" + "=" * 60)
        print("✅ All tests passed successfully!")
    else:
        print("\n" + "=" * 60)
        print("❌ Some tests failed. Check the output above for details.")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())