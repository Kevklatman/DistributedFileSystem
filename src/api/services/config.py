import os
from dotenv import load_dotenv
from typing import Dict, Optional
from dataclasses import asdict
from datetime import datetime

from ..models.system import SystemConfig, SystemStatus, SystemHealth
from ..models.storage import StorageNodeStatus

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Environment can be 'local' or 'aws'
STORAGE_ENV = os.getenv('STORAGE_ENV', 'local')

# API Configuration
API_HOST = os.getenv('API_HOST', '0.0.0.0')  # Change to 0.0.0.0 to allow external connections
API_PORT = int(os.getenv('API_PORT', 8001))  # Change default port to 8001
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# Storage Configuration
STORAGE_ROOT = os.getenv('STORAGE_ROOT', os.path.join(os.getcwd(), 'data'))
if not os.path.exists(STORAGE_ROOT):
    os.makedirs(STORAGE_ROOT, exist_ok=True)

# AWS Configuration
AWS_CONFIG = {
    'access_key': os.environ.get('AWS_ACCESS_KEY'),
    'secret_key': os.environ.get('AWS_SECRET_KEY'),
    'session_token': os.environ.get('AWS_SESSION_TOKEN'),  # Added STS session token
    'region': os.environ.get('AWS_REGION', 'us-east-2'),  # Updated default region
    'endpoint': os.environ.get('AWS_ENDPOINT_URL', None)
}

# Storage configuration
STORAGE_CONFIG = {
    'local': {
        'storage_dir': os.getenv('LOCAL_STORAGE_DIR', './storage')
    },
    'aws': AWS_CONFIG
}

# Get current storage configuration and merge with base config
storage_specific_config = STORAGE_CONFIG.get(STORAGE_ENV, STORAGE_CONFIG['local'])
current_config = {
    'api_host': API_HOST,
    'api_port': API_PORT,
    'debug': DEBUG,
    'storage_root': STORAGE_ROOT,
    'storage_env': STORAGE_ENV,
    **storage_specific_config
}

class ConfigurationService:
    """Service for managing system configuration and health monitoring"""
    
    def __init__(self):
        self.config = SystemConfig(
            replication_factor=int(os.getenv('REPLICATION_FACTOR', '3')),
            min_nodes_required=int(os.getenv('MIN_NODES_REQUIRED', '1')),
            max_volume_size=int(os.getenv('MAX_VOLUME_SIZE', str(1024 * 1024 * 1024 * 1024))),  # 1TB
            heartbeat_interval=int(os.getenv('HEARTBEAT_INTERVAL', '30')),
            metrics_interval=int(os.getenv('METRICS_INTERVAL', '60')),
        )
        self._health = SystemHealth(
            status=SystemStatus.HEALTHY,
            message="System initialized",
            last_check=datetime.utcnow(),
            warnings=[],
            errors=[],
            node_statuses={}
        )

    def get_config(self) -> Dict:
        """Get current system configuration"""
        return asdict(self.config)

    def update_config(self, updates: Dict) -> SystemConfig:
        """Update system configuration"""
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        return self.config

    def get_health(self) -> SystemHealth:
        """Get current system health status"""
        return self._health

    def update_node_status(self, node_id: str, status: StorageNodeStatus):
        """Update status for a specific node"""
        self._health.node_statuses[node_id] = status.value
        self._update_system_status()

    def _update_system_status(self):
        """Update overall system status based on node statuses"""
        total_nodes = len(self._health.node_statuses)
        if not total_nodes:
            self._health.status = SystemStatus.ERROR
            self._health.message = "No nodes registered"
            return

        healthy_nodes = sum(1 for status in self._health.node_statuses.values() 
                          if status == StorageNodeStatus.ONLINE.value)
        
        if healthy_nodes == total_nodes:
            self._health.status = SystemStatus.HEALTHY
            self._health.message = "All nodes are healthy"
        elif healthy_nodes >= self.config.min_nodes_required:
            self._health.status = SystemStatus.DEGRADED
            self._health.message = f"{healthy_nodes}/{total_nodes} nodes are healthy"
        else:
            self._health.status = SystemStatus.ERROR
            self._health.message = f"Insufficient healthy nodes ({healthy_nodes}/{total_nodes})"

        self._health.last_check = datetime.utcnow()
