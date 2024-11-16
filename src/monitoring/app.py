from flask import Flask, render_template, jsonify
from datetime import datetime
import os

app = Flask(__name__)

def get_storage_metrics():
    """Get storage metrics"""
    return {
        'total_storage': '100GB',
        'used_storage': '25GB',
        'available_storage': '75GB'
    }

def get_pod_metrics():
    """Get pod metrics"""
    return [
        {
            'name': 'dfs-api-pod-1',
            'status': 'Running',
            'ip': '10.0.0.1',
            'node': 'node-1',
            'start_time': '2024-01-01 00:00:00'
        },
        {
            'name': 'dfs-storage-pod-1',
            'status': 'Running',
            'ip': '10.0.0.2',
            'node': 'node-1',
            'start_time': '2024-01-01 00:00:00'
        }
    ]

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
