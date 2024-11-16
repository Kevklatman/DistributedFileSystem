from flask import Flask, render_template, jsonify, Response, request
from kubernetes import client, config, utils
from datetime import datetime
import os
import ssl
import urllib3
import requests
from flask_cors import CORS

# Disable SSL warnings
urllib3.disable_warnings()

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
def handle_preflight():
    if request.method == "OPTIONS":
        response = Response()
        response.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin", "*"))
        response.headers.add("Access-Control-Allow-Methods", "DELETE, GET, POST, PUT, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token")
        response.headers.add("Access-Control-Expose-Headers", "ETag, x-amz-request-id, x-amz-id-2")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Access-Control-Max-Age", "3600")
        return response

# Configure Kubernetes client
try:
    # Try to load the local kubeconfig
    config.load_kube_config()
    
    # Configure client with Docker Desktop's Kubernetes API server
    configuration = client.Configuration.get_default_copy()
    configuration.verify_ssl = False
    configuration.host = "https://kubernetes.docker.internal:6443"
    configuration.debug = True
    
    api_client = client.ApiClient(configuration)
    v1 = client.CoreV1Api(api_client)
    print("Successfully connected to Kubernetes API")
except Exception as e:
    print(f"Error configuring Kubernetes client: {e}")
    v1 = None

def get_storage_metrics():
    """Get storage metrics from PersistentVolumeClaims"""
    try:
        if not v1:
            raise Exception("Kubernetes client not configured")
            
        pvcs = v1.list_persistent_volume_claim_for_all_namespaces()
        total_storage = 0
        used_storage = 0
        
        for pvc in pvcs.items:
            if pvc.spec.resources.requests.get('storage'):
                # Convert storage string (e.g., "1Gi") to bytes
                storage_str = pvc.spec.resources.requests['storage']
                storage_value = int(storage_str[:-2])
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
            'total_storage': 'N/A',
            'used_storage': 'N/A',
            'available_storage': 'N/A'
        }

def get_pod_metrics():
    """Get metrics for all pods in the distributed-fs namespace"""
    try:
        if not v1:
            raise Exception("Kubernetes client not configured")
            
        pods = v1.list_namespaced_pod(namespace='distributed-fs')
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/metrics')
def metrics():
    return jsonify({
        'pods': get_pod_metrics(),
        'storage': get_storage_metrics(),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# Proxy routes for other services
@app.route('/web-ui')
@app.route('/web-ui/<path:path>')
def web_ui_proxy(path=''):
    try:
        headers = {key: value for key, value in request.headers if key != 'Host'}
        response = requests.request(
            method=request.method,
            url=f'http://localhost:3000/{path}',
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            verify=False
        )
        proxy_response = Response(response.content, response.status_code)
        for key, value in response.headers.items():
            if key.lower() not in ['content-length', 'connection', 'content-encoding']:
                proxy_response.headers[key] = value
        return proxy_response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/<path:path>')
def api_proxy(path):
    try:
        headers = {key: value for key, value in request.headers if key != 'Host'}
        response = requests.request(
            method=request.method,
            url=f'http://localhost:5555/{path}',
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            verify=False
        )
        proxy_response = Response(response.content, response.status_code)
        for key, value in response.headers.items():
            if key.lower() not in ['content-length', 'connection', 'content-encoding']:
                proxy_response.headers[key] = value
        return proxy_response
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
