import json
import datetime
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

# Define Prometheus metrics
BYTES_IN = Counter('storage_bytes_in_total', 'Total bytes written to storage')
BYTES_OUT = Counter('storage_bytes_out_total', 'Total bytes read from storage')
LATENCY = Gauge('storage_latency_milliseconds', 'Storage operation latency in milliseconds')
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests')
ERROR_COUNT = Counter('http_errors_total', 'Total HTTP errors')

def get_policy_metrics():
    """Get policy engine metrics including policy overrides analysis"""
    try:
        with open('config/policy_overrides.json', 'r') as f:
            policy_data = json.load(f)

        # Analyze policy patterns
        pattern_types = {
            'high-priority': 0,
            'time-sensitive': 0,
            'archive': 0,
            'other': 0
        }

        for policy in policy_data.get('path_overrides', []):
            pattern = policy.get('pattern', '')
            if 'high-priority' in pattern:
                pattern_types['high-priority'] += 1
            elif 'time-sensitive' in pattern:
                pattern_types['time-sensitive'] += 1
            elif 'archive' in pattern:
                pattern_types['archive'] += 1
            else:
                pattern_types['other'] += 1

        return {
            'total_policies': len(policy_data.get('path_overrides', [])),
            'active_policies': len([p for p in policy_data.get('path_overrides', []) if p.get('active', True)]),
            'policy_overrides': sum(pattern_types.values()),
            'policy_evaluations': policy_data.get('total_evaluations', 0),
            'cache_hits': policy_data.get('cache_hits', 0),
            'cache_misses': policy_data.get('cache_misses', 0),
            'pattern_analysis': pattern_types
        }
    except Exception as e:
        return {
            'error': str(e),
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

def get_dashboard_metrics():
    """Get real-time dashboard metrics"""
    try:
        # Calculate storage metrics
        storage_usage = BYTES_IN._value.get() - BYTES_OUT._value.get()
        request_rate = REQUEST_COUNT._value.get() / 60  # requests per minute
        error_rate = ERROR_COUNT._value.get() / 60  # errors per minute
        latency = LATENCY._value.get()

        # Calculate availability (successful requests / total requests)
        total_requests = REQUEST_COUNT._value.get()
        total_errors = ERROR_COUNT._value.get()
        availability = ((total_requests - total_errors) / total_requests * 100) if total_requests > 0 else 100.0

        return {
            'storage_usage': storage_usage,
            'request_rate': request_rate,
            'error_rate': error_rate,
            'bandwidth': (BYTES_IN._value.get() + BYTES_OUT._value.get()) / (1024 * 1024),  # MB/s
            'latency': latency,
            'availability': availability,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            'error': str(e),
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
