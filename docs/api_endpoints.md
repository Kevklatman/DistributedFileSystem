# API Reference

## S3-Compatible API

### Bucket Operations

#### GET /s3/
- **Purpose**: Lists all buckets
- **Response**: XML list of buckets
- **Auth Required**: Yes
- **Headers**:
  - `Content-Type`: application/xml
- **Example Response**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<ListAllMyBucketsResult>
    <Buckets>
        <Bucket>
            <Name>example-bucket</Name>
            <CreationDate>2024-01-01T00:00:00.000Z</CreationDate>
        </Bucket>
    </Buckets>
</ListAllMyBucketsResult>
```

#### PUT /s3/{bucket}
- **Purpose**: Creates a new bucket
- **Auth Required**: Yes
- **Parameters**:
  - `bucket`: Bucket name (required)
- **Headers**:
  - `Content-Type`: application/xml
- **Success Response**: 200 OK

#### DELETE /s3/{bucket}
- **Purpose**: Deletes a bucket
- **Auth Required**: Yes
- **Parameters**:
  - `bucket`: Bucket name (required)
- **Success Response**: 204 No Content

### Object Operations

#### GET /s3/{bucket}/{key}
- **Purpose**: Retrieves an object
- **Auth Required**: Yes
- **Parameters**:
  - `bucket`: Bucket name (required)
  - `key`: Object key (required)
- **Query Parameters**:
  - `versionId`: Version of the object to retrieve (optional)
  - `partNumber`: Part number for multipart objects (optional)
- **Success Response**: 200 OK with object data
- **Headers**:
  - `Content-Type`: [Object MIME type]
  - `Content-Length`: Size in bytes
  - `ETag`: Object hash
  - `Last-Modified`: Timestamp
  - `x-amz-version-id`: Version ID (if versioning enabled)

#### PUT /s3/{bucket}/{key}
- **Purpose**: Uploads an object
- **Auth Required**: Yes
- **Parameters**:
  - `bucket`: Bucket name (required)
  - `key`: Object key (required)
- **Headers**:
  - `Content-Type`: [Object MIME type]
  - `Content-Length`: Size in bytes
  - `x-amz-storage-class`: Storage class (optional)
- **Body**: Object data
- **Success Response**: 200 OK
- **Response Headers**:
  - `ETag`: Object hash
  - `x-amz-version-id`: Version ID (if versioning enabled)

#### DELETE /s3/{bucket}/{key}
- **Purpose**: Deletes an object
- **Auth Required**: Yes
- **Parameters**:
  - `bucket`: Bucket name (required)
  - `key`: Object key (required)
- **Query Parameters**:
  - `versionId`: Version to delete (optional)
- **Success Response**: 204 No Content

## System Management API

### Storage Management

#### GET /api/v1/storage/status
- **Purpose**: Returns storage system status
- **Auth Required**: Yes
- **Headers**:
  - `Content-Type`: application/json
- **Response**: JSON object with system metrics
```json
{
    "total_storage": "1000GB",
    "used_storage": "250GB",
    "node_count": 5,
    "health_status": "healthy",
    "uptime": "10d 4h 30m",
    "iops": {
        "read": 1000,
        "write": 500
    }
}
```

#### GET /api/v1/storage/nodes
- **Purpose**: Lists all storage nodes
- **Auth Required**: Yes
- **Headers**:
  - `Content-Type`: application/json
- **Response**: JSON array of node information
```json
{
    "nodes": [
        {
            "id": "node-1",
            "status": "active",
            "storage_used": "50GB",
            "storage_total": "100GB",
            "cpu_usage": "30%",
            "memory_usage": "45%",
            "network": {
                "in_bytes": 1024000,
                "out_bytes": 2048000
            }
        }
    ]
}
```

### Monitoring

#### GET /api/v1/metrics
- **Purpose**: Returns system metrics
- **Auth Required**: Yes
- **Headers**:
  - `Content-Type`: text/plain
- **Format**: Prometheus-compatible
- **Example Metrics**:
  - `dfs_node_storage_used_bytes`
  - `dfs_node_cpu_usage_percent`
  - `dfs_requests_total`
  - `dfs_request_duration_seconds`
  - `dfs_replication_lag_seconds`

#### GET /api/v1/health
- **Purpose**: Returns system health status
- **Auth Required**: Yes
- **Headers**:
  - `Content-Type`: application/json
- **Response**: JSON health check results
```json
{
    "status": "healthy",
    "components": {
        "storage": {
            "status": "ok",
            "message": "All storage nodes operational"
        },
        "api": {
            "status": "ok",
            "latency": "5ms"
        },
        "replication": {
            "status": "ok",
            "lag": "0.5s"
        }
    },
    "last_check": "2024-01-01T00:00:00Z"
}
```

## Error Responses

All endpoints may return these standard error codes:

- `400 Bad Request`: Invalid parameters or request
  ```json
  {
      "error": "InvalidRequest",
      "message": "Invalid bucket name",
      "request_id": "52sdj3-23d32d-232s",
      "code": "InvalidBucketName"
  }
  ```

- `401 Unauthorized`: Missing or invalid authentication
  ```json
  {
      "error": "AuthenticationRequired",
      "message": "No authentication credentials provided",
      "request_id": "52sdj3-23d32d-232s",
      "code": "MissingAuth"
  }
  ```

- `403 Forbidden`: Insufficient permissions
  ```json
  {
      "error": "AccessDenied",
      "message": "Insufficient permissions for this operation",
      "request_id": "52sdj3-23d32d-232s",
      "code": "AccessDenied"
  }
  ```

- `404 Not Found`: Resource not found
  ```json
  {
      "error": "NotFound",
      "message": "Bucket does not exist",
      "request_id": "52sdj3-23d32d-232s",
      "code": "NoSuchBucket"
  }
  ```

- `500 Internal Server Error`: Server-side error
  ```json
  {
      "error": "InternalError",
      "message": "An unexpected error occurred",
      "request_id": "52sdj3-23d32d-232s",
      "code": "InternalError"
  }
  ```

- `503 Service Unavailable`: System temporarily unavailable
  ```json
  {
      "error": "ServiceUnavailable",
      "message": "System is under maintenance",
      "request_id": "52sdj3-23d32d-232s",
      "code": "ServiceUnavailable"
  }
  ```

## Authentication

All requests must include AWS Signature Version 4 authentication:

### Required Headers
```
Authorization: AWS4-HMAC-SHA256 
    Credential=${ACCESS_KEY}/${DATE}/${REGION}/s3/aws4_request,
    SignedHeaders=host;x-amz-date;content-type,
    Signature=${SIGNATURE}
X-Amz-Date: ${TIMESTAMP}
Content-Type: [Request content type]
```

### Environment Variables
Required environment variables for authentication:
- `AWS_ACCESS_KEY_ID`: Your access key
- `AWS_SECRET_ACCESS_KEY`: Your secret key
- `AWS_REGION`: Target region (default: us-east-2)