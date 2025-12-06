"""
Connection diagnostic test for Lindorm Table and Search.

This test helps debug connection issues by:
1. Loading configuration from .env and config.yaml
2. Attempting connections with timeout
3. Printing detailed connection info if timeout occurs
"""

import pytest
import asyncio
import os
from datetime import datetime
from lindormmemobase.config import Config


@pytest.mark.integration
class TestConnectionDiagnostic:
    """Diagnostic tests for database connections."""
    
    def test_load_configuration(self):
        """Test if configuration can be loaded properly."""
        print("\n" + "="*80)
        print("STEP 1: Loading Configuration")
        print("="*80)
        
        # Try to find config.yaml
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        config_paths = [
            os.path.join(project_root, "config.yaml"),
            "config.yaml",
            os.path.join(os.getcwd(), "config.yaml")
        ]
        
        config_file_found = None
        for config_path in config_paths:
            if os.path.exists(config_path):
                config_file_found = config_path
                print(f"✓ Found config.yaml at: {config_path}")
                break
        
        if not config_file_found:
            print("✗ config.yaml not found in:")
            for path in config_paths:
                print(f"  - {path}")
        
        # Check .env file
        env_paths = [
            os.path.join(project_root, ".env"),
            ".env",
            os.path.join(os.getcwd(), ".env")
        ]
        
        env_file_found = None
        for env_path in env_paths:
            if os.path.exists(env_path):
                env_file_found = env_path
                print(f"✓ Found .env at: {env_path}")
                break
        
        if not env_file_found:
            print("✗ .env not found in:")
            for path in env_paths:
                print(f"  - {path}")
        
        # Try to load config
        try:
            if config_file_found:
                config = Config.from_yaml_file(config_file_found)
                print("\n✓ Successfully loaded configuration from config.yaml")
            else:
                config = Config(
                    llm_api_key=os.getenv("MEMOBASE_LLM_API_KEY", "test-key"),
                    test_skip_persist=True
                )
                print("\n⚠ Using default configuration (no config.yaml found)")
            
            self._print_config_summary(config)
            
        except Exception as e:
            print(f"\n✗ Error loading configuration: {str(e)}")
            raise
    
    @pytest.mark.asyncio
    async def test_table_connection(self, integration_config):
        """Test Lindorm Table connection with timeout."""
        print("\n" + "="*80)
        print("STEP 2: Testing Lindorm Table Connection")
        print("="*80)
        
        self._print_table_connection_info(integration_config)
        
        try:
            # Import here to avoid early initialization
            from lindormmemobase.core.storage.user_profiles import LindormTableStorage
            
            print("\nAttempting to connect to Lindorm Table...")
            print("⏱ Timeout: 10 seconds")
            
            # Create storage instance with timeout
            storage = LindormTableStorage(integration_config)
            
            # Try to initialize with timeout (synchronous method)
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, storage.initialize_tables),
                timeout=10.0
            )
            
            print("✓ Successfully connected to Lindorm Table!")
            print("✓ Tables initialized successfully")
            
            # Try a simple operation
            print("\nTesting basic operation...")
            result = await asyncio.wait_for(
                storage.get_user_profiles(
                    user_id="test_connection_check",
                    project_id="test_project"
                ),
                timeout=5.0
            )
            
            if result.ok():
                print("✓ Basic query operation successful")
            else:
                print(f"⚠ Query returned error: {result.msg()}")
            
        except asyncio.TimeoutError:
            print("\n" + "!"*80)
            print("✗ CONNECTION TIMEOUT!")
            print("!"*80)
            self._print_table_troubleshooting(integration_config)
            raise
            
        except Exception as e:
            print("\n" + "!"*80)
            print(f"✗ CONNECTION ERROR: {type(e).__name__}")
            print("!"*80)
            print(f"Error message: {str(e)}")
            self._print_table_troubleshooting(integration_config)
            raise
    
    @pytest.mark.asyncio
    async def test_search_connection(self, integration_config):
        """Test Lindorm Search connection with timeout."""
        print("\n" + "="*80)
        print("STEP 3: Testing Lindorm Search Connection")
        print("="*80)
        
        self._print_search_connection_info(integration_config)
        
        try:
            # Import here to avoid early initialization
            from lindormmemobase.core.storage.events import LindormSearchStorage
            
            print("\nAttempting to connect to Lindorm Search...")
            print("⏱ Timeout: 10 seconds")
            
            # Create storage instance
            storage = LindormSearchStorage(integration_config)
            
            # Try to initialize with timeout (synchronous method)
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, storage.initialize_indices),
                timeout=10.0
            )
            
            print("✓ Successfully connected to Lindorm Search!")
            print("✓ Indices initialized successfully")
            
        except asyncio.TimeoutError:
            print("\n" + "!"*80)
            print("✗ CONNECTION TIMEOUT!")
            print("!"*80)
            self._print_search_troubleshooting(integration_config)
            raise
            
        except Exception as e:
            print("\n" + "!"*80)
            print(f"✗ CONNECTION ERROR: {type(e).__name__}")
            print("!"*80)
            print(f"Error message: {str(e)}")
            self._print_search_troubleshooting(integration_config)
            raise
    
    def _print_config_summary(self, config):
        """Print configuration summary."""
        print("\nConfiguration Summary:")
        print(f"  Language: {config.language}")
        print(f"  LLM Style: {config.llm_style}")
        print(f"  Best LLM Model: {config.best_llm_model}")
        print(f"  Embedding Provider: {config.embedding_provider}")
        print(f"  Embedding Dimension: {config.embedding_dim}")
        print(f"  Test Skip Persist: {config.test_skip_persist}")
    
    def _print_table_connection_info(self, config):
        """Print Lindorm Table connection information."""
        print("\nLindorm Table Configuration:")
        print(f"  Host: {config.lindorm_table_host}")
        print(f"  Port: {config.lindorm_table_port}")
        print(f"  Database: {config.lindorm_table_database}")
        print(f"  Username: {config.lindorm_table_username}")
        print(f"  Password: {'*' * len(config.lindorm_table_password) if config.lindorm_table_password else '(empty)'}")
    
    def _print_search_connection_info(self, config):
        """Print Lindorm Search connection information."""
        print("\nLindorm Search Configuration:")
        print(f"  Host: {config.lindorm_search_host}")
        print(f"  Port: {config.lindorm_search_port}")
        print(f"  Username: {config.lindorm_search_username if hasattr(config, 'lindorm_search_username') else '(not set)'}")
        print(f"  Password: {'*' * len(config.lindorm_search_password) if hasattr(config, 'lindorm_search_password') and config.lindorm_search_password else '(empty)'}")
        print(f"  Use SSL: {config.lindorm_search_use_ssl if hasattr(config, 'lindorm_search_use_ssl') else False}")
        print(f"  Events Index: {config.lindorm_search_events_index if hasattr(config, 'lindorm_search_events_index') else '(not set)'}")
        print(f"  Event Gists Index: {config.lindorm_search_event_gists_index if hasattr(config, 'lindorm_search_event_gists_index') else '(not set)'}")
    
    def _print_table_troubleshooting(self, config):
        """Print troubleshooting information for table connection."""
        print("\nTroubleshooting Steps:")
        print("\n1. Verify Lindorm Table is accessible:")
        print(f"   Try connecting manually:")
        print(f"   mysql -h {config.lindorm_table_host} -P {config.lindorm_table_port} -u {config.lindorm_table_username} -p")
        
        print("\n2. Check network connectivity:")
        print(f"   ping {config.lindorm_table_host}")
        print(f"   telnet {config.lindorm_table_host} {config.lindorm_table_port}")
        
        print("\n3. Verify credentials in .env file:")
        print("   MEMOBASE_LINDORM_TABLE_HOST=...")
        print("   MEMOBASE_LINDORM_TABLE_PORT=...")
        print("   MEMOBASE_LINDORM_TABLE_USERNAME=...")
        print("   MEMOBASE_LINDORM_TABLE_PASSWORD=...")
        print("   MEMOBASE_LINDORM_TABLE_DATABASE=...")
        
        print("\n4. Check firewall/security group settings:")
        print("   - Port 33060 should be open for Lindorm Table")
        print("   - Your IP should be whitelisted")
        
        print("\n5. Verify Lindorm instance is running:")
        print("   - Check Alibaba Cloud console")
        print("   - Verify instance status is 'Running'")
    
    def _print_search_troubleshooting(self, config):
        """Print troubleshooting information for search connection."""
        print("\nTroubleshooting Steps:")
        print("\n1. Verify Lindorm Search is accessible:")
        print(f"   curl -XGET 'http://{config.lindorm_search_host}:{config.lindorm_search_port}/'")
        
        print("\n2. Check network connectivity:")
        print(f"   ping {config.lindorm_search_host}")
        print(f"   telnet {config.lindorm_search_host} {config.lindorm_search_port}")
        
        print("\n3. Verify credentials in .env file:")
        print("   MEMOBASE_LINDORM_SEARCH_HOST=...")
        print("   MEMOBASE_LINDORM_SEARCH_PORT=...")
        print("   MEMOBASE_LINDORM_SEARCH_USERNAME=...")
        print("   MEMOBASE_LINDORM_SEARCH_PASSWORD=...")
        
        print("\n4. Check firewall/security group settings:")
        print("   - Port 30070 should be open for Lindorm Search")
        print("   - Your IP should be whitelisted")
        
        print("\n5. Verify Lindorm Search is enabled:")
        print("   - Check if Search engine is enabled in Lindorm instance")
        print("   - Verify index names are correct")


@pytest.mark.integration
def test_print_environment_variables():
    """Print all MEMOBASE environment variables for debugging."""
    print("\n" + "="*80)
    print("Environment Variables (MEMOBASE_*)")
    print("="*80)
    
    memobase_vars = {k: v for k, v in os.environ.items() if k.startswith('MEMOBASE_')}
    
    if not memobase_vars:
        print("⚠ No MEMOBASE_* environment variables found!")
        print("\nMake sure you have created .env file from .env.example:")
        print("  cp .env.example .env")
        print("\nThen edit .env with your actual credentials.")
    else:
        print(f"\nFound {len(memobase_vars)} MEMOBASE environment variables:\n")
        
        # Sensitive keys to mask
        sensitive_keys = ['PASSWORD', 'API_KEY', 'USERNAME']
        
        for key in sorted(memobase_vars.keys()):
            value = memobase_vars[key]
            
            # Mask sensitive values
            if any(sensitive in key for sensitive in sensitive_keys):
                if value:
                    masked_value = value[:2] + '*' * (len(value) - 4) + value[-2:] if len(value) > 4 else '*' * len(value)
                else:
                    masked_value = '(empty)'
                print(f"  {key} = {masked_value}")
            else:
                print(f"  {key} = {value}")
