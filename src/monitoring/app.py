from flask import Flask, render_template, jsonify, Response, request
from kubernetes import client, config, utils
from datetime import datetime
import os
import ssl
import urllib3
import requests
import time
from flask_cors import CORS
from prometheus_client import Counter, Histogram, start_http_server
import sys

# Disable SSL warnings
urllib3.disable_warnings()

# Initialize Prometheus metrics
REQUEST_COUNT = Counter(
    'dfs_request_total',
    'Total number of requests by endpoint and method',
    ['endpoint', 'method', 'status']
)

REQUEST_LATENCY = Histogram(
    'dfs_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint', 'method']
)

NETWORK_IO = Counter(
    'dfs_network_bytes',
    'Network I/O in bytes',
    ['direction']  # 'in' or 'out'
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

@app.before_request
def before_request():
    request.start_time = time.time()
    if request.content_length:
        NETWORK_IO.labels(direction='in').inc(request.content_length)

@app.after_request
def after_request(response):
    # Record request latency
    latency = time.time() - request.start_time
    REQUEST_LATENCY.labels(
        endpoint=request.endpoint or 'unknown',
        method=request.method
    ).observe(latency)

    # Record request count
    REQUEST_COUNT.labels(
        endpoint=request.endpoint or 'unknown',
        method=request.method,
        status=response.status_code
    ).inc()

    # Record outgoing network bytes
    if response.content_length:
        NETWORK_IO.labels(direction='out').inc(response.content_length)

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

def get_storage_metrics():
    """Get storage metrics from PersistentVolumeClaims"""
    try:
        if not v1:
            print("Kubernetes client not configured, returning default values")
            return {
                'total_storage': '0GB',
                'used_storage': '0GB',
                'available_storage': '0GB'
            }

        pvcs = v1.list_persistent_volume_claim_for_all_namespaces()
        total_storage = 0

        for pvc in pvcs.items:
            if pvc.spec.resources.requests.get('storage'):
                # Convert storage string (e.g., "1Gi") to bytes
                storage_str = pvc.spec.resources.requests['storage']
                storage_value = int(''.join(filter(str.isdigit, storage_str)))
                if storage_str.endswith('Gi'):
                    storage_bytes = storage_value * 1024 * 1024 * 1024
                elif storage_str.endswith('Mi'):
                    storage_bytes = storage_value * 1024 * 1024
                else:
                    storage_bytes = storage_value
                total_storage += storage_bytes

        # Convert bytes to GB for display
        total_storage_gb = total_storage / (1024 * 1024 * 1024)
        used_storage_gb = total_storage_gb * 0.25  # Estimated usage
        available_storage_gb = total_storage_gb - used_storage_gb

        return {
            'total_storage': f'{total_storage_gb:.1f}GB',
            'used_storage': f'{used_storage_gb:.1f}GB',
            'available_storage': f'{available_storage_gb:.1f}GB'
        }
    except Exception as e:
        print(f"Error getting storage metrics: {e}")
        return {
            'total_storage': '0GB',
            'used_storage': '0GB',
            'available_storage': '0GB'
        }

def get_pod_metrics():
    """Get metrics for all pods in the distributed-fs namespace"""
    try:
        if not v1:
            print("Kubernetes client not configured, returning empty pod list")
            return []

        try:
            pods = v1.list_namespaced_pod(namespace='distributed-fs')
        except client.rest.ApiException as e:
            if e.status == 404:
                # Namespace doesn't exist, try default namespace
                pods = v1.list_namespaced_pod(namespace='default')
            else:
                raise

        pod_metrics = []

        for pod in pods.items:
            pod_info = {
                'name': pod.metadata.name,
                'status': pod.status.phase,
                'ip': pod.status.pod_ip or 'N/A',
                'node': pod.spec.node_name or 'N/A',
                'start_time': pod.status.start_time.strftime('%Y-%m-%d %H:%M:%S') if pod.status.start_time else 'N/A',
                'ready': all(cont.ready for cont in pod.status.container_statuses) if pod.status.container_statuses else False
            }
            pod_metrics.append(pod_info)

        return pod_metrics
    except Exception as e:
        print(f"Error getting pod metrics: {e}")
        return []

def get_network_metrics():
    """Get network I/O metrics"""
    try:
        in_bytes = NETWORK_IO.labels(direction='in')._value.get()
        out_bytes = NETWORK_IO.labels(direction='out')._value.get()

        return {
            'bytes_in': f'{in_bytes / (1024*1024):.2f}MB',
            'bytes_out': f'{out_bytes / (1024*1024):.2f}MB',
            'total_bytes': f'{(in_bytes + out_bytes) / (1024*1024):.2f}MB'
        }
    except Exception as e:
        print(f"Error getting network metrics: {e}")
        return {
            'bytes_in': '0MB',
            'bytes_out': '0MB',
            'total_bytes': '0MB'
        }

def get_latency_metrics():
    """Get request latency metrics"""
    try:
        latencies = []
        for sample in REQUEST_LATENCY.collect()[0].samples:
            if sample.name.endswith('_sum'):
                endpoint = dict(sample.labels)['endpoint']
                method = dict(sample.labels)['method']
                latencies.append({
                    'endpoint': endpoint,
                    'method': method,
                    'latency': f'{sample.value*1000:.2f}ms'  # Convert to milliseconds
                })
        return latencies
    except Exception as e:
        print(f"Error getting latency metrics: {e}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/metrics')
def metrics():
    return jsonify({
        'pods': get_pod_metrics(),
        'storage': get_storage_metrics(),
        'network': get_network_metrics(),
        'latency': get_latency_metrics(),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

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

if __name__ == '__main__':
    try:
        # Start the Flask app first
        app.run(host='0.0.0.0', port=5001, debug=True)
    except OSError as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)
