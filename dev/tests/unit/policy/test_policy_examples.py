"""Unit tests for policy examples."""

import pytest
from pathlib import Path
import json
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.policy.policy_examples import (
    load_policy_config,
    setup_policy_engine,
    example_financial_data_handling,
    example_log_data_handling,
)
from src.storage.policy.policy_engine import (
    HybridPolicyEngine,
    PolicyMode,
    PolicyDecision,
)
from src.models.models import (
    Volume,
    StorageLocation,
    CloudTieringPolicy,
    DataProtection,
)


class DataTemperature:
    """Temperature classification for data tiering"""
    HOT = "hot"  # Frequently accessed data
    WARM = "warm"  # Moderately accessed data
    COLD = "cold"  # Rarely accessed data
    FROZEN = "frozen"  # Almost never accessed data


@pytest.fixture
def mock_config_path(tmp_path):
    """Create a temporary config file."""
    config = {
        "global_constraints": {
            "min_replicas": 2,
            "max_replicas": 5,
            "minimum_retention_days": 30,
            "consistency_level": "eventual",
            "sync_replication": False,
            "max_cost_per_gb": 0.15,
            "force_encryption": True,
        },
        "path_overrides": [
            {
                "path_pattern": "financial/*",
                "min_replicas": 3,
                "consistency_level": "strong",
                "sync_replication": True,
            }
        ],
    }
    config_file = tmp_path / "config" / "policy_overrides.json"
    config_file.parent.mkdir(exist_ok=True)
    config_file.write_text(json.dumps(config))
    return config_file


@pytest.fixture
def mock_engine():
    """Create a mock policy engine."""
    engine = MagicMock(spec=HybridPolicyEngine)
    engine.mode = PolicyMode.HYBRID

    def evaluate_tiering_decision(volume, file_path, temp_data):
        if "financial" in file_path:
            return PolicyDecision(
                action="move_tier",
                parameters={
                    "replicas": 3,
                    "consistency": "strong",
                    "sync": True,
                },
                confidence=1.0,
                reason="Test decision - financial",
            )
        else:
            return PolicyDecision(
                action="move_tier",
                parameters={
                    "replicas": 2,
                    "consistency": "eventual",
                    "sync": False,
                },
                confidence=1.0,
                reason="Test decision - logs",
            )

    engine.evaluate_tiering_decision.side_effect = evaluate_tiering_decision
    return engine


@pytest.fixture
def mock_engine_class(mock_engine):
    """Create a mock policy engine class."""
    with patch("src.storage.policy.policy_examples.HybridPolicyEngine") as mock:
        mock.return_value = mock_engine
        yield mock


@pytest.fixture
def mock_setup(mock_engine):
    """Create a mock setup function."""
    return mock_engine


def test_load_policy_config(mock_config_path):
    """Test loading policy configuration."""
    config = load_policy_config(mock_config_path)
    assert config["global_constraints"]["min_replicas"] == 2
    assert config["global_constraints"]["force_encryption"] is True
    assert len(config["path_overrides"]) == 1


def test_load_policy_config_invalid_path():
    """Test loading policy configuration with invalid path."""
    try:
        load_policy_config(Path("/nonexistent/path"))
        pytest.fail("Expected FileNotFoundError")
    except FileNotFoundError:
        pass


@pytest.mark.asyncio
async def test_setup_policy_engine(mock_engine_class, mock_config_path, tmp_path):
    """Test setting up policy engine."""
    engine = await setup_policy_engine(mock_config_path, tmp_path)
    assert engine.mode == PolicyMode.HYBRID
    mock_engine_class.assert_called_once()


def test_example_financial_data_handling(mock_setup):
    """Test financial data handling example."""
    volume = Volume(
        name="financial_data",
        size_gb=100,  # 100 GB
        primary_pool_id="test-pool-1",
        id="financial_data",
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

    result = example_financial_data_handling(volume, mock_setup)
    assert result.parameters["replicas"] >= 3
    assert result.parameters["consistency"] == "strong"
    assert result.parameters["sync"] is True


def test_example_log_data_handling(mock_setup):
    """Test log data handling example."""
    volume = Volume(
        name="application_logs",
        size_gb=500,  # 500 GB
        primary_pool_id="test-pool-1",
        id="application_logs",
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

    result = example_log_data_handling(volume, mock_setup)
    assert result.parameters["replicas"] >= 2
    assert result.parameters["consistency"] == "eventual"
    mock_setup.evaluate_tiering_decision.assert_called_once()
