"""
Examples of using the hybrid policy engine with manual overrides and constraints
"""
from pathlib import Path
from typing import Dict, Any
import json
import logging

from .policy_engine import HybridPolicyEngine, PolicyMode
from models import DataTemperature, Volume, StorageLocation, TieringPolicy
from .tiering_manager import TierType

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
        id="finance-vol-1",
        name="Financial Reports",
        size_bytes=1024 * 1024 * 1024 * 100,  # 100GB
        primary_pool_id="pool-1",
        tiering_policy=TieringPolicy(
            enabled=True,
            target_tiers=[TierType.PERFORMANCE, TierType.CAPACITY]
        )
    )

    # Test financial data path
    file_path = "financial/reports/q2_2023.xlsx"
    temp_data = DataTemperature(
        access_frequency=5,
        days_since_last_access=2,
        size_bytes=1024 * 1024 * 10,  # 10MB
        current_tier=TierType.CAPACITY
    )

    # Get policy decision
    decision = engine.evaluate_tiering_decision(volume, file_path, temp_data)
    logger.info(f"Financial data decision: {decision}")

def example_log_data_handling():
    """Example: Handling log data with cost optimization"""
    data_path = Path("/Users/kevinklatman/Development/Code/DistributedFileSystem")
    engine = setup_policy_engine(data_path)

    # Create a test volume with log data
    volume = Volume(
        id="logs-vol-1",
        name="Application Logs",
        size_bytes=1024 * 1024 * 1024 * 500,  # 500GB
        primary_pool_id="pool-1",
        tiering_policy=TieringPolicy(
            enabled=True,
            target_tiers=[TierType.CAPACITY, TierType.COLD, TierType.ARCHIVE]
        )
    )

    # Test log data path
    file_path = "logs/app/2023/11/app.log"
    temp_data = DataTemperature(
        access_frequency=0,
        days_since_last_access=60,
        size_bytes=1024 * 1024 * 100,  # 100MB
        current_tier=TierType.CAPACITY
    )

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
        id="ml-vol-1",
        name="ML Training Sets",
        size_bytes=1024 * 1024 * 1024 * 1000,  # 1TB
        primary_pool_id="pool-1",
        tiering_policy=TieringPolicy(
            enabled=True,
            target_tiers=[TierType.PERFORMANCE, TierType.CAPACITY]
        )
    )

    # Test ML training data path
    file_path = "ml-training-data/image_dataset_v2.npz"
    temp_data = DataTemperature(
        access_frequency=20,
        days_since_last_access=1,
        size_bytes=1024 * 1024 * 1024 * 10,  # 10GB
        current_tier=TierType.CAPACITY
    )

    # Get policy decision
    decision = engine.evaluate_tiering_decision(volume, file_path, temp_data)
    logger.info(f"ML training data decision: {decision}")

def example_backup_volume():
    """Example: Handling backup volume with retention requirements"""
    data_path = Path("/Users/kevinklatman/Development/Code/DistributedFileSystem")
    engine = setup_policy_engine(data_path)

    # Create a test backup volume
    volume = Volume(
        id="backup-vol-1",
        name="Weekly Backups",
        size_bytes=1024 * 1024 * 1024 * 2000,  # 2TB
        primary_pool_id="pool-1",
        tiering_policy=TieringPolicy(
            enabled=True,
            target_tiers=[TierType.COLD, TierType.ARCHIVE]
        )
    )

    # Test backup data
    file_path = "backups/weekly/2023_w45.tar.gz"
    temp_data = DataTemperature(
        access_frequency=0,
        days_since_last_access=30,
        size_bytes=1024 * 1024 * 1024 * 100,  # 100GB
        current_tier=TierType.COLD
    )

    # Get policy decision
    decision = engine.evaluate_tiering_decision(volume, file_path, temp_data)
    logger.info(f"Backup data decision: {decision}")

if __name__ == "__main__":
    # Run examples
    example_financial_data_handling()
    example_log_data_handling()
    example_ml_training_data()
    example_backup_volume()
