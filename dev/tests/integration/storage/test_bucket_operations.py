import pytest
import os
from http import HTTPStatus
from flask import url_for


def test_create_bucket(client):
    """Test bucket creation API endpoint"""
    # Test creating a new bucket
    response = client.put("/api/v1/s3/buckets/test-bucket")
    assert response.status_code == HTTPStatus.OK

    # Test creating a bucket with invalid name
    response = client.put("/api/v1/s3/buckets/invalid bucket name")
    assert response.status_code == HTTPStatus.BAD_REQUEST

    # Test creating a bucket that already exists
    response = client.put("/api/v1/s3/buckets/test-bucket")
    assert response.status_code == HTTPStatus.CONFLICT


def test_bucket_operations(client):
    """Test basic bucket operations"""
    bucket_name = "test-ops-bucket"

    # Create bucket
    response = client.put(f"/api/v1/s3/buckets/{bucket_name}")
    assert response.status_code == HTTPStatus.OK

    # List buckets
    response = client.get("/api/v1/s3/buckets")
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert "Buckets" in data
    assert any(b["Name"] == bucket_name for b in data["Buckets"])

    # Delete bucket
    response = client.delete(f"/api/v1/s3/buckets/{bucket_name}")
    assert response.status_code == HTTPStatus.NO_CONTENT

    # Verify bucket is gone
    response = client.get("/api/v1/s3/buckets")
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert "Buckets" in data
    assert not any(b["Name"] == bucket_name for b in data["Buckets"])


def test_bucket_consistency(client):
    """Test bucket operations with different consistency levels"""
    # Test with eventual consistency
    response = client.put(
        "/api/v1/s3/buckets/eventual-bucket",
        headers={"X-Consistency-Level": "eventual"},
    )
    assert response.status_code == HTTPStatus.OK

    # Test with strong consistency
    response = client.put(
        "/api/v1/s3/buckets/strong-bucket", headers={"X-Consistency-Level": "strong"}
    )
    assert response.status_code == HTTPStatus.OK
