"""Hybrid cloud management implementation."""
from typing import Dict, List, Optional, Union, BinaryIO
from enum import Enum
import logging
from datetime import datetime
from .providers import CloudStorageProvider, AWSS3Provider, AzureBlobProvider, GCPStorageProvider
from .config import TransferConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProviderPriority(Enum):
    """Priority levels for providers."""
    PRIMARY = 1
    SECONDARY = 2
    FALLBACK = 3

class ProviderHealth(Enum):
    """Health status of providers."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class RoutingStrategy(Enum):
    """Strategies for routing requests."""
    COST_OPTIMIZED = "cost_optimized"
    LATENCY_OPTIMIZED = "latency_optimized"
    AVAILABILITY_OPTIMIZED = "availability_optimized"
    BALANCED = "balanced"

class ProviderMetrics:
    """Tracks performance and health metrics for a provider."""
    
    def __init__(self):
        self.latency_ms: List[int] = []
        self.error_count: int = 0
        self.success_count: int = 0
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None
        self.health_status: ProviderHealth = ProviderHealth.HEALTHY
        self.cost_per_gb: float = 0.0
        
    def update_latency(self, latency_ms: int):
        """Update latency metrics."""
        self.latency_ms.append(latency_ms)
        if len(self.latency_ms) > 100:
            self.latency_ms.pop(0)
    
    def record_error(self, error: str):
        """Record an error occurrence."""
        self.error_count += 1
        self.last_error = error
        self.last_error_time = datetime.now()
        self._update_health()
    
    def record_success(self):
        """Record a successful operation."""
        self.success_count += 1
        self._update_health()
    
    def _update_health(self):
        """Update health status based on metrics."""
        if self.error_count == 0:
            self.health_status = ProviderHealth.HEALTHY
        elif self.error_count / (self.success_count + self.error_count) < 0.1:
            self.health_status = ProviderHealth.DEGRADED
        else:
            self.health_status = ProviderHealth.UNHEALTHY

class HybridCloudManager:
    """Manages multiple cloud providers in a hybrid cloud setup."""
    
    def __init__(self, routing_strategy: RoutingStrategy = RoutingStrategy.BALANCED):
        self.providers: Dict[str, CloudStorageProvider] = {}
        self.priorities: Dict[str, ProviderPriority] = {}
        self.metrics: Dict[str, ProviderMetrics] = {}
        self.routing_strategy = routing_strategy
        self.replication_enabled = False
        
    def add_provider(self, name: str, provider: CloudStorageProvider, 
                    priority: ProviderPriority, cost_per_gb: float):
        """Add a cloud provider to the hybrid setup."""
        self.providers[name] = provider
        self.priorities[name] = priority
        self.metrics[name] = ProviderMetrics()
        self.metrics[name].cost_per_gb = cost_per_gb
        
    def enable_replication(self, enabled: bool = True):
        """Enable or disable data replication across providers."""
        self.replication_enabled = enabled
    
    def _select_provider(self, operation: str) -> str:
        """Select the best provider based on routing strategy."""
        if self.routing_strategy == RoutingStrategy.COST_OPTIMIZED:
            return min(self.metrics.items(), key=lambda x: x[1].cost_per_gb)[0]
        
        elif self.routing_strategy == RoutingStrategy.LATENCY_OPTIMIZED:
            return min(
                self.metrics.items(),
                key=lambda x: sum(x[1].latency_ms) / len(x[1].latency_ms) 
                if x[1].latency_ms else float('inf')
            )[0]
        
        elif self.routing_strategy == RoutingStrategy.AVAILABILITY_OPTIMIZED:
            return min(
                self.metrics.items(),
                key=lambda x: (
                    x[1].health_status.value,
                    x[1].error_count,
                    self.priorities[x[0]].value
                )
            )[0]
        
        else:  # BALANCED
            # Consider all factors with weights
            def score(item):
                name, metrics = item
                latency_score = sum(metrics.latency_ms) / len(metrics.latency_ms) if metrics.latency_ms else 1000
                health_score = len(ProviderHealth) - metrics.health_status.value
                priority_score = self.priorities[name].value
                cost_score = metrics.cost_per_gb
                
                return (
                    0.3 * (latency_score / 100) +
                    0.3 * health_score +
                    0.2 * priority_score +
                    0.2 * (cost_score / 0.1)
                )
            
            return min(self.metrics.items(), key=score)[0]
    
    def upload_file(self, file_data: Union[bytes, BinaryIO], object_key: str, 
                   bucket: str, **kwargs) -> bool:
        """Upload a file using the best available provider."""
        primary_provider = self._select_provider("upload")
        
        try:
            # Attempt primary upload
            start_time = datetime.now()
            success = self.providers[primary_provider].upload_file(
                file_data, object_key, bucket, **kwargs
            )
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            if success:
                self.metrics[primary_provider].record_success()
                self.metrics[primary_provider].update_latency(int(latency))
                
                # Handle replication if enabled
                if self.replication_enabled:
                    for name, provider in self.providers.items():
                        if name != primary_provider:
                            try:
                                provider.upload_file(file_data, object_key, bucket, **kwargs)
                            except Exception as e:
                                logger.error(f"Replication failed to {name}: {str(e)}")
                
                return True
            
            # Try fallback providers if primary fails
            for name, provider in self.providers.items():
                if name != primary_provider:
                    try:
                        if provider.upload_file(file_data, object_key, bucket, **kwargs):
                            self.metrics[name].record_success()
                            return True
                    except Exception as e:
                        self.metrics[name].record_error(str(e))
            
            return False
            
        except Exception as e:
            self.metrics[primary_provider].record_error(str(e))
            logger.error(f"Upload failed on {primary_provider}: {str(e)}")
            return False
    
    def download_file(self, object_key: str, bucket: str) -> Optional[bytes]:
        """Download a file using the best available provider."""
        primary_provider = self._select_provider("download")
        
        try:
            # Attempt primary download
            start_time = datetime.now()
            data = self.providers[primary_provider].download_file(object_key, bucket)
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            if data:
                self.metrics[primary_provider].record_success()
                self.metrics[primary_provider].update_latency(int(latency))
                return data
            
            # Try fallback providers if primary fails
            for name, provider in self.providers.items():
                if name != primary_provider:
                    try:
                        if data := provider.download_file(object_key, bucket):
                            self.metrics[name].record_success()
                            return data
                    except Exception as e:
                        self.metrics[name].record_error(str(e))
            
            return None
            
        except Exception as e:
            self.metrics[primary_provider].record_error(str(e))
            logger.error(f"Download failed on {primary_provider}: {str(e)}")
            return None
    
    def get_provider_health(self) -> Dict[str, Dict]:
        """Get health metrics for all providers."""
        return {
            name: {
                "health": metrics.health_status.value,
                "error_count": metrics.error_count,
                "success_count": metrics.success_count,
                "last_error": metrics.last_error,
                "last_error_time": metrics.last_error_time,
                "avg_latency": sum(metrics.latency_ms) / len(metrics.latency_ms) 
                if metrics.latency_ms else None,
                "cost_per_gb": metrics.cost_per_gb
            }
            for name, metrics in self.metrics.items()
        }
    
    def get_replication_status(self, object_key: str, bucket: str) -> Dict[str, bool]:
        """Check if an object is replicated across all providers."""
        status = {}
        for name, provider in self.providers.items():
            try:
                exists = provider.download_file(object_key, bucket) is not None
                status[name] = exists
            except Exception:
                status[name] = False
        return status
