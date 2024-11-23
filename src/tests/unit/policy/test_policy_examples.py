"""Unit tests for policy examples."""
import pytest
from pathlib import Path
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.storage.policy.policy_examples import (
    load_policy_config,
    setup_policy_engine,
    example_financial_data_handling,
    example_log_data_handling
)
from src.storage.policy.policy_engine import HybridPolicyEngine, PolicyMode
from src.models.models import (
    DataTemperature, Volume, StorageLocation,
    CloudTieringPolicy, DataProtection
)

@pytest.fixture
def mock_config_path(tmp_path):
    """Create a temporary config file"""
    config = {
        "global_constraints": {
            "min_replicas": 2,
            "max_replicas": 5,
            "minimum_retention_days": 30,
            "consistency_level": "eventual",
            "sync_replication": False,
            "max_cost_per_gb": 0.15,
            "force_encryption": True
        },
        "path_overrides": [
            {
                "path_pattern": "financial/*",
                "min_replicas": 3,
                "consistency_level": "strong",
                "sync_replication": True
            }
        ]
    }
    config_file = tmp_path / "config" / "policy_overrides.json"
    config_file.parent.mkdir(exist_ok=True)
    config_file.write_text(json.dumps(config))
    return config_file

def test_load_policy_config(mock_config_path):
    """Test loading policy configuration"""
    config = load_policy_config(mock_config_path)
    assert config["global_constraints"]["min_replicas"] == 2
    assert config["global_constraints"]["force_encryption"] is True
    assert "financial/*" in [o["path_pattern"] for o in config["path_overrides"]]

def test_load_policy_config_invalid_path():
    """Test loading policy configuration with invalid path"""
    config = load_policy_config(Path("/nonexistent/path"))
    assert config == {}

@pytest.fixture
def mock_engine():
    """Create a mock policy engine"""
    engine = MagicMock(spec=HybridPolicyEngine)
    engine.evaluate_tiering_decision.return_value = {
        "action": "move",
        "target_tier": "cold",
        "confidence": 0.95
    }
    return engine

@patch("src.storage.policy.policy_examples.HybridPolicyEngine")
def test_setup_policy_engine(mock_engine_class, mock_config_path, tmp_path):
    """Test setting up policy engine"""
    mock_engine = mock_engine_class.return_value
    engine = setup_policy_engine(tmp_path)
    
    assert mock_engine.update_constraints.called
    assert mock_engine.add_manual_override.called
    assert engine is mock_engine

@patch("src.storage.policy.policy_examples.setup_policy_engine")
def test_example_financial_data_handling(mock_setup):
    """Test financial data handling example"""
    mock_engine = MagicMock()
    mock_setup.return_value = mock_engine
    
    example_financial_data_handling()
    
    # Verify engine was called with correct parameters
    args = mock_engine.evaluate_tiering_decision.call_args[0]
    volume, file_path, temp_data = args
    
    assert isinstance(volume, Volume)
    assert volume.volume_id == "finance-vol-1"
    assert isinstance(volume.tiering_policy, CloudTieringPolicy)
    assert isinstance(volume.protection, DataProtection)
    assert volume.protection.replica_count == 3
    assert volume.protection.consistency_level == "strong"
    assert volume.protection.sync_replication is True
    assert volume.protection.backup_schedule == "0 0 * * *"
    assert file_path == "financial/reports/q2_2023.xlsx"
    assert temp_data == DataTemperature.HOT

@patch("src.storage.policy.policy_examples.setup_policy_engine")
def test_example_log_data_handling(mock_setup):
    """Test log data handling example"""
    mock_engine = MagicMock()
    mock_setup.return_value = mock_engine
    
    example_log_data_handling()
    
    # Verify engine was called with correct parameters
    args = mock_engine.evaluate_tiering_decision.call_args[0]
    volume, file_path, temp_data = args
    
    assert isinstance(volume, Volume)
    assert volume.volume_id == "logs-vol-1"
    assert isinstance(volume.tiering_policy, CloudTieringPolicy)
    assert isinstance(volume.protection, DataProtection)
    assert volume.protection.replica_count == 2
    assert volume.protection.consistency_level == "eventual"
    assert volume.protection.sync_replication is False
    assert volume.protection.backup_schedule == "0 0 * * 0"
    assert file_path == "logs/app/2023/11/app.log"
    assert temp_data == DataTemperature.COLD
