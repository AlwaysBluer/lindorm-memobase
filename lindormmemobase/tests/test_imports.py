#!/usr/bin/env python3
"""
Quick test to verify imports work correctly
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all search modules can be imported."""
    try:
        print("Testing search module imports...")
        
        # Test events module
        from lindormmemobase.core.search.events import get_user_event_gists
        print("✅ Events module imports OK")
        
        # Test user profiles module 
        from lindormmemobase.core.search.user_profiles import truncate_profiles
        print("✅ User profiles module imports OK")
        
        # Test context module
        from lindormmemobase.core.search.context import get_user_context
        print("✅ Context module imports OK")
        
        # Test storage modules
        from lindormmemobase.core.storage.events import store_event_with_embedding
        from lindormmemobase.core.storage.user_profiles import add_user_profiles
        print("✅ Storage modules import OK")
        
        # Test config
        from lindormmemobase.config import Config
        print("✅ Config imports OK")
        
        print("\n🎉 All imports successful!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)