"""
Examples of using the hybrid policy engine with manual overrides and constraints
"""
from pathlib import Path
from typing import Dict, Any
import json
import logging
from datetime import datetime

from .policy_engine import HybridPolicyEngine, PolicyMode
from src.storage.core.models import (
    DataTemperature, Volume, StorageLocation, 
    CloudTieringPolicy, DataProtection
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_policy_config(config_path: Path) -> Dict[str, Any]:
    """Load policy configuration from JSON file"""
    try:
        return json.loads(config_path.read_text())
    except Exception as e:
        logger.error(f"Failed to load policy config: {e}")
        return {}

def setup_policy_engine(data_path: Path) -> HybridPolicyEngine:
    """Set up policy engine with configuration"""
    engine = HybridPolicyEngine(data_path)

    # Load configuration
    config_path = data_path / "config" / "policy_overrides.json"
    config = load_policy_config(config_path)

    # Apply global constraints
    if "global_constraints" in config:
        engine.update_constraints(config["global_constraints"])

    # Add path overrides
    for override in config.get("path_overrides", []):
        engine.add_manual_override(override)

    return engine

def example_financial_data_handling():
    """Example: Handling financial data with strict requirements"""
    data_path = Path("/Users/kevinklatman/Development/Code/DistributedFileSystem")
    engine = setup_policy_engine(data_path)

    # Create a test volume with financial data
    volume = Volume(
        volume_id="finance-vol-1",
        size_bytes=1024 * 1024 * 1024 * 100,  # 100GB
        used_bytes=0,
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        locations=[],
        tiering_policy=CloudTieringPolicy(
            cold_tier_after_days=30,
            archive_tier_after_days=90
        ),
        protection=DataProtection(
            replica_count=3,
            consistency_level="strong",
            sync_replication=True,
            backup_schedule="0 0 * * *"  # Daily backup at midnight
        )
    )

    # Test financial data path
    file_path = "financial/reports/q2_2023.xlsx"
    temp_data = DataTemperature.HOT

    # Get policy decision
    decision = engine.evaluate_tiering_decision(volume, file_path, temp_data)
    logger.info(f"Financial data decision: {decision}")

def example_log_data_handling():
    """Example: Handling log data with cost optimization"""
    data_path = Path("/Users/kevinklatman/Development/Code/DistributedFileSystem")
    engine = setup_policy_engine(data_path)

    # Create a test volume with log data
    volume = Volume(
        volume_id="logs-vol-1",
        size_bytes=1024 * 1024 * 1024 * 500,  # 500GB
        used_bytes=0,
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        locations=[],
        tiering_policy=CloudTieringPolicy(
            cold_tier_after_days=30,
            archive_tier_after_days=60
        ),
        protection=DataProtection(
            replica_count=2,
            consistency_level="eventual",
            sync_replication=False,
            backup_schedule="0 0 * * 0"  # Weekly backup on Sunday
        )
    )

    # Test log data path
    file_path = "logs/app/2023/11/app.log"
    temp_data = DataTemperature.COLD

    # Get policy decision
    decision = engine.evaluate_tiering_decision(volume, file_path, temp_data)
    logger.info(f"Log data decision: {decision}")

def example_ml_training_data():
    """Example: Handling ML training data with balanced requirements"""
    data_path = Path("/Users/kevinklatman/Development/Code/DistributedFileSystem")
    engine = setup_policy_engine(data_path)

    # Set to ML mode for this specific case
    engine.set_mode(PolicyMode.ML)

    # Create a test volume with ML training data
    volume = Volume(
        volume_id="ml-vol-1",
        size_bytes=1024 * 1024 * 1024 * 1000,  # 1TB
        used_bytes=0,
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        locations=[],
        tiering_policy=CloudTieringPolicy(
            cold_tier_after_days=30,
            archive_tier_after_days=90
        ),
        protection=DataProtection(
            replica_count=3,
            consistency_level="strong",
            sync_replication=True,
            backup_schedule="0 0 * * *"  # Daily backup at midnight
        )
    )

    # Test ML training data path
    file_path = "ml-training-data/image_dataset_v2.npz"
    temp_data = DataTemperature.HOT

    # Get policy decision
    decision = engine.evaluate_tiering_decision(volume, file_path, temp_data)
    logger.info(f"ML training data decision: {decision}")

def example_backup_volume():
    """Example: Handling backup volume with retention requirements"""
    data_path = Path("/Users/kevinklatman/Development/Code/DistributedFileSystem")
    engine = setup_policy_engine(data_path)

    # Create a test backup volume
    volume = Volume(
        volume_id="backup-vol-1",
        size_bytes=1024 * 1024 * 1024 * 2000,  # 2TB
        used_bytes=0,
        created_at=datetime.now(),
        last_accessed_at=datetime.now(),
        locations=[],
        tiering_policy=CloudTieringPolicy(
            cold_tier_after_days=30,
            archive_tier_after_days=60
        ),
        protection=DataProtection(
            replica_count=2,
            consistency_level="eventual",
            sync_replication=False,
            backup_schedule="0 0 * * 0"  # Weekly backup on Sunday
        )
    )

    # Test backup data
    file_path = "backups/weekly/2023_w45.tar.gz"
    temp_data = DataTemperature.COLD

    # Get policy decision
    decision = engine.evaluate_tiering_decision(volume, file_path, temp_data)
    logger.info(f"Backup data decision: {decision}")

if __name__ == "__main__":
    # Run examples
    example_financial_data_handling()
    example_log_data_handling()
    example_ml_training_data()
    example_backup_volume()
