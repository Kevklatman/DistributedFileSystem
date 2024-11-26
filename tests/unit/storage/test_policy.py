"""Unit tests for the storage policy module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.models.models import (
    Volume,
    DataProtection,
    CloudTieringPolicy,
    DataTemperature,
)
from src.storage.policy.policy_engine import (
    PolicyMode,
    HybridPolicyEngine,
    PolicyDecision,
)
from src.storage.policy.policy_examples import (
    example_financial_data_handling,
    example_log_data_handling,
)


def create_mock_engine():
    """Create a mock policy engine"""
    engine = MagicMock(spec=HybridPolicyEngine)
    engine.mode = PolicyMode.HYBRID

    def evaluate_tiering_decision(volume, file_path, temp_data):
        if "financial" in str(volume.volume_id):
            return PolicyDecision(
                action="move_tier",
                parameters={
                    "replicas": 3,
                    "consistency": "strong",
                    "sync": True,
                    "tier": "hot",
                },
                confidence=1.0,
                reason="Financial data requires strong consistency and multiple replicas",
            )
        else:
            return PolicyDecision(
                action="move_tier",
                parameters={
                    "replicas": 2,
                    "consistency": "eventual",
                    "sync": False,
                    "tier": "cold",
                },
                confidence=1.0,
                reason="Log data can use eventual consistency with fewer replicas",
            )

    engine.evaluate_tiering_decision.side_effect = evaluate_tiering_decision
    return engine


def create_financial_volume():
    """Create a test volume for financial data"""
    return Volume(
        volume_id="financial_data",
        size_bytes=100 * 1024 * 1024 * 1024,  # 100 GB
        protection=DataProtection(
            volume_id="financial_data",
            local_snapshot_enabled=True,
            local_snapshot_schedule="0 * * * *",
            local_snapshot_retention_days=7,
            cloud_backup_enabled=True,
            cloud_backup_schedule="0 0 * * *",
            cloud_backup_retention_days=30,
        ),
        tiering_policy=CloudTieringPolicy(
            volume_id="financial_data",
            mode=PolicyMode.HYBRID,
            cold_tier_after_days=30,
            archive_tier_after_days=90,
        ),
    )


def create_log_volume():
    """Create a test volume for log data"""
    return Volume(
        volume_id="application_logs",
        size_bytes=500 * 1024 * 1024 * 1024,  # 500 GB
        protection=DataProtection(
            volume_id="application_logs",
            local_snapshot_enabled=True,
            local_snapshot_schedule="0 0 * * *",
            local_snapshot_retention_days=7,
            cloud_backup_enabled=True,
            cloud_backup_schedule="0 0 * * 0",
            cloud_backup_retention_days=30,
        ),
        tiering_policy=CloudTieringPolicy(
            volume_id="application_logs",
            mode=PolicyMode.HYBRID,
            cold_tier_after_days=7,
            archive_tier_after_days=30,
        ),
    )


def test_financial_data_policy():
    """Test that financial data uses strong consistency and multiple replicas."""
    # Given
    volume = create_financial_volume()
    engine = create_mock_engine()

    # When
    result = example_financial_data_handling(volume, engine)

    # Then
    assert result.parameters["consistency"] == "strong", "Financial data should use strong consistency"
    assert result.parameters["replicas"] >= 3, "Financial data should have at least 3 replicas"
    assert result.parameters["tier"] == "hot", "Financial data should be in hot tier"
    assert result.parameters["sync"] is True, "Financial data should use synchronous replication"


def test_log_data_policy():
    """Test that log data uses eventual consistency and fewer replicas."""
    # Given
    volume = create_log_volume()
    engine = create_mock_engine()

    # When
    result = example_log_data_handling(volume, engine)

    # Then
    assert result.parameters["consistency"] == "eventual", "Log data can use eventual consistency"
    assert result.parameters["replicas"] >= 2, "Log data should have at least 2 replicas"
    assert result.parameters["tier"] == "cold", "Log data should be in cold tier"
    assert result.parameters["sync"] is False, "Log data can use asynchronous replication"
