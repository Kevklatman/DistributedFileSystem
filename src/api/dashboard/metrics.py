"""
Dashboard metrics and monitoring endpoints
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

PROMETHEUS_URL = "http://prometheus:9090"

class SystemMetrics(BaseModel):
    """System metrics"""
    cpu_percent: float
    memory: Dict[str, float]  # total, used, available in bytes
    network: Dict[str, float]  # bytes_in, bytes_out, total
    timestamp: str

class StorageMetrics(BaseModel):
    """Storage metrics"""
    total: float  # bytes
    used: float   # bytes
    available: float  # bytes
    percent: float

class NodeMetrics(BaseModel):
    """Individual node metrics"""
    name: str
    status: str
    cpu_percent: float
    memory_used_percent: float
    latency_ms: float

class DashboardMetrics(BaseModel):
    """Complete dashboard metrics"""
    system: SystemMetrics
    storage: StorageMetrics
    nodes: List[NodeMetrics]

def query_prometheus(query: str) -> dict:
    """Execute a PromQL query"""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5
        )
        if response.ok:
            return response.json()
        logger.error(f"Prometheus query failed: {response.text}")
        return None
    except Exception as e:
        logger.error(f"Error querying Prometheus: {e}")
        return None

@router.get("/metrics")
async def get_metrics():
    """Get aggregated metrics from all nodes via Prometheus"""
    try:
        # System-wide metrics
        cpu_query = 'avg(rate(process_cpu_seconds_total[5m]) * 100)'
        memory_query = 'sum(process_resident_memory_bytes) by (job)'
        network_in_query = 'sum(rate(node_network_receive_bytes_total[5m]))'
        network_out_query = 'sum(rate(node_network_transmit_bytes_total[5m]))'

        # Storage metrics
        storage_total = 'sum(node_filesystem_size_bytes{mountpoint="/app/data"})'
        storage_free = 'sum(node_filesystem_free_bytes{mountpoint="/app/data"})'

        # Per-node metrics
        node_cpu = 'rate(process_cpu_seconds_total[5m]) * 100'
        node_memory = 'process_resident_memory_bytes / node_memory_MemTotal_bytes * 100'
        node_latency = 'rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m]) * 1000'

        # Execute queries
        cpu_result = query_prometheus(cpu_query)
        memory_result = query_prometheus(memory_query)
        net_in_result = query_prometheus(network_in_query)
        net_out_result = query_prometheus(network_out_query)
        storage_total_result = query_prometheus(storage_total)
        storage_free_result = query_prometheus(storage_free)
        node_cpu_result = query_prometheus(node_cpu)
        node_memory_result = query_prometheus(node_memory)
        node_latency_result = query_prometheus(node_latency)

        # Extract values
        cpu_percent = float(cpu_result['data']['result'][0]['value'][1]) if cpu_result else 0
        memory_used = float(memory_result['data']['result'][0]['value'][1]) if memory_result else 0
        net_in = float(net_in_result['data']['result'][0]['value'][1]) if net_in_result else 0
        net_out = float(net_out_result['data']['result'][0]['value'][1]) if net_out_result else 0
        total_storage = float(storage_total_result['data']['result'][0]['value'][1]) if storage_total_result else 0
        free_storage = float(storage_free_result['data']['result'][0]['value'][1]) if storage_free_result else 0
        used_storage = total_storage - free_storage

        # Process per-node metrics
        nodes = []
        if node_cpu_result and node_memory_result and node_latency_result:
            for node in node_cpu_result['data']['result']:
                node_name = node['metric'].get('instance', 'unknown')
                nodes.append(NodeMetrics(
                    name=node_name,
                    status="up",
                    cpu_percent=float(node['value'][1]),
                    memory_used_percent=float(next(
                        (m['value'][1] for m in node_memory_result['data']['result']
                         if m['metric'].get('instance') == node_name),
                        0
                    )),
                    latency_ms=float(next(
                        (l['value'][1] for l in node_latency_result['data']['result']
                         if l['metric'].get('instance') == node_name),
                        0
                    ))
                ))

        return DashboardMetrics(
            system=SystemMetrics(
                cpu_percent=cpu_percent,
                memory={
                    "total": memory_used * 1.2,  # Approximate total based on used
                    "used": memory_used,
                    "available": memory_used * 0.2  # Approximate available
                },
                network={
                    "bytes_in": net_in,
                    "bytes_out": net_out,
                    "total": net_in + net_out
                },
                timestamp=datetime.now().isoformat()
            ),
            storage=StorageMetrics(
                total=total_storage,
                used=used_storage,
                available=free_storage,
                percent=(used_storage / total_storage * 100) if total_storage > 0 else 0
            ),
            nodes=nodes
        )
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def get_health():
    """Get system health status based on Prometheus metrics"""
    try:
        metrics = await get_metrics()
        health_status = "healthy"

        # Check system-wide health indicators
        if metrics.system.cpu_percent > 80 or metrics.storage.percent > 90:
            health_status = "warning"

        # Check if any nodes are showing high resource usage
        for node in metrics.nodes:
            if node.cpu_percent > 90 or node.memory_used_percent > 90:
                health_status = "warning"
                break

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
