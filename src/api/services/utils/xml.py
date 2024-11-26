"""XML handling utilities for S3-compatible APIs."""

import xmltodict
from flask import request
import logging

logger = logging.getLogger(__name__)


def parse_xml_request(required_fields=None):
    """Parse XML request data and validate required fields.

    Args:
        required_fields (list): List of required field paths (e.g., ['VersioningConfiguration.Status'])

    Returns:
        dict: Parsed XML data

    Raises:
        ValueError: If required fields are missing or invalid
    """
    try:
        data = xmltodict.parse(request.data)

        if required_fields:
            for field_path in required_fields:
                value = get_nested_value(data, field_path.split("."))
                if value is None:
                    raise ValueError(f"Missing required field: {field_path}")

        return data
    except Exception as e:
        logger.error(f"Error parsing XML request: {str(e)}")
        raise ValueError(f"Invalid XML request: {str(e)}")


def get_nested_value(data, path):
    """Get a nested value from a dictionary using a path.

    Args:
        data (dict): Dictionary to traverse
        path (list): List of keys forming the path

    Returns:
        Any: Value at the path or None if not found
    """
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def parse_multipart_complete(data):
    """Parse CompleteMultipartUpload XML.

    Returns:
        list: List of part dictionaries with PartNumber and ETag
    """
    try:
        parts = data["CompleteMultipartUpload"]["Part"]
        if not isinstance(parts, list):
            parts = [parts]

        return [
            {"PartNumber": int(part["PartNumber"]), "ETag": part["ETag"].strip('"')}
            for part in parts
        ]
    except (KeyError, ValueError) as e:
        logger.error(f"Error parsing multipart complete XML: {str(e)}")
        raise ValueError("Invalid CompleteMultipartUpload XML format")


def parse_versioning_config(data):
    """Parse VersioningConfiguration XML.

    Returns:
        str: 'Enabled' or 'Suspended'
    """
    try:
        status = data["VersioningConfiguration"].get("Status", "").lower()
        if status not in ["enabled", "suspended"]:
            raise ValueError("Invalid versioning status")
        return status
    except (KeyError, AttributeError) as e:
        logger.error(f"Error parsing versioning configuration: {str(e)}")
        raise ValueError("Invalid VersioningConfiguration XML format")
