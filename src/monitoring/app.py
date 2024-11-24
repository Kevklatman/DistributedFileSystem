"""
Monitoring application for the distributed file system.
"""
from flask import Flask, render_template, jsonify, Response, request
from kubernetes import client
from datetime import datetime
import os
import urllib3
import requests
import time
from flask_cors import CORS
import sys
import psutil
import json
import socket
import traceback
import logging
import threading

from src.storage.metrics.collector import SystemMetricsCollector
# Create a logger
logger = logging.getLogger(__name__)

# Disable SSL warnings
urllib3.disable_warnings()

# Initialize Flask app with CORS and templates
app = Flask(__name__,
           template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'),
           static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static'))
CORS(app)

# Initialize metrics collector
metrics = SystemMetricsCollector(
    instance_id=socket.gethostname()
)

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
            start_time = time.time()
            request.start_time = start_time
            app.request_queue.add_request({
                'path': request.path,
                'method': request.method,
                'time': start_time
            })
            metrics.update_queue_length(app.request_queue.get_length())
    except Exception as e:
        logger.error(f"Error tracking request: {e}")

@app.after_request
def process_request(response):
    """Process completed requests"""
    try:
        if not request.path.startswith(('/metrics', '/static')):
            duration = time.time() - request.start_time
            metrics.record_request(
                endpoint=request.path,
                method=request.method,
                duration=duration,
                error=str(response.status_code) if response.status_code >= 400 else None
            )
            app.request_queue.remove_request()
            metrics.update_queue_length(app.request_queue.get_length())
    except Exception as e:
        logger.error(f"Error processing request: {e}")
    return response

def update_system_metrics():
    """Update system metrics periodically"""
    while True:
        try:
            metrics.update_system_metrics()
            metrics.update_storage_metrics()
            metrics.update_network_metrics()
            time.sleep(15)  # Update every 15 seconds
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")
            time.sleep(5)  # Shorter sleep on error

# Start system metrics collection in a background thread
metrics_thread = threading.Thread(target=update_system_metrics, daemon=True)
metrics_thread.start()

@app.route('/')
def index():
    """Serve the main dashboard page"""
    return render_template('index.html')

@app.route('/metrics')
def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(metrics.get_metrics(), mimetype="text/plain")

@app.route('/api/metrics')
def api_metrics():
    """API metrics endpoint for the dashboard"""
    try:
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': {
                'system': {
                    'cpu': psutil.cpu_percent(),
                    'memory': psutil.virtual_memory().percent,
                    'disk': psutil.disk_usage('/').percent
                },
                'queue': {
                    'length': app.request_queue.get_length()
                }
            }
        })
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Basic health checks
        cpu_ok = psutil.cpu_percent() < 90
        memory = psutil.virtual_memory()
        memory_ok = memory.available > (0.1 * memory.total)  # At least 10% free
        disk = psutil.disk_usage('/')
        disk_ok = disk.free > (0.1 * disk.total)  # At least 10% free

        status = 'healthy' if all([cpu_ok, memory_ok, disk_ok]) else 'degraded'
        
        return jsonify({
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {
                'cpu': 'ok' if cpu_ok else 'warning',
                'memory': 'ok' if memory_ok else 'warning',
                'disk': 'ok' if disk_ok else 'warning'
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    try:
        # Start Flask app
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        sys.exit(1)
