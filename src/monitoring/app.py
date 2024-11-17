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
        "origins": ["http://localhost:3000", "http://localhost:5000", "http://localhost:5555"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"],
        "expose_headers": ["ETag", "x-amz-request-id", "x-amz-id-2"],
        "supports_credentials": True
    }
})

def update_system_metrics():
    """Update system metrics including CPU and memory"""
    try:
        # CPU metrics
        CPU_USAGE.set(psutil.cpu_percent(interval=1))
        
        # Memory metrics
        memory = psutil.virtual_memory()
        MEMORY_USAGE.labels(type='total').set(memory.total)
        MEMORY_USAGE.labels(type='used').set(memory.used)
        MEMORY_USAGE.labels(type='available').set(memory.available)
        
        # Storage metrics
        storage = psutil.disk_usage('/Users/kevinklatman/Development/Code/DistributedFileSystem/storage')
        STORAGE_TOTAL.set(storage.total)
        STORAGE_USED.set(storage.used)
        STORAGE_AVAILABLE.set(storage.free)
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

@app.route('/api/metrics')
def api_metrics():
    """API endpoint for dashboard metrics"""
    try:
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        storage = psutil.disk_usage('/Users/kevinklatman/Development/Code/DistributedFileSystem/storage')
        
        # Get network metrics
        network_in = NETWORK_IO.labels(direction='in')._value.get()
        network_out = NETWORK_IO.labels(direction='out')._value.get()
        
        # Get pod metrics
        pods = []
        try:
            config.load_kube_config()
            v1 = client.CoreV1Api()
            pod_list = v1.list_namespaced_pod(namespace='default')
            for pod in pod_list.items:
                pods.append({
                    'name': pod.metadata.name,
                    'status': pod.status.phase,
                    'ip': pod.status.pod_ip or 'None',
                    'node': pod.spec.node_name or 'None',
                    'start_time': pod.status.start_time.strftime('%Y-%m-%d %H:%M:%S') if pod.status.start_time else 'Unknown'
                })
        except Exception as e:
            print(f"Error getting pod metrics: {e}", file=sys.stderr)
        
        return jsonify({
            'system': {
                'cpu_percent': cpu_percent,
                'memory': {
                    'total': memory.total,
                    'used': memory.used,
                    'available': memory.available,
                    'percent': memory.percent
                }
            },
            'storage': {
                'total': storage.total,
                'used': storage.used,
                'available': storage.free,
                'percent': storage.percent
            },
            'network': {
                'bytes_in': network_in,
                'bytes_out': network_out,
                'total': network_in + network_out
            },
            'pods': pods,
            'timestamp': datetime.now().isoformat()
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

if __name__ == '__main__':
    try:
        # Start Prometheus metrics server first
        metrics_port = 9091
        try:
            start_http_server(metrics_port, registry=REGISTRY)
            print(f"Prometheus metrics server started on port {metrics_port}")
        except Exception as e:
            print(f"Warning: Could not start Prometheus metrics server: {e}")
            
        # Start the Flask app
        app.run(host='0.0.0.0', port=5001, debug=True)
    except OSError as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)
