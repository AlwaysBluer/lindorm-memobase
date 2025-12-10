#!/usr/bin/env python3
"""
Demo: Reset Storage Interface
Demonstrates how to use the reset_all_storage method to clear all storage tables.
"""

import asyncio
from lindormmemobase import LindormMemobase, Config


async def main():
    # Initialize LindormMemobase
    config = Config.from_yaml_file("config.yaml")
    memobase = LindormMemobase(config)
    
    print("=" * 60)
    print("Demo: Reset Storage Interface")
    print("=" * 60)
    
    # Example 1: Reset all data (drops and recreates tables)
    print("\n1. Reset ALL data (user_id=None, project_id=None)")
    print("   This will DROP all tables and recreate them from scratch")
    result = await memobase.reset_all_storage()
    print(f"   Result: {result}")
    print(f"   Tables recreated: {result['tables_recreated']}")
    
    # Example 2: Reset data for a specific user across all projects
    print("\n2. Reset data for specific user (user_id='user123', project_id=None)")
    print("   This will DELETE all records for user123 across all projects")
    result = await memobase.reset_all_storage(user_id="user123")
    print(f"   Result: {result}")
    print(f"   Buffer deleted: {result['buffer_deleted']} rows")
    print(f"   Events deleted: {result['events_deleted']} rows")
    print(f"   Gists deleted: {result['gists_deleted']} rows")
    print(f"   Profiles deleted: {result['profiles_deleted']} rows")
    
    # Example 3: Reset data for a specific user and project
    print("\n3. Reset data for specific user and project")
    print("   (user_id='user456', project_id='project_A')")
    print("   This will DELETE only records for user456 in project_A")
    result = await memobase.reset_all_storage(user_id="user456", project_id="project_A")
    print(f"   Result: {result}")
    print(f"   Buffer deleted: {result['buffer_deleted']} rows")
    print(f"   Events deleted: {result['events_deleted']} rows")
    print(f"   Gists deleted: {result['gists_deleted']} rows")
    print(f"   Profiles deleted: {result['profiles_deleted']} rows")
    
    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
