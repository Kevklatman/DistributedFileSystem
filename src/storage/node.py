import os
import time
from flask import Flask, jsonify

app = Flask(__name__)


# Health check endpoint
@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


# Readiness probe endpoint
@app.route("/ready")
def ready():
    return jsonify({"status": "ready"})


if __name__ == "__main__":
    # Get configuration from environment
    node_id = os.getenv("NODE_ID", "unknown")
    pod_ip = os.getenv("POD_IP", "0.0.0.0")

    print(f"Starting storage node {node_id} on {pod_ip}")

    # Create data directory if it doesn't exist
    os.makedirs("/data", exist_ok=True)

    # Start the Flask server
    app.run(host="0.0.0.0", port=8080)
