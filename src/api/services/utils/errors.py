"""Error handling utilities for S3-compatible APIs."""

import logging
from functools import wraps
from flask import make_response
from .response import format_error_response

logger = logging.getLogger(__name__)

class S3Error(Exception):
    """Base class for S3 API errors."""
    def __init__(self, message, code='InternalError'):
        super().__init__(message)
        self.message = message
        self.code = code

class NoSuchBucket(S3Error):
    """Bucket does not exist."""
    def __init__(self, bucket):
        super().__init__(f"The specified bucket does not exist: {bucket}", "NoSuchBucket")

class NoSuchKey(S3Error):
    """Object key does not exist."""
    def __init__(self, key):
        super().__init__(f"The specified key does not exist: {key}", "NoSuchKey")

class InvalidRequest(S3Error):
    """Invalid request parameters."""
    def __init__(self, message):
        super().__init__(message, "InvalidRequest")

class BucketAlreadyExists(S3Error):
    """Bucket already exists."""
    def __init__(self, bucket):
        super().__init__(f"The requested bucket name is not available: {bucket}", "BucketAlreadyExists")

def handle_s3_errors(aws_style=False):
    """Decorator to handle S3 API errors consistently.
    
    Args:
        aws_style (bool): If True, format errors in AWS S3 style
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except S3Error as e:
                logger.error(f"S3 error in {f.__name__}: {str(e)}")
                return format_error_response(e.code, e.message, aws_style)
            except Exception as e:
                logger.error(f"Unexpected error in {f.__name__}: {str(e)}")
                return format_error_response(
                    'InternalError',
                    str(e) if aws_style else "Internal server error",
                    aws_style
                )
        return wrapped
    return decorator
