"""
Examples of using the hybrid policy engine with manual overrides and constraints
"""

from pathlib import Path
from typing import Dict, Any
import json
import logging
from datetime import datetime

from .policy_engine import HybridPolicyEngine, PolicyMode
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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_policy_config(config_path: Path) -> Dict[str, Any]:
    """Load policy configuration from JSON file"""
    try:
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        return json.loads(config_path.read_text())
    except FileNotFoundError as e:
        logger.error(f"Failed to load policy config: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to load policy config: {str(e)}")
        return {}


async def setup_policy_engine(config_path: Path, data_path: Path) -> HybridPolicyEngine:
    """Set up policy engine with configuration"""
    engine = HybridPolicyEngine(data_path)

    # Load configuration
    config = load_policy_config(config_path)

    # Apply global constraints
    if "global_constraints" in config:
        engine.update_constraints(config["global_constraints"])

    # Add path overrides
    for override in config.get("path_overrides", []):
        engine.add_manual_override(override)

    return engine


def example_financial_data_handling(volume: Volume, engine: HybridPolicyEngine) -> Dict[str, Any]:
    """Example: Handling financial data with strict requirements"""
    decision = engine.evaluate_tiering_decision(
        volume=volume,
        file_path="financial/reports/q2_2023.xlsx",
        temp_data=DataTemperature.HOT
    )
    return decision


def example_log_data_handling(volume: Volume, engine: HybridPolicyEngine) -> Dict[str, Any]:
    """Example: Handling log data with cost optimization"""
    decision = engine.evaluate_tiering_decision(
        volume=volume,
        file_path="logs/app/2023/11/app.log",
        temp_data=DataTemperature.COLD
    )
    return decision


def example_ml_training_data(volume: Volume, engine: HybridPolicyEngine) -> Dict[str, Any]:
    """Example: Handling ML training data with balanced requirements"""
    decision = engine.evaluate_tiering_decision(
        volume=volume,
        file_path="ml/training/dataset_v2.parquet",
        temp_data=DataTemperature.WARM
    )
    return decision


def example_backup_volume(volume: Volume, engine: HybridPolicyEngine) -> Dict[str, Any]:
    """Example: Handling backup volume with retention requirements"""
    decision = engine.evaluate_tiering_decision(
        volume=volume,
        file_path="backups/mysql/daily/backup_2023_11_25.sql",
        temp_data=DataTemperature.COLD
    )
    return decision


if __name__ == "__main__":
    # Run examples
    import asyncio

    async def main():
        data_path = Path("data")
        config_path = data_path / "config" / "policy_overrides.json"
        engine = await setup_policy_engine(config_path, data_path)

        volume = Volume(
            volume_id="test-volume",
            size_bytes=100 * 1024 * 1024 * 1024,  # 100 GB
            protection=DataProtection(
                volume_id="test-volume",
                local_snapshot_enabled=True,
                local_snapshot_schedule="0 * * * *",
                local_snapshot_retention_days=7,
                cloud_backup_enabled=True,
                cloud_backup_schedule="0 0 * * *",
                cloud_backup_retention_days=30,
            ),
            tiering_policy=CloudTieringPolicy(
                volume_id="test-volume",
                mode=PolicyMode.HYBRID,
                cold_tier_after_days=30,
                archive_tier_after_days=90,
            ),
        )

        financial_decision = example_financial_data_handling(volume, engine)
        log_decision = example_log_data_handling(volume, engine)
        ml_decision = example_ml_training_data(volume, engine)
        backup_decision = example_backup_volume(volume, engine)

        print(f"Financial data decision: {financial_decision}")
        print(f"Log data decision: {log_decision}")
        print(f"ML training data decision: {ml_decision}")
        print(f"Backup volume decision: {backup_decision}")

    asyncio.run(main())
