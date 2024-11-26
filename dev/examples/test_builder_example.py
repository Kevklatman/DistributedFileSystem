"""Example of using the Easy Test Builder to write tests in plain English."""

from pathlib import Path
import sys
from unittest.mock import MagicMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Add dev tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from test_builder import TestBuilder
from src.storage.policy.policy_examples import (
    example_financial_data_handling,
    example_log_data_handling,
)
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

def check_strong_consistency(results):
    """Check if the storage policy uses strong consistency"""
    return results.parameters["consistency"] == "strong"

def check_replicas(results):
    """Check if there are at least 3 replicas"""
    return results.parameters["replicas"] >= 3

def check_eventual_consistency(results):
    """Check if the storage policy uses eventual consistency"""
    return results.parameters["consistency"] == "eventual"

def check_min_replicas(results):
    """Check if there are at least 2 replicas"""
    return results.parameters["replicas"] >= 2

def check_hot_tier(results):
    """Check if data is in hot tier"""
    return results.parameters["tier"] == "hot"

def check_cold_tier(results):
    """Check if data is in cold tier"""
    return results.parameters["tier"] == "cold"

if __name__ == "__main__":
    # Create a test suite
    suite = TestBuilder("Storage Policy Tests")

    # Create mock engine
    mock_engine = create_mock_engine()

    # Test case 1: Financial data handling
    suite.test("When uploading a financial document, it should use strong consistency") \
        .given("a financial volume is created", create_financial_volume) \
        .when("a document is uploaded to the financial folder", 
              lambda vol: example_financial_data_handling(vol, mock_engine)) \
        .then("the storage policy should use strong consistency", check_strong_consistency) \
        .and_then("there should be at least 3 replicas", check_replicas) \
        .and_then("data should be in hot tier", check_hot_tier) \
        .build()

    # Test case 2: Log data handling
    suite.test("When storing log data, it should use eventual consistency") \
        .given("a log volume is created", create_log_volume) \
        .when("logs are written to the volume", 
              lambda vol: example_log_data_handling(vol, mock_engine)) \
        .then("the storage policy should use eventual consistency", check_eventual_consistency) \
        .and_then("there should be at least 2 replicas", check_min_replicas) \
        .and_then("data should be in cold tier", check_cold_tier) \
        .build()

    # Run all tests
    suite.run()
