"""
Advanced DFS Dashboard Example demonstrating monitoring and management capabilities
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import json
from pathlib import Path

from src.api.storage.models import (
    Volume, StoragePool, StorageLocation, TierType,
    DataTemperature, HybridStorageSystem
)
from src.api.storage.policy_engine import PolicyMode
from src.api.storage.tiering_manager import TierCost

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SystemHealth:
    """System health metrics"""
    cpu_usage: float
    memory_usage: float
    io_latency_ms: float
    network_bandwidth_mbps: float
    error_count: int
    warning_count: int

@dataclass
class StorageMetrics:
    """Storage-related metrics"""
    total_capacity_gb: float
    used_capacity_gb: float
    dedup_ratio: float
    compression_ratio: float
    iops: int
    throughput_mbps: float

@dataclass
class CostMetrics:
    """Cost-related metrics"""
    total_cost_month: float
    savings_from_tiering: float
    savings_from_dedup: float
    savings_from_compression: float
    projected_cost_next_month: float
    cost_per_gb: Dict[TierType, float]

class DFSDashboard:
    """Advanced DFS Dashboard with monitoring and management capabilities"""
    
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.system = HybridStorageSystem(
            name="Production DFS",
            storage_pools={},
            volumes={}
        )
        
        # Initialize monitoring metrics
        self.health = SystemHealth(
            cpu_usage=0.0,
            memory_usage=0.0,
            io_latency_ms=0.0,
            network_bandwidth_mbps=0.0,
            error_count=0,
            warning_count=0
        )
        
        self.metrics = StorageMetrics(
            total_capacity_gb=0.0,
            used_capacity_gb=0.0,
            dedup_ratio=1.0,
            compression_ratio=1.0,
            iops=0,
            throughput_mbps=0.0
        )
        
        self.costs = CostMetrics(
            total_cost_month=0.0,
            savings_from_tiering=0.0,
            savings_from_dedup=0.0,
            savings_from_compression=0.0,
            projected_cost_next_month=0.0,
            cost_per_gb={
                TierType.PERFORMANCE: 0.15,
                TierType.CAPACITY: 0.05,
                TierType.COLD: 0.01,
                TierType.ARCHIVE: 0.004
            }
        )
        
    def show_system_overview(self):
        """Display system overview"""
        logger.info("\n=== System Overview ===")
        logger.info(f"System Name: {self.system.name}")
        logger.info(f"Total Pools: {len(self.system.storage_pools)}")
        logger.info(f"Total Volumes: {len(self.system.volumes)}")
        
        # Health status
        health_status = "🟢 Healthy" if self.health.error_count == 0 else "🔴 Issues Detected"
        logger.info(f"System Status: {health_status}")
        
        # Capacity overview
        usage_percent = (self.metrics.used_capacity_gb / self.metrics.total_capacity_gb * 100) \
            if self.metrics.total_capacity_gb > 0 else 0
        logger.info(f"Storage Usage: {usage_percent:.1f}% ({self.metrics.used_capacity_gb:.1f} GB / {self.metrics.total_capacity_gb:.1f} GB)")
        
    def show_health_metrics(self):
        """Display detailed health metrics"""
        logger.info("\n=== Health Metrics ===")
        logger.info(f"CPU Usage: {self.health.cpu_usage:.1f}%")
        logger.info(f"Memory Usage: {self.health.memory_usage:.1f}%")
        logger.info(f"I/O Latency: {self.health.io_latency_ms:.2f} ms")
        logger.info(f"Network Bandwidth: {self.health.network_bandwidth_mbps:.1f} Mbps")
        logger.info(f"Active Alerts: {self.health.error_count} errors, {self.health.warning_count} warnings")
        
    def show_performance_metrics(self):
        """Display performance metrics"""
        logger.info("\n=== Performance Metrics ===")
        logger.info(f"IOPS: {self.metrics.iops}")
        logger.info(f"Throughput: {self.metrics.throughput_mbps:.1f} MB/s")
        logger.info(f"Deduplication Ratio: {self.metrics.dedup_ratio:.2f}x")
        logger.info(f"Compression Ratio: {self.metrics.compression_ratio:.2f}x")
        
    def show_cost_analysis(self):
        """Display cost analysis"""
        logger.info("\n=== Cost Analysis ===")
        logger.info(f"Current Month Cost: ${self.costs.total_cost_month:.2f}")
        logger.info(f"Projected Next Month: ${self.costs.projected_cost_next_month:.2f}")
        logger.info("\nCost Savings:")
        logger.info(f"- From Tiering: ${self.costs.savings_from_tiering:.2f}")
        logger.info(f"- From Deduplication: ${self.costs.savings_from_dedup:.2f}")
        logger.info(f"- From Compression: ${self.costs.savings_from_compression:.2f}")
        total_savings = (self.costs.savings_from_tiering + 
                        self.costs.savings_from_dedup + 
                        self.costs.savings_from_compression)
        logger.info(f"Total Monthly Savings: ${total_savings:.2f}")
        
    def show_policy_status(self):
        """Display policy engine status"""
        logger.info("\n=== Policy Engine Status ===")
        
        # Count volumes by policy mode
        policy_modes = {
            PolicyMode.MANUAL: 0,
            PolicyMode.ML: 0,
            PolicyMode.HYBRID: 0,
            PolicyMode.SUPERVISED: 0
        }
        
        # Count data by tier
        tier_distribution = {
            TierType.PERFORMANCE: 0,
            TierType.CAPACITY: 0,
            TierType.COLD: 0,
            TierType.ARCHIVE: 0
        }
        
        # Analyze volumes
        for volume in self.system.volumes.values():
            # Increment policy mode counter
            if volume.cloud_tiering_enabled:
                policy_modes[PolicyMode.HYBRID] += 1
            else:
                policy_modes[PolicyMode.MANUAL] += 1
            
            # Add to tier distribution
            for temp in volume.data_temperature.values():
                tier_distribution[temp.current_tier] += 1
        
        # Display policy modes
        logger.info("Policy Mode Distribution:")
        for mode, count in policy_modes.items():
            logger.info(f"- {mode.value}: {count} volumes")
            
        # Display tier distribution
        logger.info("\nData Tier Distribution:")
        for tier, count in tier_distribution.items():
            logger.info(f"- {tier.value}: {count} objects")
            
    def show_recommendations(self):
        """Display system recommendations"""
        logger.info("\n=== System Recommendations ===")
        
        # Capacity recommendations
        usage_percent = (self.metrics.used_capacity_gb / self.metrics.total_capacity_gb * 100) \
            if self.metrics.total_capacity_gb > 0 else 0
        if usage_percent > 80:
            logger.info("⚠️ High storage usage detected:")
            logger.info("- Consider adding more capacity")
            logger.info("- Review data retention policies")
            logger.info("- Enable automatic tiering to cold storage")
            
        # Performance recommendations
        if self.health.io_latency_ms > 10:
            logger.info("\n⚠️ High I/O latency detected:")
            logger.info("- Check for hot spots in data access")
            logger.info("- Consider redistributing workload")
            logger.info("- Review storage pool configuration")
            
        # Cost optimization
        if self.costs.projected_cost_next_month > self.costs.total_cost_month * 1.2:
            logger.info("\n⚠️ Rising cost trajectory detected:")
            logger.info("- Review data placement policies")
            logger.info("- Enable cost-optimization features")
            logger.info("- Consider archiving cold data")
            
    def simulate_metrics(self):
        """Simulate some metrics for demonstration"""
        # System health
        self.health.cpu_usage = 45.5
        self.health.memory_usage = 62.3
        self.health.io_latency_ms = 12.5
        self.health.network_bandwidth_mbps = 850.0
        self.health.error_count = 2
        self.health.warning_count = 5
        
        # Storage metrics
        self.metrics.total_capacity_gb = 10000.0
        self.metrics.used_capacity_gb = 8500.0
        self.metrics.dedup_ratio = 2.3
        self.metrics.compression_ratio = 1.8
        self.metrics.iops = 15000
        self.metrics.throughput_mbps = 450.0
        
        # Cost metrics
        self.costs.total_cost_month = 1250.0
        self.costs.savings_from_tiering = 450.0
        self.costs.savings_from_dedup = 280.0
        self.costs.savings_from_compression = 180.0
        self.costs.projected_cost_next_month = 1500.0
        
        # Add some sample volumes
        pool = StoragePool(
            name="Pool-1",
            location=StorageLocation(type="on_prem", path="/data/pool1"),
            total_capacity_gb=10000,
            available_capacity_gb=1500
        )
        self.system.storage_pools[pool.id] = pool
        
        # Add volumes with different characteristics
        for i in range(5):
            volume = Volume(
                name=f"vol-{i}",
                size_gb=1000,
                primary_pool_id=pool.id,
                cloud_tiering_enabled=(i % 2 == 0)
            )
            self.system.volumes[volume.id] = volume
            
            # Add some temperature data
            volume.data_temperature["/data/hot"] = DataTemperature(
                access_frequency=100,
                days_since_last_access=0,
                size_bytes=1024**3 * 100,
                current_tier=TierType.PERFORMANCE
            )
            volume.data_temperature["/data/cold"] = DataTemperature(
                access_frequency=1,
                days_since_last_access=90,
                size_bytes=1024**3 * 900,
                current_tier=TierType.COLD
            )

def main():
    """Main function demonstrating dashboard capabilities"""
    dashboard = DFSDashboard(Path("/Users/kevinklatman/Development/Code/DistributedFileSystem"))
    
    # Simulate some metrics
    dashboard.simulate_metrics()
    
    # Show different dashboard views
    dashboard.show_system_overview()
    dashboard.show_health_metrics()
    dashboard.show_performance_metrics()
    dashboard.show_cost_analysis()
    dashboard.show_policy_status()
    dashboard.show_recommendations()

if __name__ == "__main__":
    main()
