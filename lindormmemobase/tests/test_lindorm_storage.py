#!/usr/bin/env python3
"""
Lindorm Storage Integration Test Suite

This script runs comprehensive tests for both LindormSearch and LindormTable 
storage implementations using real connections from .env configuration.

Usage:
    python test_lindorm_storage.py              # Run all tests
    python test_lindorm_storage.py --search     # Run only search tests
    python test_lindorm_storage.py --table      # Run only table tests
    python test_lindorm_storage.py --verbose    # Run with verbose output
"""

import sys
import argparse
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lindormmemobase.config import Config
from tests.test_lindorm_search import TestLindormSearchStorage
from tests.test_lindorm_table import TestLindormTableStorage


class Colors:
    """ANSI color codes for terminal output."""
    BLUE = "\033[94m"
    GREEN = "\033[92m" 
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_banner(text: str):
    """Print a colored banner."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


async def test_configuration():
    """Test basic configuration and connectivity."""
    print_banner("Configuration & Connectivity Tests")
    
    try:
        config = Config.load_config()
        print_success("Configuration loaded successfully")
        
        # Print configuration summary (without sensitive data)
        print(f"📋 Configuration Summary:")
        print(f"   - Language: {config.language}")
        print(f"   - LLM Model: {config.best_llm_model}")
        print(f"   - Embedding Model: {config.embedding_model}")
        print(f"   - Embedding Dimension: {config.embedding_dim}")
        print(f"   - OpenSearch Host: {config.lindorm_search_host}:{config.lindorm_search_port}")
        print(f"   - MySQL Host: {config.lindorm_table_host}:{config.lindorm_table_port}")
        print(f"   - MySQL Database: {config.lindorm_table_database}")
        
        return config
    except Exception as e:
        print_error(f"Configuration failed: {e}")
        return None


async def run_search_tests(verbose: bool = False):
    """Run LindormSearch storage tests."""
    print_banner("LindormSearch Storage Tests")
    
    try:
        test_class = TestLindormSearchStorage()
        test_class.setup_class()
        
        tests = [
            ("Connection Test", test_class.test_connection),
            ("Indices Creation", test_class.test_indices_creation),
            ("Store Event with Embedding", test_class.test_store_event_with_embedding),
            ("Store Event Gist", test_class.test_store_event_gist_with_embedding),
            ("Hybrid Search Events", test_class.test_hybrid_search_events),
            ("Hybrid Search Gists", test_class.test_hybrid_search_gist_events),
            ("Error Handling", test_class.test_error_handling),
            ("Store without Embedding", test_class.test_store_event_without_embedding),
        ]
        
        results = {"passed": 0, "failed": 0, "errors": []}
        
        for test_name, test_func in tests:
            try:
                if verbose:
                    print(f"\n🔍 Running: {test_name}")
                
                if asyncio.iscoroutinefunction(test_func):
                    await test_func()
                else:
                    test_func()
                
                print_success(f"{test_name}")
                results["passed"] += 1
                
            except Exception as e:
                print_error(f"{test_name}: {str(e)}")
                results["failed"] += 1
                results["errors"].append((test_name, str(e)))
        
        # Cleanup
        test_class.teardown_class()
        
        print(f"\n📊 LindormSearch Results: {results['passed']} passed, {results['failed']} failed")
        return results
        
    except Exception as e:
        print_error(f"LindormSearch test setup failed: {e}")
        return {"passed": 0, "failed": 1, "errors": [("Setup", str(e))]}


async def run_table_tests(verbose: bool = False):
    """Run LindormTable storage tests.""" 
    print_banner("LindormTable Storage Tests")
    
    try:
        test_class = TestLindormTableStorage()
        test_class.setup_class()
        
        tests = [
            ("Connection Test", test_class.test_connection),
            ("Table Creation", test_class.test_table_creation),
            ("Add Profiles", test_class.test_add_profiles),
            ("Get User Profiles", test_class.test_get_user_profiles),
            ("Update Profiles", test_class.test_update_profiles),
            ("Delete Profiles", test_class.test_delete_profiles),
            ("Concurrent Operations", test_class.test_concurrent_operations),
            ("Large Content Handling", test_class.test_large_content_handling),
            ("JSON Attributes", test_class.test_json_attributes_handling),
            ("Error Handling", test_class.test_error_handling),
        ]
        
        results = {"passed": 0, "failed": 0, "errors": []}
        
        for test_name, test_func in tests:
            try:
                if verbose:
                    print(f"\n🔍 Running: {test_name}")
                
                if asyncio.iscoroutinefunction(test_func):
                    await test_func()
                else:
                    test_func()
                
                print_success(f"{test_name}")
                results["passed"] += 1
                
            except Exception as e:
                print_error(f"{test_name}: {str(e)}")
                results["failed"] += 1
                results["errors"].append((test_name, str(e)))
        
        # Cleanup
        test_class.teardown_class()
        
        print(f"\n📊 LindormTable Results: {results['passed']} passed, {results['failed']} failed")
        return results
        
    except Exception as e:
        print_error(f"LindormTable test setup failed: {e}")
        return {"passed": 0, "failed": 1, "errors": [("Setup", str(e))]}


async def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Lindorm Storage Integration Tests")
    parser.add_argument("--search", action="store_true", help="Run only search tests")
    parser.add_argument("--table", action="store_true", help="Run only table tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    print_banner("🚀 Lindorm Storage Integration Test Suite")
    
    # Test configuration first
    config = await test_configuration()
    if not config:
        print_error("Configuration test failed. Exiting.")
        return 1
    
    total_results = {"passed": 0, "failed": 0, "errors": []}
    
    # Run tests based on arguments
    if args.search or (not args.search and not args.table):
        search_results = await run_search_tests(args.verbose)
        total_results["passed"] += search_results["passed"]
        total_results["failed"] += search_results["failed"]
        total_results["errors"].extend(search_results["errors"])
    
    if args.table or (not args.search and not args.table):
        table_results = await run_table_tests(args.verbose)
        total_results["passed"] += table_results["passed"]
        total_results["failed"] += table_results["failed"]
        total_results["errors"].extend(table_results["errors"])
    
    # Print final summary
    print_banner("📋 Final Test Summary")
    print(f"{Colors.BOLD}Total Results:{Colors.END}")
    print(f"  ✅ Passed: {total_results['passed']}")
    print(f"  ❌ Failed: {total_results['failed']}")
    
    if total_results["errors"]:
        print(f"\n{Colors.BOLD}Errors:{Colors.END}")
        for test_name, error in total_results["errors"]:
            print(f"  ❌ {test_name}: {error}")
    
    if total_results["failed"] == 0:
        print_success("All tests passed! 🎉")
        return 0
    else:
        print_error(f"{total_results['failed']} tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)