from flask import Flask, render_template, jsonify
from kubernetes import client, config
import os
import requests
from datetime import datetime
import prometheus_client
from prometheus_client import Counter, Gauge, generate_latest

app = Flask(__name__)

# Initialize Prometheus metrics
pod_status = Gauge('dfs_pod_status', 'Status of DFS pods', ['pod_name'])
api_requests = Counter('dfs_api_requests_total', 'Total API requests', ['endpoint'])
storage_usage = Gauge('dfs_storage_usage_bytes', 'Storage usage in bytes')

try:
    # Try to load in-cluster config
    config.load_incluster_config()
except config.ConfigException:
    # Fall back to local kubeconfig
    config.load_kube_config()

v1 = client.CoreV1Api()

def get_pod_metrics():
    """Get metrics for all pods in the distributed-fs namespace"""
    try:
        pods = v1.list_namespaced_pod(namespace='distributed-fs')
        pod_metrics = []
        
        for pod in pods.items:
            status = pod.status.phase
            pod_status.labels(pod_name=pod.metadata.name).set(1 if status == 'Running' else 0)
            
            pod_info = {
                'name': pod.metadata.name,
                'status': status,
                'ip': pod.status.pod_ip,
                'node': pod.spec.node_name,
                'start_time': pod.status.start_time.strftime('%Y-%m-%d %H:%M:%S') if pod.status.start_time else 'N/A',
                'ready': all(cont.ready for cont in pod.status.container_statuses) if pod.status.container_statuses else False
            }
            pod_metrics.append(pod_info)
            
        return pod_metrics
    except Exception as e:
        print(f"Error getting pod metrics: {e}")
        return []

def get_storage_metrics():
    """Get storage metrics from the API pods"""
    try:
        # You would implement this based on your specific storage metrics
        # For now, returning dummy data
        return {
            'total_storage': '100GB',
            'used_storage': '25GB',
            'available_storage': '75GB'
        }
    except Exception as e:
        print(f"Error getting storage metrics: {e}")
        return {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/metrics')
def metrics():
    pod_metrics = get_pod_metrics()
    storage_metrics = get_storage_metrics()
    
    return jsonify({
        'pods': pod_metrics,
        'storage': storage_metrics,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/metrics')
def prometheus_metrics():
    """Endpoint for Prometheus metrics"""
    return generate_latest()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
