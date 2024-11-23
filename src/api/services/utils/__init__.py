"""Utility modules for S3-compatible APIs."""

from .response import (
    format_error_response,
    format_list_buckets_response,
    format_list_objects_response,
    format_object_response,
    generate_request_id
)

from .xml import (
    parse_xml_request,
    parse_multipart_complete,
    parse_versioning_config
)

from .errors import (
    S3Error,
    NoSuchBucket,
    NoSuchKey,
    InvalidRequest,
    BucketAlreadyExists,
    handle_s3_errors
)

__all__ = [
    # Response formatting
    'format_error_response',
    'format_list_buckets_response',
    'format_list_objects_response',
    'format_object_response',
    'generate_request_id',
    
    # XML handling
    'parse_xml_request',
    'parse_multipart_complete',
    'parse_versioning_config',
    
    # Error handling
    'S3Error',
    'NoSuchBucket',
    'NoSuchKey',
    'InvalidRequest',
    'BucketAlreadyExists',
    'handle_s3_errors'
]
