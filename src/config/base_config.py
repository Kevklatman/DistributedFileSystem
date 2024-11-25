"""
Configuration settings for the Distributed File System.
"""
import os

# API Server Configuration
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8081'))
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# Storage Configuration
STORAGE_ROOT = os.getenv('STORAGE_ROOT', '/data/dfs')
NODE_ID = os.getenv('NODE_ID', 'default-node')
CLOUD_PROVIDER_TYPE = os.getenv('CLOUD_PROVIDER_TYPE', 'local')

# Security Configuration
API_KEY = os.getenv('API_KEY', None)
SSL_CERT = os.getenv('SSL_CERT', None)
SSL_KEY = os.getenv('SSL_KEY', None)

# Performance Configuration
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '4'))
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1048576'))  # 1MB default
MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', '5368709120'))  # 5GB default

# Cache Configuration
CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'True').lower() == 'true'
CACHE_SIZE = int(os.getenv('CACHE_SIZE', '1073741824'))  # 1GB default
CACHE_TTL = int(os.getenv('CACHE_TTL', '3600'))  # 1 hour default

# Replication Configuration
REPLICATION_FACTOR = int(os.getenv('REPLICATION_FACTOR', '3'))
CONSISTENCY_LEVEL = os.getenv('CONSISTENCY_LEVEL', 'strong')
