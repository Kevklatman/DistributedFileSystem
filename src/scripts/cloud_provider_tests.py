#!/usr/bin/env python3
"""
Unified cloud provider testing module for DFS.
Tests connectivity and functionality for various cloud storage providers.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add src to Python path
src_path = str(Path(__file__).parent.parent)
sys.path.append(src_path)

from storage.cloud.azure_provider import AzureStorageProvider
from storage.cloud.gcp_provider import GCPStorageProvider
from storage.cloud.provider_factory import CloudProviderFactory
from storage.models.cloud_config import CloudProviderConfig

def setup_logging():
    """Configure logging with consistent format."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='DFS Cloud Provider Tests')
    parser.add_argument('--provider', choices=['azure', 'gcp', 'all'],
                       default='all', help='Cloud provider to test')
    parser.add_argument('--config', type=str,
                       help='Path to cloud provider configuration')
    parser.add_argument('--credentials', type=str,
                       help='Path to cloud credentials file')
    parser.add_argument('--container', type=str,
                       help='Container/bucket name for testing')
    return parser.parse_args()

async def test_azure_connection(config: Dict) -> bool:
    """Test Azure storage connection and basic operations."""
    logging.info("Testing Azure Storage connection...")
    
    try:
        provider = AzureStorageProvider(
            account_name=config['account_name'],
            account_key=config['account_key'],
            container_name=config['container']
        )
        
        # Test connection
        await provider.initialize()
        
        # Test basic operations
        test_data = b"DFS Azure Test Data"
        test_key = "test/azure_connection_test.txt"
        
        # Upload test
        await provider.upload(test_key, test_data)
        logging.info("✓ Upload test passed")
        
        # Download test
        downloaded = await provider.download(test_key)
        assert downloaded == test_data
        logging.info("✓ Download test passed")
        
        # List test
        files = await provider.list("test/")
        assert test_key in files
        logging.info("✓ List operation test passed")
        
        # Delete test
        await provider.delete(test_key)
        logging.info("✓ Delete operation test passed")
        
        logging.info("Azure Storage tests completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"Azure Storage test failed: {e}")
        return False

async def test_gcp_connection(config: Dict) -> bool:
    """Test Google Cloud Storage connection and basic operations."""
    logging.info("Testing Google Cloud Storage connection...")
    
    try:
        provider = GCPStorageProvider(
            project_id=config['project_id'],
            credentials_path=config['credentials_path'],
            bucket_name=config['bucket']
        )
        
        # Test connection
        await provider.initialize()
        
        # Test basic operations
        test_data = b"DFS GCP Test Data"
        test_key = "test/gcp_connection_test.txt"
        
        # Upload test
        await provider.upload(test_key, test_data)
        logging.info("✓ Upload test passed")
        
        # Download test
        downloaded = await provider.download(test_key)
        assert downloaded == test_data
        logging.info("✓ Download test passed")
        
        # List test
        files = await provider.list("test/")
        assert test_key in files
        logging.info("✓ List operation test passed")
        
        # Delete test
        await provider.delete(test_key)
        logging.info("✓ Delete operation test passed")
        
        logging.info("Google Cloud Storage tests completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"Google Cloud Storage test failed: {e}")
        return False

async def test_provider_factory(config: Dict) -> bool:
    """Test cloud provider factory with different providers."""
    logging.info("Testing cloud provider factory...")
    
    try:
        factory = CloudProviderFactory()
        
        # Test Azure provider creation
        if 'azure' in config:
            azure_config = CloudProviderConfig(
                provider_type='azure',
                **config['azure']
            )
            azure_provider = factory.create_provider(azure_config)
            await azure_provider.initialize()
            logging.info("✓ Azure provider factory test passed")
        
        # Test GCP provider creation
        if 'gcp' in config:
            gcp_config = CloudProviderConfig(
                provider_type='gcp',
                **config['gcp']
            )
            gcp_provider = factory.create_provider(gcp_config)
            await gcp_provider.initialize()
            logging.info("✓ GCP provider factory test passed")
        
        logging.info("Cloud provider factory tests completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"Cloud provider factory test failed: {e}")
        return False

def load_config(config_path: Optional[str] = None) -> Dict:
    """Load cloud provider configuration from file or environment."""
    config = {}
    
    if config_path and os.path.exists(config_path):
        with open(config_path) as f:
            config = json.load(f)
    else:
        # Load from environment variables
        if os.getenv('AZURE_STORAGE_ACCOUNT'):
            config['azure'] = {
                'account_name': os.getenv('AZURE_STORAGE_ACCOUNT'),
                'account_key': os.getenv('AZURE_STORAGE_KEY'),
                'container': os.getenv('AZURE_STORAGE_CONTAINER', 'dfs-test')
            }
        
        if os.getenv('GOOGLE_CLOUD_PROJECT'):
            config['gcp'] = {
                'project_id': os.getenv('GOOGLE_CLOUD_PROJECT'),
                'credentials_path': os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
                'bucket': os.getenv('GCP_STORAGE_BUCKET', 'dfs-test')
            }
    
    return config

async def run_tests(args):
    """Run cloud provider tests based on configuration."""
    config = load_config(args.config)
    
    if not config:
        logging.error("No cloud provider configuration found")
        sys.exit(1)
    
    results = []
    
    if args.provider in ['azure', 'all'] and 'azure' in config:
        results.append(('Azure', await test_azure_connection(config['azure'])))
    
    if args.provider in ['gcp', 'all'] and 'gcp' in config:
        results.append(('GCP', await test_gcp_connection(config['gcp'])))
    
    if args.provider == 'all':
        results.append(('Provider Factory', await test_provider_factory(config)))
    
    # Print summary
    print("\nTest Results:")
    print("-------------")
    for provider, success in results:
        status = "✓ Passed" if success else "✗ Failed"
        color = '\033[92m' if success else '\033[91m'
        print(f"{color}{provider}: {status}\033[0m")
    
    # Exit with status code
    if not all(success for _, success in results):
        sys.exit(1)

def main():
    """Main entry point for cloud provider tests."""
    setup_logging()
    args = parse_args()
    
    try:
        asyncio.run(run_tests(args))
    except KeyboardInterrupt:
        logging.info("Tests stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
