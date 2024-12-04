# API Reference

## S3-Compatible API

### Bucket Operations

#### GET /s3/
- **Purpose**: Lists all buckets
- **Response**: XML list of buckets
- **Auth Required**: Yes
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
- **Success Response**: 200 OK with object data
- **Headers**:
  - `Content-Length`: Size in bytes
  - `ETag`: Object hash
  - `Last-Modified`: Timestamp

#### PUT /s3/{bucket}/{key}
- **Purpose**: Uploads an object
- **Auth Required**: Yes
- **Parameters**:
  - `bucket`: Bucket name (required)
  - `key`: Object key (required)
- **Body**: Object data
- **Success Response**: 200 OK
- **Headers**:
  - `ETag`: Object hash

#### DELETE /s3/{bucket}/{key}
- **Purpose**: Deletes an object
- **Auth Required**: Yes
- **Parameters**:
  - `bucket`: Bucket name (required)
  - `key`: Object key (required)
- **Success Response**: 204 No Content

## System Management API

### Storage Management

#### GET /api/v1/storage/status
- **Purpose**: Returns storage system status
- **Auth Required**: Yes
- **Response**: JSON object with system metrics
```json
{
    "total_storage": "1000GB",
    "used_storage": "250GB",
    "node_count": 5,
    "health_status": "healthy"
}
```

#### GET /api/v1/storage/nodes
- **Purpose**: Lists all storage nodes
- **Auth Required**: Yes
- **Response**: JSON array of node information
```json
{
    "nodes": [
        {
            "id": "node-1",
            "status": "active",
            "storage_used": "50GB",
            "cpu_usage": "30%"
        }
    ]
}
```

### Monitoring

#### GET /api/v1/metrics
- **Purpose**: Returns system metrics
- **Auth Required**: Yes
- **Format**: Prometheus-compatible
- **Example Metrics**:
  - `dfs_node_storage_used_bytes`
  - `dfs_node_cpu_usage_percent`
  - `dfs_requests_total`

#### GET /api/v1/health
- **Purpose**: Returns system health status
- **Auth Required**: Yes
- **Response**: JSON health check results
```json
{
    "status": "healthy",
    "components": {
        "storage": "ok",
        "api": "ok",
        "replication": "ok"
    }
}
```

## Error Responses

All endpoints may return these standard error codes:

- `400 Bad Request`: Invalid parameters or request
  ```json
  {
      "error": "InvalidRequest",
      "message": "Invalid bucket name"
  }
  ```

- `401 Unauthorized`: Missing or invalid authentication
  ```json
  {
      "error": "AuthenticationRequired",
      "message": "No authentication credentials provided"
  }
  ```

- `403 Forbidden`: Insufficient permissions
  ```json
  {
      "error": "AccessDenied",
      "message": "Insufficient permissions for this operation"
  }
  ```

- `404 Not Found`: Resource not found
  ```json
  {
      "error": "NotFound",
      "message": "Bucket does not exist"
  }
  ```

- `500 Internal Server Error`: Server-side error
  ```json
  {
      "error": "InternalError",
      "message": "An unexpected error occurred"
  }
  ```

- `503 Service Unavailable`: System temporarily unavailable
  ```json
  {
      "error": "ServiceUnavailable",
      "message": "System is under maintenance"
  }
  ```

## Authentication

All requests must include AWS Signature Version 4 authentication:

### Required Headers
```
Authorization: AWS4-HMAC-SHA256 
    Credential=${ACCESS_KEY}/${DATE}/${REGION}/s3/aws4_request,
    SignedHeaders=host;x-amz-date,
    Signature=${SIGNATURE}
X-Amz-Date: ${TIMESTAMP}
```

### Environment Variables
Required environment variables for authentication:
- `AWS_ACCESS_KEY_ID`: Your access key
- `AWS_SECRET_ACCESS_KEY`: Your secret key
- `AWS_REGION`: Target region (default: us-east-2)