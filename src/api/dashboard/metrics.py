"""
Dashboard metrics and monitoring endpoints
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.storage.models import (
    Volume, StoragePool, StorageLocation, TierType,
    DataTemperature, HybridStorageSystem
)
from src.api.storage.policy_engine import PolicyMode
from src.api.storage.tiering_manager import TierCost

logger = logging.getLogger(__name__)
router = APIRouter()

class SystemHealthMetrics(BaseModel):
    """System health metrics"""
    cpu_usage: float
    memory_usage: float
    io_latency_ms: float
    network_bandwidth_mbps: float
    error_count: int
    warning_count: int
    status: str
    last_updated: datetime

class StorageMetrics(BaseModel):
    """Storage-related metrics"""
    total_capacity_gb: float
    used_capacity_gb: float
    available_capacity_gb: float
    usage_percent: float
    dedup_ratio: float
    compression_ratio: float
    iops: int
    throughput_mbps: float
    last_updated: datetime

class CostMetrics(BaseModel):
    """Cost-related metrics"""
    total_cost_month: float
    savings_from_tiering: float
    savings_from_dedup: float
    savings_from_compression: float
    total_savings: float
    projected_cost_next_month: float
    cost_trend_percent: float
    cost_per_gb: Dict[str, float]
    last_updated: datetime

class PolicyMetrics(BaseModel):
    """Policy engine metrics"""
    policy_distribution: Dict[str, int]
    tier_distribution: Dict[str, int]
    ml_policy_accuracy: float
    policy_changes_24h: int
    data_moved_24h_gb: float
    last_updated: datetime

class SystemRecommendation(BaseModel):
    """System recommendation"""
    category: str
    severity: str
    title: str
    description: str
    suggestions: List[str]
    created_at: datetime

class DashboardMetrics(BaseModel):
    """Complete dashboard metrics"""
    health: SystemHealthMetrics
    storage: StorageMetrics
    cost: CostMetrics
    policy: PolicyMetrics
    recommendations: List[SystemRecommendation]

class MetricsManager:
    """Manager for collecting and computing system metrics"""
    
    def __init__(self, system: HybridStorageSystem):
        self.system = system
        self.last_metrics: Optional[DashboardMetrics] = None
        
    def get_health_metrics(self) -> SystemHealthMetrics:
        """Collect system health metrics"""
        # In production, these would come from real system monitoring
        cpu_usage = 45.5
        memory_usage = 62.3
        io_latency = 12.5
        network_bandwidth = 850.0
        error_count = len([v for v in self.system.volumes.values() if v.status == "error"])
        warning_count = len([v for v in self.system.volumes.values() if v.status == "warning"])
        
        status = "healthy"
        if error_count > 0:
            status = "error"
        elif warning_count > 0:
            status = "warning"
            
        return SystemHealthMetrics(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            io_latency_ms=io_latency,
            network_bandwidth_mbps=network_bandwidth,
            error_count=error_count,
            warning_count=warning_count,
            status=status,
            last_updated=datetime.now()
        )
        
    def get_storage_metrics(self) -> StorageMetrics:
        """Collect storage metrics"""
        total_capacity = sum(p.total_capacity_gb for p in self.system.storage_pools.values())
        used_capacity = sum(p.total_capacity_gb - p.available_capacity_gb 
                          for p in self.system.storage_pools.values())
        available_capacity = total_capacity - used_capacity
        usage_percent = (used_capacity / total_capacity * 100) if total_capacity > 0 else 0
        
        return StorageMetrics(
            total_capacity_gb=total_capacity,
            used_capacity_gb=used_capacity,
            available_capacity_gb=available_capacity,
            usage_percent=usage_percent,
            dedup_ratio=2.3,  # In production, calculate from actual data
            compression_ratio=1.8,
            iops=15000,
            throughput_mbps=450.0,
            last_updated=datetime.now()
        )
        
    def get_cost_metrics(self) -> CostMetrics:
        """Collect cost metrics"""
        # In production, these would be calculated from actual usage
        total_cost = 1250.0
        tiering_savings = 450.0
        dedup_savings = 280.0
        compression_savings = 180.0
        total_savings = tiering_savings + dedup_savings + compression_savings
        projected_cost = 1500.0
        cost_trend = ((projected_cost - total_cost) / total_cost * 100)
        
        return CostMetrics(
            total_cost_month=total_cost,
            savings_from_tiering=tiering_savings,
            savings_from_dedup=dedup_savings,
            savings_from_compression=compression_savings,
            total_savings=total_savings,
            projected_cost_next_month=projected_cost,
            cost_trend_percent=cost_trend,
            cost_per_gb={
                "performance": 0.15,
                "capacity": 0.05,
                "cold": 0.01,
                "archive": 0.004
            },
            last_updated=datetime.now()
        )
        
    def get_policy_metrics(self) -> PolicyMetrics:
        """Collect policy engine metrics"""
        policy_dist = {
            "manual": 0,
            "ml": 0,
            "hybrid": 0,
            "supervised": 0
        }
        
        tier_dist = {
            "performance": 0,
            "capacity": 0,
            "cold": 0,
            "archive": 0
        }
        
        for volume in self.system.volumes.values():
            if volume.cloud_tiering_enabled:
                policy_dist["hybrid"] += 1
            else:
                policy_dist["manual"] += 1
                
            for temp in volume.data_temperature.values():
                tier_dist[temp.current_tier.value.lower()] += 1
                
        return PolicyMetrics(
            policy_distribution=policy_dist,
            tier_distribution=tier_dist,
            ml_policy_accuracy=92.5,  # In production, calculate from actual predictions
            policy_changes_24h=15,
            data_moved_24h_gb=250.0,
            last_updated=datetime.now()
        )
        
    def get_recommendations(self) -> List[SystemRecommendation]:
        """Generate system recommendations"""
        recommendations = []
        
        # Check storage capacity
        storage = self.get_storage_metrics()
        if storage.usage_percent > 80:
            recommendations.append(
                SystemRecommendation(
                    category="capacity",
                    severity="warning",
                    title="High Storage Usage",
                    description=f"Storage usage is at {storage.usage_percent:.1f}%",
                    suggestions=[
                        "Consider adding more capacity",
                        "Review data retention policies",
                        "Enable automatic tiering to cold storage"
                    ],
                    created_at=datetime.now()
                )
            )
            
        # Check performance
        health = self.get_health_metrics()
        if health.io_latency_ms > 10:
            recommendations.append(
                SystemRecommendation(
                    category="performance",
                    severity="warning",
                    title="High I/O Latency",
                    description=f"I/O latency is {health.io_latency_ms:.1f}ms",
                    suggestions=[
                        "Check for hot spots in data access",
                        "Consider redistributing workload",
                        "Review storage pool configuration"
                    ],
                    created_at=datetime.now()
                )
            )
            
        # Check costs
        costs = self.get_cost_metrics()
        if costs.cost_trend_percent > 20:
            recommendations.append(
                SystemRecommendation(
                    category="cost",
                    severity="warning",
                    title="Rising Cost Trajectory",
                    description=f"Costs are projected to increase by {costs.cost_trend_percent:.1f}%",
                    suggestions=[
                        "Review data placement policies",
                        "Enable cost-optimization features",
                        "Consider archiving cold data"
                    ],
                    created_at=datetime.now()
                )
            )
            
        return recommendations
        
    def get_all_metrics(self) -> DashboardMetrics:
        """Get all dashboard metrics"""
        return DashboardMetrics(
            health=self.get_health_metrics(),
            storage=self.get_storage_metrics(),
            cost=self.get_cost_metrics(),
            policy=self.get_policy_metrics(),
            recommendations=self.get_recommendations()
        )

# Initialize metrics manager with the system
metrics_manager = MetricsManager(HybridStorageSystem(
    name="Production DFS",
    storage_pools={},
    volumes={}
))

@router.get("/api/dashboard/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics():
    """Get all dashboard metrics"""
    try:
        return metrics_manager.get_all_metrics()
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching dashboard metrics")

@router.get("/api/dashboard/health", response_model=SystemHealthMetrics)
async def get_health_metrics():
    """Get system health metrics"""
    try:
        return metrics_manager.get_health_metrics()
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching health metrics")

@router.get("/api/dashboard/storage", response_model=StorageMetrics)
async def get_storage_metrics():
    """Get storage metrics"""
    try:
        return metrics_manager.get_storage_metrics()
    except Exception as e:
        logger.error(f"Error getting storage metrics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching storage metrics")

@router.get("/api/dashboard/cost", response_model=CostMetrics)
async def get_cost_metrics():
    """Get cost metrics"""
    try:
        return metrics_manager.get_cost_metrics()
    except Exception as e:
        logger.error(f"Error getting cost metrics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching cost metrics")

@router.get("/api/dashboard/policy", response_model=PolicyMetrics)
async def get_policy_metrics():
    """Get policy metrics"""
    try:
        return metrics_manager.get_policy_metrics()
    except Exception as e:
        logger.error(f"Error getting policy metrics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching policy metrics")

@router.get("/api/dashboard/recommendations", response_model=List[SystemRecommendation])
async def get_recommendations():
    """Get system recommendations"""
    try:
        return metrics_manager.get_recommendations()
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail="Error fetching recommendations")

@router.get("/metrics")
async def get_metrics():
    """Get all dashboard metrics"""
    try:
        metrics = metrics_manager.get_all_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
