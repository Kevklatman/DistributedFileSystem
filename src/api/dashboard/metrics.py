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

def get_node_metrics(node_port: int) -> dict:
    """Get metrics from a specific node"""
    try:
        response = requests.get(f'http://localhost:{node_port}/metrics', timeout=5)
        if response.ok:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error fetching metrics from node on port {node_port}: {e}")
        return None

@router.get("/metrics")
async def get_metrics():
    """Get all dashboard metrics"""
    try:
        # Get metrics from node1 (primary node)
        metrics = get_node_metrics(8001)
        if not metrics:
            raise HTTPException(status_code=500, detail="Failed to fetch metrics from primary node")

        # Get memory info
        memory = psutil.virtual_memory()._asdict()

        # Get network info
        network_io = psutil.net_io_counters()
        network = {
            "bytes_in": network_io.bytes_recv,
            "bytes_out": network_io.bytes_sent,
            "total": network_io.bytes_recv + network_io.bytes_sent
        }

        # Convert to our consistent format
        return DashboardMetrics(
            system=SystemMetrics(
                cpu_percent=psutil.cpu_percent(),
                memory={
                    "total": memory["total"],
                    "used": memory["used"],
                    "available": memory["available"]
                },
                network=network,
                timestamp=datetime.now().isoformat()
            ),
            storage=StorageMetrics(
                total=metrics.get("storage_total", 0),
                used=metrics.get("storage_used", 0),
                available=metrics.get("storage_available", 0),
                percent=metrics.get("storage_percent", 0)
            ),
            pods=[PodMetrics(
                name=f"node{i}",
                status="running" if get_node_metrics(8000 + i) else "error",
                ip=f"localhost:{8000 + i}",
                node=f"node{i}",
                start_time=datetime.now().isoformat()
            ) for i in range(1, 4)]  # Check nodes 1-3
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
