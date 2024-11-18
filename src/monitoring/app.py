from flask import Flask, render_template, jsonify, Response, request
from kubernetes import client, config, utils
from datetime import datetime
import os
import ssl
import urllib3
import requests
import time
from flask_cors import CORS
from prometheus_client import start_http_server, Counter, Histogram, Gauge, REGISTRY, generate_latest, CONTENT_TYPE_LATEST
import sys
import psutil
from pathlib import Path
import json
import socket
import atexit

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

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",  # React dev server
            "http://localhost:5000",  # Local Flask server
            "http://localhost:5001",  # Docker Flask server
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Store previous network counters for calculating deltas
previous_net_io = psutil.net_io_counters()
previous_timestamp = time.time()

def update_system_metrics():
    """Update system metrics including CPU and memory"""
    global previous_net_io, previous_timestamp
    try:
        # CPU metrics
        CPU_USAGE.set(psutil.cpu_percent(interval=1))

        # Memory metrics
        memory = psutil.virtual_memory()
        MEMORY_USAGE.labels(type='total').set(memory.total)
        MEMORY_USAGE.labels(type='used').set(memory.used)
        MEMORY_USAGE.labels(type='available').set(memory.available)

        # Storage metrics
        storage = get_storage_metrics()

        # Update storage metrics
        STORAGE_TOTAL.set(storage["total_storage_gb"] * (1024 * 1024 * 1024))
        STORAGE_USED.set(storage["used_storage_gb"] * (1024 * 1024 * 1024))
        STORAGE_AVAILABLE.set(storage["free_storage_gb"] * (1024 * 1024 * 1024))

        # Network metrics - calculate bytes/sec
        current_net_io = psutil.net_io_counters()
        current_timestamp = time.time()
        time_delta = current_timestamp - previous_timestamp

        if time_delta > 0:
            bytes_in = int((current_net_io.bytes_recv - previous_net_io.bytes_recv) / time_delta)
            bytes_out = int((current_net_io.bytes_sent - previous_net_io.bytes_sent) / time_delta)

            NETWORK_IO.labels(direction='in').inc(bytes_in)
            NETWORK_IO.labels(direction='out').inc(bytes_out)

        # Update previous values
        previous_net_io = current_net_io
        previous_timestamp = current_timestamp

    except Exception as e:
        print(f"Error updating system metrics: {e}", file=sys.stderr)

def update_pod_metrics():
    """Update pod metrics from Kubernetes"""
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(namespace='default')  # Changed to 'default' namespace

        # Clear existing pod metrics
        for item in REGISTRY.collect():
            if item.name == 'dfs_pod_status':
                for metric in item.samples:
                    POD_STATUS.remove(*[l for l in metric.labels.values()])

        # Set new pod metrics
        for pod in pods.items:
            POD_STATUS.labels(
                pod_name=pod.metadata.name,
                status=pod.status.phase,
                ip=pod.status.pod_ip or 'None',
                node=pod.spec.node_name or 'None'
            ).set(1)
    except Exception as e:
        print(f"Error updating pod metrics: {e}", file=sys.stderr)

@app.before_request
def before_request():
    update_system_metrics()  # Now includes CPU and memory
    update_pod_metrics()
    request.start_time = time.time()

@app.after_request
def after_request(response):
    if request.path != '/formatted_metrics':  # Don't track metrics about getting metrics
        latency = time.time() - request.start_time
        REQUESTS.labels(
            endpoint=request.endpoint or 'unknown',
            method=request.method,
            status=response.status_code
        ).inc()

        LATENCY.labels(
            endpoint=request.endpoint or 'unknown',
            method=request.method
        ).observe(latency)

        # Track response size
        response_size = len(response.get_data())
        NETWORK_IO.labels(direction='out').inc(response_size)

        # Track request size
        request_size = len(request.get_data())
        NETWORK_IO.labels(direction='in').inc(request_size)

    return response

# Configure Kubernetes client
try:
    # Try to load the local kubeconfig first
    config.load_kube_config()
except:
    try:
        # If local config fails, try in-cluster config
        config.load_incluster_config()
    except:
        print("Failed to load both local and in-cluster Kubernetes config")
        v1 = None

# Create the API client if config was loaded
if 'v1' not in locals():
    try:
        v1 = client.CoreV1Api()
        print("Successfully connected to Kubernetes API")
    except Exception as e:
        print(f"Error creating Kubernetes client: {e}")
        v1 = None

@app.route('/')
def index():
    return render_template('index.html')

def get_policy_metrics():
    """Get policy metrics from configuration"""
    try:
        # Get project root directory
        policy_file = Path("/app/config/policy_overrides.json")

        if not policy_file.exists():
            print(f"Policy file not found at {policy_file}")
            return {
                "policy_distribution": {"hot": 0, "warm": 0, "cold": 0},
                "total_policies": 0,
                "ml_policy_accuracy": 0,
                "policy_changes_24h": 0,
                "data_moved_24h_gb": 0
            }

        with open(policy_file, 'r') as f:
            policy_data = json.load(f)

        # Calculate policy distribution
        tier_counts = {"performance": 0, "capacity": 0, "cold": 0}
        for override in policy_data.get("path_overrides", []):
            tier = override.get("tier")
            if tier in tier_counts:
                tier_counts[tier] += 1

        total_policies = len(policy_data.get("path_overrides", []))

        return {
            "policy_distribution": {
                "hot": round((tier_counts["performance"] / total_policies * 100) if total_policies > 0 else 0),
                "warm": round((tier_counts["capacity"] / total_policies * 100) if total_policies > 0 else 0),
                "cold": round((tier_counts["cold"] / total_policies * 100) if total_policies > 0 else 0)
            },
            "total_policies": total_policies,
            "ml_policy_accuracy": policy_data.get("ml_accuracy", 0),
            "policy_changes_24h": policy_data.get("changes_24h", 0),
            "data_moved_24h_gb": policy_data.get("data_moved_gb", 0)
        }
    except Exception as e:
        print(f"Error getting policy metrics: {e}")
        return {
            "policy_distribution": {"hot": 0, "warm": 0, "cold": 0},
            "total_policies": 0,
            "ml_policy_accuracy": 0,
            "policy_changes_24h": 0,
            "data_moved_24h_gb": 0
        }

def get_storage_metrics():
    """Get storage metrics from the filesystem"""
    try:
        # Get storage path from environment or use default
        storage_path = os.getenv('DFS_STORAGE_PATH', os.path.expanduser('~'))

        # Get disk usage statistics for the root directory if storage path doesn't exist
        if not os.path.exists(storage_path):
            storage_path = '/'
        
        disk_usage = psutil.disk_usage(storage_path)

        # Calculate storage metrics
        total_gb = disk_usage.total / (1024 * 1024 * 1024)  # Convert to GB
        used_gb = disk_usage.used / (1024 * 1024 * 1024)
        free_gb = disk_usage.free / (1024 * 1024 * 1024)

        # Get disk I/O statistics
        disk_io = psutil.disk_io_counters()
        
        # Calculate compression and dedup ratios (simplified for demo)
        compression_ratio = 1.2  # Example ratio
        dedup_ratio = 1.3       # Example ratio

        # Get IOPS and throughput
        iops = get_iops_metrics()
        throughput = get_throughput_metrics()

        return {
            "total_storage_gb": round(total_gb, 2),
            "used_storage_gb": round(used_gb, 2),
            "free_storage_gb": round(free_gb, 2),
            "storage_usage_percent": round(disk_usage.percent, 2),
            "compression_ratio": compression_ratio,
            "dedup_ratio": dedup_ratio,
            "iops": iops,
            "throughput": throughput
        }
    except Exception as e:
        print(f"Error getting storage metrics: {e}")
        return {
            "total_storage_gb": 0,
            "used_storage_gb": 0,
            "free_storage_gb": 0,
            "storage_usage_percent": 0,
            "compression_ratio": 1.0,
            "dedup_ratio": 1.0,
            "iops": {"read": 0, "write": 0},
            "throughput": {"read_mbps": 0, "write_mbps": 0}
        }

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

@app.route('/api/dashboard/metrics')
def api_metrics():
    """API endpoint for dashboard metrics"""
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
                "description": f"Current policy distribution: {policy['policy_distribution']}",
                "suggestions": [
                    "Review policy patterns for optimal data placement",
                    "Consider consolidating similar policies"
                ],
                "created_at": current_time
            }
        ]

        return jsonify({
            "health": health,
            "storage": storage_metrics,
            "cost": cost,
            "policy": policy,
            "recommendations": recommendations
        })

    except Exception as e:
        print(f"Error in api_metrics: {e}", file=sys.stderr)
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def api_health():
    try:
        response = requests.get('http://localhost:5555/api/v1/health', timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({'status': 'not available', 'error': f'API returned status {response.status_code}'}), 503
    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'not available', 'error': str(e)}), 503

@app.route('/api/docs')
def api_docs():
    try:
        response = requests.get('http://localhost:5555/api/v1/swagger.json', timeout=5)
        if response.status_code == 200:
            return response.json(), 200
        return jsonify({'error': f'API documentation not available (status {response.status_code})'}), 503
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 503

@app.route('/api/<path:path>')
def api_proxy(path):
    try:
        # Don't modify health check path
        if path == 'health':
            target_url = f'http://localhost:5555/api/v1/health'
        else:
            target_url = f'http://localhost:5555/api/v1/{path}'

        headers = {key: value for key, value in request.headers if key.lower() != 'host'}

        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            timeout=10
        )

        excluded_headers = ['content-length', 'connection', 'content-encoding']
        headers = [(k, v) for k, v in response.raw.headers.items() if k.lower() not in excluded_headers]

        return Response(response.content, response.status_code, headers)
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 503

@app.route('/web-ui')
@app.route('/web-ui/<path:path>')
def web_ui_proxy(path=''):
    try:
        target_url = f'http://localhost:3000/{path}'
        headers = {
            key: value for key, value
            in request.headers.items()
            if key.lower() not in ['host', 'content-length']
        }

        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            timeout=5,
            allow_redirects=True
        )

        # Only forward specific headers we want
        allowed_headers = [
            'content-type',
            'cache-control',
            'etag',
            'date',
            'last-modified'
        ]

        headers = {
            k: v for k, v in response.headers.items()
            if k.lower() in allowed_headers
        }

        # Ensure we're returning text/html for the main page
        if not path and 'content-type' not in headers:
            headers['content-type'] = 'text/html; charset=utf-8'

        return Response(
            response.content,
            response.status_code,
            headers
        )
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 503

@app.route('/web-ui/status')
def web_ui_status():
    """Check Web UI status"""
    try:
        response = requests.get('http://localhost:3000/', timeout=5)
        if response.status_code == 200:
            return jsonify({'status': 'available'}), 200
        return jsonify({
            'status': 'not available',
            'error': f'Web UI returned status {response.status_code}'
        }), 503
    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'not available',
            'error': str(e)
        }), 503

@app.route('/api/status')
def api_status():
    """Check API status"""
    try:
        response = requests.get('http://localhost:5555/api/v1/health', timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({
            'status': 'not available',
            'error': f'API returned status {response.status_code}'
        }), 503
    except requests.exceptions.RequestException as e:
        return jsonify({
            'status': 'not available',
            'error': str(e)
        }), 503

@app.route('/formatted_metrics')
def formatted_metrics():
    """Custom metrics endpoint that formats Prometheus metrics for readability"""
    # Use the same registry as the Prometheus server
    raw_metrics = generate_latest(REGISTRY).decode('utf-8')

    # Parse and format metrics
    formatted_metrics = []
    current_metric = []

    for line in raw_metrics.split('\n'):
        if line.startswith('# HELP'):
            if current_metric:
                formatted_metrics.append('\n'.join(current_metric))
                formatted_metrics.append('-' * 80 + '\n')  # Separator
            current_metric = []
            # Format help line
            name = line.split()[2]
            help_text = ' '.join(line.split()[3:])
            current_metric.append(f"\n📊 Metric: {name}")
            current_metric.append(f"📝 Description: {help_text}")
        elif line.startswith('# TYPE'):
            type_text = line.split()[3]
            current_metric.append(f"📈 Type: {type_text}")
        elif line and not line.startswith('#'):
            # Format metric values
            parts = line.split()
            if len(parts) >= 1:
                metric_name = parts[0].split('{')[0]
                if '{' in line:
                    labels = line[line.index('{')+1:line.index('}')]
                    value = line.split()[-1]
                    current_metric.append(f"   └─ {labels}: {value}")
                else:
                    value = parts[-1]
                    current_metric.append(f"   └─ Value: {value}")

    # Add the last metric group
    if current_metric:
        formatted_metrics.append('\n'.join(current_metric))

    # Return formatted metrics with text/plain content type
    return Response('\n'.join(formatted_metrics), mimetype='text/plain')

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    try:
        # Update metrics before returning
        update_system_metrics()
        update_pod_metrics()

        # Generate and return metrics in Prometheus format
        return Response(generate_latest(), mimetype='text/plain')
    except Exception as e:
        print(f"Error generating metrics: {e}")
        return Response(status=500)

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def cleanup():
    print("Cleaning up...")
    # Any cleanup code here if needed
    sys.exit(0)

if __name__ == '__main__':
    # Register cleanup function
    atexit.register(cleanup)

    try:
        # Check if ports are already in use
        if is_port_in_use(9091):
            print("Error: Port 9091 is already in use. Please free up the port and try again.")
            sys.exit(1)
        if is_port_in_use(5000):
            print("Error: Port 5000 is already in use. Please free up the port and try again.")
            sys.exit(1)

        # Start Prometheus metrics server first
        metrics_port = 9091
        start_http_server(metrics_port)
        print(f"Prometheus metrics server started on port {metrics_port}")

        # Start Flask app without debug mode
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)
