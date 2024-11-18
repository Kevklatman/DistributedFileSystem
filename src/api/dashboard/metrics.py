"""
Dashboard metrics and monitoring endpoints
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import psutil
import requests
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

class SystemMetrics(BaseModel):
    """System metrics"""
    cpu_percent: float
    memory: Dict[str, int]  # total, used, available in bytes
    network: Dict[str, int]  # bytes_in, bytes_out, total
    timestamp: str

class StorageMetrics(BaseModel):
    """Storage metrics"""
    total: int  # bytes
    used: int   # bytes
    available: int  # bytes
    percent: float

class PodMetrics(BaseModel):
    """Pod metrics"""
    name: str
    status: str
    ip: str
    node: str
    start_time: str

class DashboardMetrics(BaseModel):
    """Complete dashboard metrics"""
    system: SystemMetrics
    storage: StorageMetrics
    pods: List[PodMetrics]

@router.get("/metrics")
async def get_metrics():
    """Get all dashboard metrics"""
    try:
        # Get metrics from monitoring service
        response = requests.get('http://localhost:5001/api/dashboard/metrics', timeout=5)
        if not response.ok:
            raise HTTPException(status_code=500, detail="Failed to fetch metrics from monitoring service")

        metrics = response.json()

        # Convert to our consistent format
        return DashboardMetrics(
            system=SystemMetrics(
                cpu_percent=metrics['system']['cpu_percent'],
                memory=metrics['system']['memory'],
                network=metrics['system']['network'],
                timestamp=metrics['timestamp']
            ),
            storage=StorageMetrics(
                total=metrics['storage']['total'],
                used=metrics['storage']['used'],
                available=metrics['storage']['available'],
                percent=metrics['storage']['percent']
            ),
            pods=[PodMetrics(
                name=pod['name'],
                status=pod['status'],
                ip=pod['ip'],
                node=pod['node'],
                start_time=pod['start_time']
            ) for pod in metrics['pods']]
        )
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def get_health():
    """Get system health status"""
    try:
        metrics = await get_metrics()
        health_status = "healthy"
        if metrics.system.cpu_percent > 80 or metrics.storage.percent > 90:
            health_status = "warning"

        return {
            "status": health_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking health: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }
