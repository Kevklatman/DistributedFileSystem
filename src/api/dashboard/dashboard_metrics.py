"""
Dashboard metrics and monitoring endpoints using the unified metrics system.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from storage.metrics import UnifiedMetricsCollector

logger = logging.getLogger(__name__)
router = APIRouter()

PROMETHEUS_URL = "http://prometheus:9091"


class NetworkMetrics(BaseModel):
    """Network metrics"""

    bytes_in: float
    bytes_out: float
    total_bytes: float


class StorageMetrics(BaseModel):
    """Storage metrics"""

    total_bytes: float
    used_bytes: float
    available_bytes: float
    usage_percent: float


class CacheMetrics(BaseModel):
    """Cache performance metrics"""

    hits: int
    misses: int
    hit_rate: float


class RequestMetrics(BaseModel):
    """Request handling metrics"""

    total_requests: int
    success_rate: float
    error_rate: float
    avg_latency: float
    p95_latency: float
    queue_length: int


class FileOperationMetrics(BaseModel):
    """File operation metrics"""

    reads: int
    writes: int
    deletes: int
    avg_duration: float


class ReplicationMetrics(BaseModel):
    """Replication metrics"""

    lag_seconds: float
    queue_length: int


class ResourceMetrics(BaseModel):
    """Resource usage metrics"""

    cpu_percent: float
    memory_used_bytes: float
    memory_total_bytes: float
    memory_percent: float


class NodeMetrics(BaseModel):
    """Individual node metrics"""

    node_id: str
    status: str  # 'healthy', 'degraded', 'unhealthy'
    uptime: float
    storage: StorageMetrics
    cache: CacheMetrics
    requests: RequestMetrics
    operations: FileOperationMetrics
    replication: ReplicationMetrics
    resources: ResourceMetrics
    network: NetworkMetrics


class DashboardMetrics(BaseModel):
    """Complete dashboard metrics"""

    timestamp: str
    nodes: List[NodeMetrics]
    cluster_storage: StorageMetrics
    total_requests: int
    global_success_rate: float
    global_error_rate: float


def query_prometheus(query: str) -> dict:
    """Execute a PromQL query"""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=5
        )
        if response.ok:
            return response.json()
        logger.error(f"Prometheus query failed: {response.text}")
        return None
    except Exception as e:
        logger.error(f"Error querying Prometheus: {e}")
        return None


def get_node_metrics(node_id: str, timeframe: str = "5m") -> NodeMetrics:
    """Get metrics for a specific node using the unified metrics system"""
    try:
        # System metrics
        cpu = query_prometheus(
            f'avg_over_time(dfs_system_cpu_percent{{instance="{node_id}"}}[{timeframe}])'
        )
        memory = query_prometheus(
            f'avg_over_time(dfs_system_memory_percent{{instance="{node_id}"}}[{timeframe}])'
        )
        uptime = query_prometheus(f'dfs_system_uptime_seconds{{instance="{node_id}"}}')

        # Storage metrics
        storage_total = query_prometheus(
            f'dfs_storage_capacity_bytes{{instance="{node_id}"}}'
        )
        storage_used = query_prometheus(
            f'dfs_storage_used_bytes{{instance="{node_id}"}}'
        )

        # Cache metrics
        cache_hits = query_prometheus(
            f'increase(dfs_cache_hits_total{{instance="{node_id}"}}[{timeframe}])'
        )
        cache_misses = query_prometheus(
            f'increase(dfs_cache_misses_total{{instance="{node_id}"}}[{timeframe}])'
        )

        # Request metrics
        total_requests = query_prometheus(
            f'increase(dfs_requests_total{{instance="{node_id}"}}[{timeframe}])'
        )
        failed_requests = query_prometheus(
            f'increase(dfs_requests_failed_total{{instance="{node_id}"}}[{timeframe}])'
        )
        request_duration = query_prometheus(
            f'rate(dfs_request_duration_seconds_sum{{instance="{node_id}"}}[{timeframe}])'
        )
        request_p95 = query_prometheus(
            f'histogram_quantile(0.95, rate(dfs_request_duration_seconds_bucket{{instance="{node_id}"}}[{timeframe}]))'
        )

        # File operations
        reads = query_prometheus(
            f'increase(dfs_file_reads_total{{instance="{node_id}"}}[{timeframe}])'
        )
        writes = query_prometheus(
            f'increase(dfs_file_writes_total{{instance="{node_id}"}}[{timeframe}])'
        )
        deletes = query_prometheus(
            f'increase(dfs_file_deletes_total{{instance="{node_id}"}}[{timeframe}])'
        )
        op_duration = query_prometheus(
            f'rate(dfs_file_operation_duration_seconds_sum{{instance="{node_id}"}}[{timeframe}])'
        )

        # Replication metrics
        rep_lag = query_prometheus(
            f'dfs_replication_lag_seconds{{instance="{node_id}"}}'
        )
        rep_queue = query_prometheus(
            f'dfs_replication_queue_length{{instance="{node_id}"}}'
        )

        # Network metrics
        network_in = query_prometheus(
            f'rate(dfs_network_received_bytes_total{{instance="{node_id}"}}[{timeframe}])'
        )
        network_out = query_prometheus(
            f'rate(dfs_network_sent_bytes_total{{instance="{node_id}"}}[{timeframe}])'
        )

        def extract_value(result):
            if result and result.get("data", {}).get("result"):
                return float(result["data"]["result"][0]["value"][1])
            return 0.0

        total_reqs = extract_value(total_requests)
        failed_reqs = extract_value(failed_requests)
        success_rate = 1.0 - (failed_reqs / total_reqs if total_reqs > 0 else 0.0)

        return NodeMetrics(
            node_id=node_id,
            status="healthy" if extract_value(uptime) > 0 else "unhealthy",
            uptime=extract_value(uptime),
            storage=StorageMetrics(
                total_bytes=extract_value(storage_total),
                used_bytes=extract_value(storage_used),
                available_bytes=extract_value(storage_total)
                - extract_value(storage_used),
                usage_percent=(
                    (extract_value(storage_used) / extract_value(storage_total) * 100)
                    if extract_value(storage_total) > 0
                    else 0
                ),
            ),
            cache=CacheMetrics(
                hits=int(extract_value(cache_hits)),
                misses=int(extract_value(cache_misses)),
                hit_rate=(
                    extract_value(cache_hits)
                    / (extract_value(cache_hits) + extract_value(cache_misses))
                    if (extract_value(cache_hits) + extract_value(cache_misses)) > 0
                    else 1.0
                ),
            ),
            requests=RequestMetrics(
                total_requests=int(total_reqs),
                success_rate=success_rate,
                error_rate=1.0 - success_rate,
                avg_latency=extract_value(request_duration),
                p95_latency=extract_value(request_p95),
                queue_length=0,  # TODO: Add queue length metric
            ),
            operations=FileOperationMetrics(
                reads=int(extract_value(reads)),
                writes=int(extract_value(writes)),
                deletes=int(extract_value(deletes)),
                avg_duration=extract_value(op_duration),
            ),
            replication=ReplicationMetrics(
                lag_seconds=extract_value(rep_lag),
                queue_length=int(extract_value(rep_queue)),
            ),
            resources=ResourceMetrics(
                cpu_percent=extract_value(cpu),
                memory_used_bytes=extract_value(memory),
                memory_total_bytes=100.0,  # Memory is reported as percentage
                memory_percent=extract_value(memory),
            ),
            network=NetworkMetrics(
                bytes_in=extract_value(network_in),
                bytes_out=extract_value(network_out),
                total_bytes=extract_value(network_in) + extract_value(network_out),
            ),
        )
    except Exception as e:
        logger.error(f"Error getting node metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics(timeframe: str = "5m"):
    """Get aggregated metrics from all nodes"""
    try:
        # Get list of all nodes
        nodes_result = query_prometheus(
            "count(dfs_system_uptime_seconds) by (instance)"
        )
        if not nodes_result or not nodes_result.get("data", {}).get("result"):
            raise HTTPException(status_code=500, detail="Failed to get node list")

        node_ids = [
            result["metric"]["instance"] for result in nodes_result["data"]["result"]
        ]

        # Get metrics for each node
        nodes_metrics = []
        for node_id in node_ids:
            node_metrics = get_node_metrics(node_id, timeframe)
            nodes_metrics.append(node_metrics)

        # Calculate cluster-wide metrics
        total_storage = sum(node.storage.total_bytes for node in nodes_metrics)
        used_storage = sum(node.storage.used_bytes for node in nodes_metrics)
        available_storage = total_storage - used_storage
        storage_percent = (
            (used_storage / total_storage * 100) if total_storage > 0 else 0
        )

        total_requests = sum(node.requests.total_requests for node in nodes_metrics)
        success_rates = [
            node.requests.success_rate
            for node in nodes_metrics
            if node.requests.total_requests > 0
        ]
        global_success_rate = (
            sum(success_rates) / len(success_rates) if success_rates else 1.0
        )

        return DashboardMetrics(
            timestamp=datetime.utcnow().isoformat(),
            nodes=nodes_metrics,
            cluster_storage=StorageMetrics(
                total_bytes=total_storage,
                used_bytes=used_storage,
                available_bytes=available_storage,
                usage_percent=storage_percent,
            ),
            total_requests=total_requests,
            global_success_rate=global_success_rate,
            global_error_rate=1.0 - global_success_rate,
        )
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_health():
    """Get system health status"""
    try:
        # Check node health using uptime as a proxy
        health_result = query_prometheus("min(dfs_system_uptime_seconds > 0)")
        if not health_result:
            return {"status": "unknown", "message": "Failed to get health metrics"}

        all_healthy = float(health_result["data"]["result"][0]["value"][1]) == 1.0

        # Check storage usage
        storage_result = query_prometheus(
            "max(dfs_storage_used_bytes / dfs_storage_capacity_bytes * 100)"
        )
        storage_critical = False
        if storage_result:
            storage_percent = float(storage_result["data"]["result"][0]["value"][1])
            storage_critical = storage_percent > 80

        # Check replication lag
        lag_result = query_prometheus("max(dfs_replication_lag_seconds)")
        replication_critical = False
        if lag_result:
            max_lag = float(lag_result["data"]["result"][0]["value"][1])
            replication_critical = max_lag > 60

        # Check error rate
        error_result = query_prometheus(
            "max(rate(dfs_requests_failed_total[5m]) / rate(dfs_requests_total[5m]))"
        )
        error_critical = False
        if error_result:
            error_rate = float(error_result["data"]["result"][0]["value"][1])
            error_critical = error_rate > 0.1  # More than 10% error rate

        if (
            all_healthy
            and not storage_critical
            and not replication_critical
            and not error_critical
        ):
            return {"status": "healthy", "message": "All systems operational"}
        elif storage_critical or replication_critical or error_critical:
            issues = {
                "storage_critical": storage_critical,
                "replication_lag": replication_critical,
                "high_error_rate": error_critical,
            }
            return {
                "status": "degraded",
                "message": "System performance may be degraded",
                "issues": {k: v for k, v in issues.items() if v},
            }
        else:
            return {"status": "unhealthy", "message": "One or more nodes are unhealthy"}
    except Exception as e:
        logger.error(f"Error checking health: {e}")
        return {"status": "unknown", "message": f"Error checking health: {str(e)}"}
