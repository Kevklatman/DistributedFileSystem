"""Response formatting utilities for S3-compatible APIs."""

from flask import make_response
import xmltodict
import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)

def generate_request_id():
    """Generate a unique request ID for AWS-style responses."""
    return hashlib.md5(datetime.datetime.now(datetime.timezone.utc).isoformat().encode()).hexdigest()

def format_error_response(code, message, aws_style=False):
    """Format an error response in S3-compatible or AWS S3 style.
    
    Args:
        code (str): Error code (used only in AWS style)
        message (str): Error message
        aws_style (bool): If True, format as AWS S3 response with code
    """
    if aws_style:
        error = {
            'Error': {
                'Code': code,
                'Message': message,
                'RequestId': generate_request_id()
            }
        }
    else:
        error = {
            'Error': {
                'Message': message
            }
        }
    return make_response(xmltodict.unparse(error), 400 if aws_style else 500)

def format_list_buckets_response(buckets, aws_style=False):
    """Format a list buckets response.
    
    Args:
        buckets (list): List of bucket names
        aws_style (bool): If True, format as AWS S3 response
    """
    if aws_style:
        response = {
            'ListAllMyBucketsResult': {
                '@xmlns': 'http://s3.amazonaws.com/doc/2006-03-01/',
                'Owner': {
                    'ID': 'dfs-owner-id',
                    'DisplayName': 'dfs-owner'
                },
                'Buckets': {
                    'Bucket': [
                        {
                            'Name': bucket,
                            'CreationDate': datetime.datetime.now(datetime.timezone.utc).isoformat()
                        } for bucket in buckets
                    ]
                }
            }
        }
    else:
        response = {
            'Buckets': [{'Name': bucket} for bucket in buckets],
            'Owner': {'ID': 'dfs-owner'}
        }
        response = {'ListAllMyBucketsResult': response}
    
    return make_response(xmltodict.unparse(response), 200)

def format_list_objects_response(bucket, objects, prefix='', max_keys=1000, aws_style=False):
    """Format a list objects response.
    
    Args:
        bucket (str): Bucket name
        objects (list): List of object dictionaries
        prefix (str): Prefix filter used
        max_keys (int): Maximum number of keys to return
        aws_style (bool): If True, format as AWS S3 response
    """
    base_response = {
        'Name': bucket,
        'Prefix': prefix,
        'MaxKeys': max_keys,
        'Contents': [
            {
                'Key': obj['key'],
                'LastModified': obj.get('last_modified', datetime.datetime.now().isoformat()),
                'Size': obj.get('size', 0),
                'ETag': f"\"{obj.get('etag', '')}\""
            } for obj in objects
        ]
    }
    
    if aws_style:
        base_response['@xmlns'] = 'http://s3.amazonaws.com/doc/2006-03-01/'
    
    return make_response(xmltodict.unparse({'ListBucketResult': base_response}), 200)

def format_object_response(obj):
    """Format an object download response.
    
    Args:
        obj (dict): Object data including content and metadata
    """
    if obj is None:
        return format_error_response('NoSuchKey', 'The specified key does not exist.')
        
    headers = {
        'ETag': f"\"{obj.get('etag', '')}\"",
        'Last-Modified': obj.get('last_modified', datetime.datetime.now().isoformat()),
        'Content-Length': str(len(obj['content']))
    }
    
    if 'version_id' in obj:
        headers['VersionId'] = obj['version_id']
    
    return make_response(
        obj['content'],
        200,
        headers
    )
