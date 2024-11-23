from flask import Flask, request, jsonify, Response, make_response, render_template, send_from_directory
from flask_cors import CORS
from flask_restx import Api, Resource, fields
from werkzeug.exceptions import BadRequest
import xmltodict
import datetime
import hashlib
import os
import logging
import sys
import json
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.storage_backend import get_storage_backend
from routes.s3 import s3_api, S3ApiHandler
from routes.aws_s3 import aws_s3_api, AWSS3ApiHandler
from core.fs_manager import FileSystemManager
from core.config import API_HOST, API_PORT, DEBUG

# Configure Flask app
app = Flask(__name__,
           static_url_path='',
           static_folder='static')

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "http://localhost:5000", "http://localhost:8000"],
                            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                            "allow_headers": ["Content-Type", "Authorization"]}})

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize filesystem manager and storage backend
fs_manager = FileSystemManager()
storage_backend = get_storage_backend(fs_manager)

# Initialize S3-compatible API handler and register blueprint
s3_handler = S3ApiHandler(fs_manager)
app.register_blueprint(s3_api, url_prefix='/s3')

# Initialize AWS S3 API handler and register blueprint
aws_s3_handler = AWSS3ApiHandler(fs_manager)
app.register_blueprint(aws_s3_api, url_prefix='/aws-s3')

# Add request logging
@app.before_request
def log_request_info():
    logger.debug('Headers: %s', dict(request.headers))
    logger.debug('Body: %s', request.get_data())

@app.after_request
def after_request(response):
    logger.debug('Response Headers: %s', dict(response.headers))
    return response

# Handle favicon.ico requests
@app.route('/favicon.ico')
def favicon():
    return '', 204  # Return no content

# Initialize Flask-RESTX with Swagger UI
authorizations = {
    'apikey': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'X-Api-Key'
    }
}

api = Api(app, version='1.0',
          title='Distributed File System API',
          description='S3-compatible API for distributed file storage',
          doc='/docs')

# Define namespaces
s3_ns = api.namespace('',
                      description='S3-compatible operations',
                      path='/')

# Define models for request/response documentation
bucket_model = api.model('Bucket', {
    'Name': fields.String(required=True, description='Name of the bucket'),
    'CreationDate': fields.DateTime(description='When the bucket was created'),
    'Region': fields.String(description='Bucket region')
})

object_model = api.model('Object', {
    'Key': fields.String(required=True, description='Object key/path'),
    'Size': fields.Integer(description='Size of object in bytes'),
    'LastModified': fields.DateTime(description='Last modification timestamp'),
    'StorageClass': fields.String(description='Storage class of the object'),
    'VersionId': fields.String(description='Version ID of the object'),
    'ETag': fields.String(description='Entity tag for the object'),
    'ContentType': fields.String(description='MIME type of the object')
})

multipart_model = api.model('MultipartUpload', {
    'UploadId': fields.String(required=True, description='Multipart upload ID'),
    'Key': fields.String(required=True, description='Object key'),
    'Initiated': fields.DateTime(description='When the upload was initiated'),
    'StorageClass': fields.String(description='Storage class for the object'),
    'PartNumber': fields.Integer(description='Part number in multipart upload')
})

versioning_model = api.model('VersioningConfiguration', {
    'Status': fields.String(required=True, description='Versioning state (Enabled/Suspended)'),
    'MfaDelete': fields.String(description='MFA Delete state'),
    'Versions': fields.List(fields.Nested(object_model), description='List of object versions')
})

policy_metrics_model = api.model('PolicyMetrics', {
    'total_policies': fields.Integer(description='Total number of policies'),
    'active_policies': fields.Integer(description='Number of active policies'),
    'policy_overrides': fields.Integer(description='Number of policy overrides'),
    'policy_evaluations': fields.Integer(description='Total policy evaluations'),
    'cache_hits': fields.Integer(description='Policy cache hit count'),
    'cache_misses': fields.Integer(description='Policy cache miss count')
})

dashboard_metrics_model = api.model('DashboardMetrics', {
    'storage_usage': fields.Float(description='Total storage usage in bytes'),
    'object_count': fields.Integer(description='Total number of objects'),
    'request_rate': fields.Float(description='Requests per second'),
    'error_rate': fields.Float(description='Errors per second'),
    'bandwidth': fields.Float(description='Current bandwidth usage (MB/s)'),
    'latency': fields.Float(description='Average request latency (ms)'),
    'availability': fields.Float(description='System availability percentage')
})

error_model = api.model('Error', {
    'Code': fields.String(required=True, description='Error code'),
    'Message': fields.String(required=True, description='Error message'),
    'RequestId': fields.String(description='Unique request identifier'),
    'Resource': fields.String(description='Affected resource'),
    'TimeStamp': fields.DateTime(description='When the error occurred')
})

# Add CORS preflight handler
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin", "*"))
        response.headers.add("Access-Control-Allow-Methods", "DELETE, GET, POST, PUT, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token")
        response.headers.add("Access-Control-Expose-Headers", "ETag, x-amz-request-id, x-amz-id-2")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Access-Control-Max-Age", "3600")
        return response

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"Error: {str(error)}")
    return jsonify({'error': str(error)}), 500

# Add back the index route
@app.route('/')
def index():
    """Serve the web UI"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory(app.static_folder, path)

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'available',
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
    })

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
            'policy_distribution': pattern_types,
            'total_policies': len(policy_data.get('path_overrides', [])),
            'ml_policy_accuracy': 0.92,  # Sample value
            'policy_changes_24h': 156,   # Sample value
            'data_moved_24h_gb': 250.5   # Sample value
        }
    except Exception as e:
        logger.error(f"Error getting policy metrics: {str(e)}")
        return {
            'policy_distribution': {'error': 'Failed to load policy data'},
            'total_policies': 0,
            'ml_policy_accuracy': 0,
            'policy_changes_24h': 0,
            'data_moved_24h_gb': 0
        }

# Dashboard metrics endpoint
@app.route('/dashboard/metrics', methods=['GET'])
def get_dashboard_metrics():
    """Get all dashboard metrics"""
    try:
        logger.debug('Fetching dashboard metrics')

        # Get storage backend metrics
        storage = storage_backend
        io_metrics = storage.get_io_metrics()

        # Get policy metrics
        policy_metrics = get_policy_metrics()

        metrics = {
            'health': {
                'cpu_usage': 45.2,  # TODO: Get from system
                'memory_usage': 62.8,  # TODO: Get from system
                'io_latency_ms': io_metrics['latency_ms'],
                'network_bandwidth_mbps': io_metrics['bandwidth_mbps'],
                'error_count': 0,
                'warning_count': 2,
                'status': 'healthy',
                'last_updated': datetime.datetime.now(datetime.timezone.utc).isoformat()
            },
            'storage': {
                'total_capacity_gb': 1000.0,
                'used_capacity_gb': 450.0,
                'available_capacity_gb': 550.0,
                'usage_percent': 45.0,
                'dedup_ratio': 2.5,
                'compression_ratio': 3.0,
                'iops': io_metrics['iops'],
                'throughput_mbps': io_metrics['throughput_mbps'],
                'bytes_in': io_metrics['bytes_in'],
                'bytes_out': io_metrics['bytes_out'],
                'last_updated': datetime.datetime.now(datetime.timezone.utc).isoformat()
            },
            'cost': {
                'total_cost_month': 1250.0,
                'savings_from_tiering': 450.0,
                'savings_from_dedup': 300.0,
                'savings_from_compression': 200.0,
                'total_savings': 950.0,
                'last_updated': datetime.datetime.now(datetime.timezone.utc).isoformat()
            },
            'policy': policy_metrics,
            'recommendations': [
                {
                    'category': 'performance',
                    'severity': 'warning',
                    'title': 'High I/O Latency',
                    'description': 'Storage tier showing increased latency',
                    'suggestions': [
                        'Consider moving frequently accessed data to SSD tier',
                        'Review application I/O patterns'
                    ],
                    'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat()
                },
                {
                    'category': 'policy',
                    'severity': 'info',
                    'title': 'Policy Distribution',
                    'description': f'Current policy distribution: {policy_metrics["policy_distribution"]}',
                    'suggestions': [
                        'Review policy patterns for optimal data placement',
                        'Consider consolidating similar policies'
                    ],
                    'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            ]
        }

        logger.debug(f'Returning metrics: {metrics}')
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        logger.exception(e)
        return jsonify({'error': str(e)}), 500

# Define Prometheus metrics
BYTES_IN = Counter('storage_bytes_in_total', 'Total bytes written to storage')
BYTES_OUT = Counter('storage_bytes_out_total', 'Total bytes read from storage')
LATENCY = Gauge('storage_latency_milliseconds', 'Storage operation latency in milliseconds')
IOPS = Gauge('storage_iops', 'Storage IOPS')
BANDWIDTH = Gauge('storage_bandwidth_mbps', 'Storage bandwidth in MB/s')
THROUGHPUT = Gauge('storage_throughput_mbps', 'Storage throughput in MB/s')

# Metrics endpoint
@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    try:
        # Update Prometheus metrics from storage backend
        BYTES_IN._value.set(storage_backend.io_metrics['bytes_in'])
        BYTES_OUT._value.set(storage_backend.io_metrics['bytes_out'])
        LATENCY.set(storage_backend.io_metrics['latency_ms'])
        IOPS.set(storage_backend.io_metrics['iops'])
        BANDWIDTH.set(storage_backend.io_metrics['bandwidth_mbps'])
        THROUGHPUT.set(storage_backend.io_metrics['throughput_mbps'])

        # Check Accept header for format
        accept = request.headers.get('Accept', '')
        if 'application/json' in accept:
            # Return JSON format
            return jsonify({
                'storage': {
                    'bytes_in': storage_backend.io_metrics['bytes_in'],
                    'bytes_out': storage_backend.io_metrics['bytes_out'],
                    'latency_ms': storage_backend.io_metrics['latency_ms'],
                    'iops': storage_backend.io_metrics['iops'],
                    'bandwidth_mbps': storage_backend.io_metrics['bandwidth_mbps'],
                    'throughput_mbps': storage_backend.io_metrics['throughput_mbps']
                }
            })
        else:
            # Return Prometheus format
            return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    except Exception as e:
        logger.error(f"Error in metrics endpoint: {e}")
        return jsonify({"error": str(e)}), 500

# Decorate existing routes with API documentation
@s3_ns.route('/')
class BucketList(Resource):
    @s3_ns.doc('list_buckets',
               description='List all buckets',
               responses={
                   200: ('Success', [bucket_model]),
                   500: ('Server Error', error_model)
               })
    def get(self):
        """List all buckets"""
        return s3_handler.list_buckets()

@s3_ns.route('/<string:bucket_name>')
@s3_ns.param('bucket_name', 'The bucket name')
class BucketOperations(Resource):
    @s3_ns.doc('create_bucket',
               description='Create a new bucket',
               responses={
                   200: ('Success', bucket_model),
                   400: ('Invalid Request', error_model),
                   409: ('Bucket Already Exists', error_model),
                   500: ('Server Error', error_model)
               })
    def put(self, bucket_name):
        """Create a new bucket"""
        return s3_handler.create_bucket(bucket_name)

    @s3_ns.doc('delete_bucket',
               description='Delete a bucket',
               responses={
                   204: 'Success - Bucket Deleted',
                   404: ('Bucket Not Found', error_model),
                   409: ('Bucket Not Empty', error_model),
                   500: ('Server Error', error_model)
               })
    def delete(self, bucket_name):
        """Delete a bucket"""
        return s3_handler.delete_bucket(bucket_name)

    @s3_ns.doc('list_objects',
               description='List objects in bucket',
               responses={
                   200: ('Success', [object_model]),
                   404: ('Bucket Not Found', error_model),
                   500: ('Server Error', error_model)
               })
    def get(self, bucket_name):
        """List objects in bucket"""
        return s3_handler.list_objects(bucket_name)

@s3_ns.route('/<string:bucket_name>/<string:object_key>')
@s3_ns.param('bucket_name', 'The bucket name')
@s3_ns.param('object_key', 'The object key')
class ObjectOperations(Resource):
    @s3_ns.doc('get_object',
               description='Download an object',
               responses={
                   200: 'Success - Object Data Returned',
                   404: ('Object Not Found', error_model),
                   500: ('Server Error', error_model)
               })
    def get(self, bucket_name, object_key):
        """Download an object"""
        return s3_handler.get_object(bucket_name, object_key)

    @s3_ns.doc('put_object',
               description='Upload an object',
               responses={
                   200: 'Success - Object Uploaded',
                   400: ('Invalid Request', error_model),
                   404: ('Bucket Not Found', error_model),
                   500: ('Server Error', error_model)
               })
    def put(self, bucket_name, object_key):
        """Upload an object"""
        return s3_handler.put_object(bucket_name, object_key, request.data)

    @s3_ns.doc('delete_object',
               description='Delete an object',
               responses={
                   204: 'Success - Object Deleted',
                   404: ('Object Not Found', error_model),
                   500: ('Server Error', error_model)
               })
    def delete(self, bucket_name, object_key):
        """Delete an object"""
        return s3_handler.delete_object(bucket_name, object_key)

    @s3_ns.doc('head_object',
               description='Get object metadata',
               responses={
                   200: ('Success', object_model),
                   404: ('Object Not Found', error_model),
                   500: ('Server Error', error_model)
               })
    def head(self, bucket_name, object_key):
        """Get object metadata"""
        return s3_handler.head_object(bucket_name, object_key)

# Serve Swagger UI files
@app.route('/swaggerui/<path:path>')
def swagger_ui(path):
    return send_from_directory('static/swaggerui', path)

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            if isinstance(obj, datetime.datetime):
                return obj.isoformat()
            elif isinstance(obj, datetime.date):
                return obj.isoformat()
            elif isinstance(obj, datetime.time):
                return obj.isoformat()
            return json.JSONEncoder.default(self, obj)
        except Exception as e:
            logger.error(f"Error encoding JSON: {e}")
            return str(obj)  # Fallback to string representation

app.json_encoder = JSONEncoder

if __name__ == '__main__':
    # Ensure the buckets directory exists
    os.makedirs('buckets', exist_ok=True)

    print(f"Starting server on {API_HOST}:{API_PORT}")
    app.run(host=API_HOST, port=API_PORT, debug=DEBUG)
