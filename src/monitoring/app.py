from flask import Flask, render_template, jsonify, Response, request
from kubernetes import client
from datetime import datetime
import os
import urllib3
import requests
import time
from flask_cors import CORS
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import sys
import psutil
import json
import socket
import traceback
import logging
import threading

# Create a logger
logger = logging.getLogger(__name__)

# Disable SSL warnings
urllib3.disable_warnings()

# Create a single registry for all metrics
REQUESTS = Counter(
    'dfs_request_total',
    'Total number of requests by endpoint and method',
    ['endpoint', 'method', 'status']
)

LATENCY = Histogram(
    'dfs_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint', 'method'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
)

NETWORK_IO = Counter(
    'dfs_network_bytes_total',
    'Network I/O in bytes',
    ['direction']  # 'in' or 'out'
)

NETWORK_RECEIVED = Counter(
    'dfs_network_received_bytes_total',
    'Total number of bytes received',
    ['instance']
)

NETWORK_TRANSMITTED = Counter(
    'dfs_network_transmitted_bytes_total',
    'Total number of bytes transmitted',
    ['instance']
)

STORAGE_TOTAL = Gauge(
    'dfs_storage_bytes_total',
    'Total storage capacity in bytes'
)

STORAGE_USED = Gauge(
    'dfs_storage_bytes_used',
    'Used storage in bytes'
)

STORAGE_AVAILABLE = Gauge(
    'dfs_storage_bytes_available',
    'Available storage in bytes'
)

CPU_USAGE = Gauge(
    'dfs_cpu_usage_percent',
    'CPU usage percentage'
)

MEMORY_USAGE = Gauge(
    'dfs_memory_usage_bytes',
    'Memory usage in bytes',
    ['type']  # 'total', 'used', 'available'
)

POD_STATUS = Gauge(
    'dfs_pod_status',
    'Status of pods in the distributed system',
    ['pod_name', 'status', 'ip', 'node']
)

REQUEST_QUEUE_LENGTH = Gauge(
    'dfs_request_queue_length',
    'Current length of the request queue',
    ['instance']
)

# Initialize Flask app with CORS and templates
app = Flask(__name__,
           template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'),
           static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static'))
CORS(app)

# Add error handlers
@app.errorhandler(404)
def not_found_error(error):
    print(f"404 Error: {error}", file=sys.stderr)
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    print(f"500 Error: {error}", file=sys.stderr)
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(503)
def service_unavailable_error(error):
    print(f"503 Error: {error}", file=sys.stderr)
    return jsonify({'error': 'Service temporarily unavailable'}), 503

# Add request logging
@app.before_request
def log_request_info():
    print(f"Request: {request.method} {request.path}", file=sys.stderr)

@app.after_request
def log_response_info(response):
    print(f"Response: {response.status}", file=sys.stderr)
    return response

class RequestQueue:
    def __init__(self):
        self.queue = []
        self.lock = threading.Lock()

    def add_request(self, request):
        with self.lock:
            self.queue.append(request)

    def remove_request(self):
        with self.lock:
            if self.queue:
                return self.queue.pop(0)
            return None

    def get_length(self):
        with self.lock:
            return len(self.queue)

# Initialize request queue
app.request_queue = RequestQueue()

@app.before_request
def track_request():
    """Track incoming requests"""
    try:
        if not request.path.startswith(('/metrics', '/static')):  # Don't track metrics endpoint
            app.request_queue.add_request({
                'path': request.path,
                'method': request.method,
                'time': time.time()
            })
    except Exception as e:
        logger.error(f"Error tracking request: {e}")

@app.after_request
def process_request(response):
    """Process completed requests"""
    try:
        if not request.path.startswith(('/metrics', '/static')):
            app.request_queue.remove_request()
    except Exception as e:
        logger.error(f"Error processing request: {e}")
    return response

# Environment Configuration
STORAGE_PATH = os.getenv('DFS_STORAGE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'storage'))
POLICY_CONFIG_PATH = os.getenv('DFS_POLICY_CONFIG', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'policy_overrides.json'))
KUBERNETES_ENABLED = os.getenv('DFS_KUBERNETES_ENABLED', 'false').lower() == 'true'

# Create required directories if they don't exist
os.makedirs(STORAGE_PATH, exist_ok=True)
os.makedirs(os.path.dirname(POLICY_CONFIG_PATH), exist_ok=True)

# Create default policy file if it doesn't exist
if not os.path.exists(POLICY_CONFIG_PATH):
    default_policy = {
        "storage_policies": {
            "compression_enabled": True,
            "deduplication_enabled": True,
            "max_file_size_gb": 10,
            "retention_days": 30
        },
        "distribution_policies": {
            "min_replicas": 2,
            "max_replicas": 5,
            "target_availability": 0.99999
        }
    }
    try:
        with open(POLICY_CONFIG_PATH, 'w') as f:
            json.dump(default_policy, f, indent=4)
        print(f"Created default policy file at {POLICY_CONFIG_PATH}")
    except Exception as e:
        print(f"Error creating policy file: {e}", file=sys.stderr)

# Store previous network counters for calculating deltas
previous_net_io = psutil.net_io_counters()
previous_timestamp = time.time()

def get_storage_metrics():
    """Get storage metrics from the filesystem"""
    try:
        disk_usage = psutil.disk_usage(STORAGE_PATH)
        total_gb = disk_usage.total / (1024 * 1024 * 1024)
        used_gb = disk_usage.used / (1024 * 1024 * 1024)
        free_gb = disk_usage.free / (1024 * 1024 * 1024)

        # Get disk I/O statistics
        disk_io = psutil.disk_io_counters()

        # Example compression and dedup ratios (in a real system, these would be calculated)
        compression_ratio = 1.2
        dedup_ratio = 1.3

        # Get IOPS and throughput
        iops = get_iops_metrics()
        throughput = get_throughput_metrics()

        iops = {"read": 0, "write": 0}
        throughput = {"read_mbps": 0, "write_mbps": 0}
        return {
            "used_storage_gb": used_gb,
            "free_storage_gb": free_gb,
            "storage_usage_percent": disk_usage.percent,
            "compression_ratio": compression_ratio,
            "dedup_ratio": dedup_ratio,
            "iops": iops,
            "throughput": throughput
        }
    except Exception as e:
        print(f"Error getting storage metrics: {e}")
        # Return default values if metrics collection fails
        return {
            "total_storage_gb": 100,
            "used_storage_gb": 30,
            "free_storage_gb": 70,
            "storage_usage_percent": 30,
            "compression_ratio": 1.0,
            "dedup_ratio": 1.0,
            "iops": {"read": 0, "write": 0},
            "throughput": {"read_mbps": 0, "write_mbps": 0}
        }

def get_policy_metrics():
    """Get policy metrics from configuration"""
    try:
        if os.path.exists(POLICY_CONFIG_PATH):
            with open(POLICY_CONFIG_PATH, 'r') as f:
                policy = json.load(f)
                return policy.get('storage_policies', {})
        else:
            # Return default policy if file doesn't exist
            return {
                "compression_enabled": True,
                "deduplication_enabled": True,
                "max_file_size_gb": 10,
                "retention_days": 30
            }
    except Exception as e:
        print(f"Error reading policy file: {e}", file=sys.stderr)
        # Return default policy on error
        return {
            "compression_enabled": True,
            "deduplication_enabled": True,
            "max_file_size_gb": 10,
            "retention_days": 30
        }

def update_pod_metrics():
    """Update pod metrics from Kubernetes if enabled"""
    if not KUBERNETES_ENABLED:
        return

    try:
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace='default')
        for pod in pods.items:
            POD_STATUS.labels(
                pod_name=pod.metadata.name,
                status=pod.status.phase,
                ip=pod.status.pod_ip or 'None',
                node=pod.spec.node_name or 'None'
            ).set(1 if pod.status.phase == 'Running' else 0)
    except Exception as e:
        print(f"Error updating pod metrics: {e}")

def update_system_metrics():
    """Update system metrics"""
    try:
        # Get CPU and memory metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        # Update Prometheus metrics
        CPU_USAGE.set(cpu_percent)
        MEMORY_USAGE.labels(type='total').set(memory.total)
        MEMORY_USAGE.labels(type='used').set(memory.used)
        MEMORY_USAGE.labels(type='available').set(memory.available)

        # Get storage metrics
        storage = get_storage_metrics()

        # Update storage metrics (convert GB to bytes)
        bytes_per_gb = 1024 * 1024 * 1024
        STORAGE_TOTAL.set(storage["total_storage_gb"] * bytes_per_gb)
        STORAGE_USED.set(storage["used_storage_gb"] * bytes_per_gb)
        STORAGE_AVAILABLE.set(storage["free_storage_gb"] * bytes_per_gb)

        # Update network metrics
        net_io = psutil.net_io_counters()
        NETWORK_IO.labels(direction='in').inc(net_io.bytes_recv)
        NETWORK_IO.labels(direction='out').inc(net_io.bytes_sent)

    except Exception as e:
        print(f"Error updating system metrics: {e}")

def update_network_metrics():
    """Update network I/O metrics"""
    try:
        net_io = psutil.net_io_counters()
        hostname = socket.gethostname()

        # Update received bytes
        current_received = NETWORK_RECEIVED.labels(instance=hostname)._value.get()
        if net_io.bytes_recv > current_received:
            NETWORK_RECEIVED.labels(instance=hostname).inc(net_io.bytes_recv - current_received)

        # Update transmitted bytes
        current_transmitted = NETWORK_TRANSMITTED.labels(instance=hostname)._value.get()
        if net_io.bytes_sent > current_transmitted:
            NETWORK_TRANSMITTED.labels(instance=hostname).inc(net_io.bytes_sent - current_transmitted)

    except Exception as e:
        logger.error(f"Error updating network metrics: {e}")

def update_request_metrics():
    """Update request queue metrics"""
    try:
        hostname = socket.gethostname()

        # Get the current request queue length
        queue_length = app.request_queue.get_length()

        # Update the gauge
        REQUEST_QUEUE_LENGTH.labels(instance=hostname).set(queue_length)
    except Exception as e:
        logger.error(f"Error updating request metrics: {e}")

# Basic routes
@app.route('/')
def index():
    """Serve the main dashboard page"""
    return render_template('index.html')

@app.route('/metrics')
def metrics():
    """Endpoint for Prometheus metrics."""
    try:
        # Update all metrics
        update_system_metrics()
        update_network_metrics()
        update_request_metrics()

        # Generate Prometheus format metrics
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Error in metrics endpoint: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/metrics')
def dashboard_metrics():
    """Dashboard metrics endpoint"""
    try:
        print("Entering dashboard_metrics endpoint", file=sys.stderr)
        metrics_data = get_metrics()
        return jsonify({
            'metrics': metrics_data
        })
    except Exception as e:
        print(f"Error in dashboard_metrics: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 503

@app.route('/api/docs')
def api_docs():
    try:
        print("Entering api_docs endpoint", file=sys.stderr)
        docs = {
            "openapi": "3.0.0",
            "info": {
                "title": "DFS Monitoring API",
                "version": "1.0.0",
                "description": "API for the Distributed File System Monitoring Service"
            },
            "servers": [
                {
                    "url": "http://localhost:5001",
                    "description": "Local development server"
                }
            ],
            "paths": {
                "/": {
                    "get": {
                        "summary": "Monitoring Dashboard",
                        "description": "Returns the main monitoring dashboard UI",
                        "responses": {
                            "200": {
                                "description": "HTML dashboard page"
                            }
                        }
                    }
                },
                "/api/dashboard/metrics": {
                    "get": {
                        "summary": "Dashboard Metrics",
                        "description": "Returns comprehensive system metrics",
                        "responses": {
                            "200": {
                                "description": "System metrics in JSON format",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "metrics": {
                                                    "type": "object"
                                                },
                                                "timestamp": {
                                                    "type": "string",
                                                    "format": "date-time"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/metrics": {
                    "get": {
                        "summary": "Prometheus Metrics",
                        "description": "Returns metrics in Prometheus format",
                        "responses": {
                            "200": {
                                "description": "Metrics in Prometheus text format",
                                "content": {
                                    "text/plain": {
                                        "schema": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/health": {
                    "get": {
                        "summary": "Health check endpoint",
                        "description": "Returns the health status of the service",
                        "responses": {
                            "200": {
                                "description": "Health status in JSON format",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "status": {
                                                    "type": "string"
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        print("Returning API docs", file=sys.stderr)
        return jsonify(docs)
    except Exception as e:
        print(f"Error in api_docs: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 503

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Check if we can connect to the storage nodes
        healthy = True
        node_status = {}

        for node in ['node1', 'node2', 'node3']:
            try:
                response = requests.get(f'http://{node}:8001/health', timeout=2)
                node_status[node] = {
                    'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                    'code': response.status_code
                }
            except Exception as e:
                healthy = False
                node_status[node] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }

        status_code = 200 if healthy else 503
        return jsonify({
            'status': 'healthy' if healthy else 'unhealthy',
            'nodes': node_status
        }), status_code
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503

def get_iops_metrics():
    """Get IOPS metrics from disk IO counters"""
    try:
        disk_io = psutil.disk_io_counters()
        if disk_io:
            return {
                "read": int(disk_io.read_count),
                "write": int(disk_io.write_count)
            }
    except Exception as e:
        print(f"Error getting IOPS metrics: {e}")
    return {"read": 0, "write": 0}

def get_throughput_metrics():
    """Get throughput metrics from disk IO counters"""
    try:
        disk_io = psutil.disk_io_counters()
        if disk_io:
            # Convert bytes to MB/s
            read_mbps = disk_io.read_bytes / (1024 * 1024)
            write_mbps = disk_io.write_bytes / (1024 * 1024)
            return {
                "read_mbps": round(read_mbps, 2),
                "write_mbps": round(write_mbps, 2)
            }
    except Exception as e:
        print(f"Error getting throughput metrics: {e}")
    return {"read_mbps": 0, "write_mbps": 0}

def get_metrics():
    """Get comprehensive system metrics"""
    try:
        current_time = datetime.now().isoformat()

        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        net_io = psutil.net_io_counters()
        disk_io = psutil.disk_io_counters()
        storage = get_storage_metrics()

        # Calculate network bandwidth in Mbps
        network_bandwidth = (net_io.bytes_sent + net_io.bytes_recv) * 8 / (1024 * 1024)  # Convert to Mbps

        # Health metrics
        health = {
            "cpu_usage": round(cpu_percent, 1),
            "memory_usage": round(memory.percent, 1),
            "network_bandwidth_mbps": round(network_bandwidth, 2),
            "io_latency_ms": 0,  # Would need actual IO latency measurement
            "error_count": 0,
            "warning_count": 2,  # Example value
            "status": "healthy" if cpu_percent < 80 and memory.percent < 80 else "warning",
            "last_updated": current_time
        }

        # Storage metrics
        storage_metrics = {
            "total_capacity_gb": storage["total_storage_gb"],
            "used_capacity_gb": storage["used_storage_gb"],
            "available_capacity_gb": storage["free_storage_gb"],
            "usage_percent": storage["storage_usage_percent"],
            "compression_ratio": storage["compression_ratio"],
            "dedup_ratio": storage["dedup_ratio"],
            "iops": storage["iops"],
            "throughput_mbps": storage["throughput"],
            "bytes_in": int(net_io.bytes_recv),
            "bytes_out": int(net_io.bytes_sent),
            "last_updated": current_time
        }

        # Cost metrics
        cost = {
            "total_cost_month": 1250.0,
            "savings_from_tiering": 450.0,
            "savings_from_dedup": 300.0,
            "savings_from_compression": 200.0,
            "total_savings": 950.0,
            "last_updated": current_time
        }

        # Get policy metrics
        policy = get_policy_metrics()

        # Generate recommendations based on metrics
        recommendations = [
            {
                "category": "performance",
                "severity": "warning" if health["io_latency_ms"] > 5 else "info",
                "title": "High I/O Latency",
                "description": "Storage tier showing increased latency",
                "suggestions": [
                    "Consider moving frequently accessed data to SSD tier",
                    "Review application I/O patterns"
                ],
                "created_at": current_time
            },
            {
                "category": "policy",
                "severity": "info",
                "title": "Policy Distribution",
                "description": f"Current policy distribution: {policy.get('compression_enabled', False)}, {policy.get('deduplication_enabled', False)}",
                "suggestions": [
                    "Review policy patterns for optimal data placement",
                    "Consider consolidating similar policies"
                ],
                "created_at": current_time
            }
        ]

        return {
            "health": health,
            "storage": storage_metrics,
            "cost": cost,
            "policy": policy,
            "recommendations": recommendations
        }
    except Exception as e:
        print(f"Error in get_metrics: {e}", file=sys.stderr)
        return {'error': str(e)}

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def cleanup():
    print("Cleaning up...")
    # Any cleanup code here if needed
    sys.exit(0)

# S3 API proxy
@app.route('/s3/', defaults={'subpath': ''})
@app.route('/s3/<path:subpath>')
def s3_proxy(subpath):
    """Proxy requests to the S3 API"""
    try:
        # Build the target URL - use the Docker service name
        target_url = f'http://node1:8000/{subpath}'
        print(f"Proxying request to: {target_url}", file=sys.stderr)

        # Forward the request
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers={key: value for (key, value) in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True
        )

        # Create the response
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                  if name.lower() not in excluded_headers]

        print(f"Proxy response status: {resp.status_code}", file=sys.stderr)

        response = Response(resp.content, resp.status_code, headers)
        return response

    except Exception as e:
        print(f"Error in s3_proxy: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    try:
        # Start Flask app
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)
