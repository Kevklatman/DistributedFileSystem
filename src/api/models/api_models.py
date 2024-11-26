from flask_restx import fields


def create_api_models(api):
    """Create and return all API models"""

    bucket_model = api.model(
        "Bucket",
        {
            "Name": fields.String(required=True, description="Name of the bucket"),
            "CreationDate": fields.DateTime(description="When the bucket was created"),
            "Region": fields.String(description="Bucket region"),
        },
    )

    object_model = api.model(
        "Object",
        {
            "Key": fields.String(required=True, description="Object key/path"),
            "Size": fields.Integer(description="Size of object in bytes"),
            "LastModified": fields.DateTime(description="Last modification timestamp"),
            "StorageClass": fields.String(description="Storage class of the object"),
            "VersionId": fields.String(description="Version ID of the object"),
            "ETag": fields.String(description="Entity tag for the object"),
            "ContentType": fields.String(description="MIME type of the object"),
        },
    )

    multipart_model = api.model(
        "MultipartUpload",
        {
            "UploadId": fields.String(required=True, description="Multipart upload ID"),
            "Key": fields.String(required=True, description="Object key"),
            "Initiated": fields.DateTime(description="When the upload was initiated"),
            "StorageClass": fields.String(description="Storage class for the object"),
            "PartNumber": fields.Integer(description="Part number in multipart upload"),
        },
    )

    versioning_model = api.model(
        "VersioningConfiguration",
        {
            "Status": fields.String(
                required=True, description="Versioning state (Enabled/Suspended)"
            ),
            "MfaDelete": fields.String(description="MFA Delete state"),
            "Versions": fields.List(
                fields.Nested(object_model), description="List of object versions"
            ),
        },
    )

    policy_metrics_model = api.model(
        "PolicyMetrics",
        {
            "total_policies": fields.Integer(description="Total number of policies"),
            "active_policies": fields.Integer(description="Number of active policies"),
            "policy_overrides": fields.Integer(
                description="Number of policy overrides"
            ),
            "policy_evaluations": fields.Integer(
                description="Total policy evaluations"
            ),
            "cache_hits": fields.Integer(description="Policy cache hit count"),
            "cache_misses": fields.Integer(description="Policy cache miss count"),
        },
    )

    dashboard_metrics_model = api.model(
        "DashboardMetrics",
        {
            "storage_usage": fields.Float(description="Total storage usage in bytes"),
            "object_count": fields.Integer(description="Total number of objects"),
            "request_rate": fields.Float(description="Requests per second"),
            "error_rate": fields.Float(description="Errors per second"),
            "bandwidth": fields.Float(description="Current bandwidth usage (MB/s)"),
            "latency": fields.Float(description="Average request latency (ms)"),
            "availability": fields.Float(description="System availability percentage"),
        },
    )

    error_model = api.model(
        "Error",
        {
            "Code": fields.String(required=True, description="Error code"),
            "Message": fields.String(required=True, description="Error message"),
            "RequestId": fields.String(description="Unique request identifier"),
            "Resource": fields.String(description="Affected resource"),
            "TimeStamp": fields.DateTime(description="When the error occurred"),
        },
    )

    return {
        "bucket_model": bucket_model,
        "object_model": object_model,
        "multipart_model": multipart_model,
        "versioning_model": versioning_model,
        "policy_metrics_model": policy_metrics_model,
        "dashboard_metrics_model": dashboard_metrics_model,
        "error_model": error_model,
    }
