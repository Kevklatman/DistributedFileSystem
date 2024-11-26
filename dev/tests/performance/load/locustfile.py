from locust import HttpUser, task, between, events
from prometheus_client import Counter, Histogram, start_http_server
import random
import json

# Initialize Prometheus metrics
REQUEST_COUNT = Counter(
    "dfs_request_count", "Number of requests", ["operation", "status"]
)
REQUEST_LATENCY = Histogram(
    "dfs_request_latency_seconds", "Request latency", ["operation"]
)

# Start Prometheus metrics server on port 9100
start_http_server(9100)


# Event handlers for metrics
@events.request.add_listener
def request_handler(
    request_type, name, response_time, response_length, exception, **kwargs
):
    operation = name.split("/")[-1]  # Extract operation from URL
    status = "success" if exception is None else "failure"
    REQUEST_COUNT.labels(operation=operation, status=status).inc()
    REQUEST_LATENCY.labels(operation=operation).observe(response_time)


class DFSUser(HttpUser):
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    def on_start(self):
        """Initialize test data"""
        self.test_data = b"Test data content " * 1000  # 16KB of test data
        self.file_ids = []

    @task(3)
    def write_file(self):
        """Simulate write operations"""
        file_id = f"test_file_{random.randint(1, 1000)}"
        headers = {
            "X-Edge-Device-Type": random.choice(["mobile", "iot", "laptop"]),
            "X-Battery-Level": str(random.randint(20, 100)),
            "X-Available-Bandwidth": str(random.randint(100, 1000)),
            "X-Latency-Requirement": str(random.randint(50, 500)),
            "X-Processing-Power": str(random.random()),
            "X-Device-Location": random.choice(["us-west", "us-east", "eu-central"]),
        }

        response = self.client.post(
            f"/write/{file_id}", data=self.test_data, headers=headers
        )

        if response.status_code == 200:
            self.file_ids.append(file_id)

    @task(5)
    def read_file(self):
        """Simulate read operations"""
        if not self.file_ids:
            return

        file_id = random.choice(self.file_ids)
        consistency = random.choice(["strong", "quorum", "eventual"])
        headers = {
            "X-Edge-Device-Type": random.choice(["mobile", "iot", "laptop"]),
            "X-Battery-Level": str(random.randint(20, 100)),
            "X-Available-Bandwidth": str(random.randint(100, 1000)),
            "X-Latency-Requirement": str(random.randint(50, 500)),
            "X-Processing-Power": str(random.random()),
            "X-Device-Location": random.choice(["us-west", "us-east", "eu-central"]),
        }

        self.client.get(f"/read/{file_id}?consistency={consistency}", headers=headers)

    @task(1)
    def list_files(self):
        """Simulate listing operations"""
        self.client.get("/list")

    @task(1)
    def check_health(self):
        """Simulate health check operations"""
        self.client.get("/health")
