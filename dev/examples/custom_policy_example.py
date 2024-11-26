"""
Custom policy example demonstrating intelligent data placement
"""
from pathlib import Path
import logging
from datetime import datetime, timedelta
import json

from src.storage.policy.policy_engine import HybridPolicyEngine, PolicyMode, PolicyDecision
from src.models.models import Volume, StorageLocation, TieringPolicy, DataTemperature
from src.storage.policy.tiering_manager import TierType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CustomPolicyExample:
    def __init__(self):
        self.data_path = Path("/Users/kevinklatman/Development/Code/DistributedFileSystem")
        self.engine = HybridPolicyEngine(self.data_path)

    def setup_custom_policies(self):
        """Set up custom policies combining ML and manual rules"""
        # Define performance tier regions
        performance_regions = ["us-east-2", "us-west-1"]

        # Base policy for all data
        self.engine.update_constraints({
            "max_cost_per_gb": 0.15,
            "min_copies": 2,
            "force_encryption": True
        })

        # High-priority data policy
        self.engine.add_manual_override({
            "pattern": "**/high-priority/**",
            "tier": "performance",
            "min_copies": 3,
            "required_regions": performance_regions,
            "reason": "High-priority data requirements"
        })

        # Time-sensitive data policy
        self.engine.add_manual_override({
            "pattern": "**/time-sensitive/**",
            "tier": "performance",
            "max_latency_ms": 10,
            "required_regions": performance_regions,
            "reason": "Low-latency access requirements"
        })

        # Cost-optimized data policy
        self.engine.add_manual_override({
            "pattern": "**/archive/**",
            "tier": "cold",
            "min_copies": 1,
            "max_cost_per_gb": 0.05,
            "reason": "Cost optimization for archived data"
        })

        # Enable ML for standard data paths
        self.engine.set_mode(PolicyMode.HYBRID)

    def evaluate_data_placement(self, file_path: str, access_pattern: dict):
        """Evaluate data placement based on access patterns"""
        volume = Volume(
            name="Custom Volume",
            size_gb=1000,  # 1TB
            primary_pool_id="pool-1",
            cloud_tiering_enabled=True
        )

        temp_data = DataTemperature(
            access_frequency=access_pattern["frequency"],
            days_since_last_access=access_pattern["days_since_access"],
            size_bytes=access_pattern["size_bytes"],
            current_tier=access_pattern["current_tier"]
        )

        decision = self.engine.evaluate_tiering_decision(volume, file_path, temp_data)
        return decision

    def run_examples(self):
        """Run examples with different data types and access patterns"""
        self.setup_custom_policies()

        test_cases = [
            {
                "name": "Frequently accessed high-priority data",
                "path": "high-priority/customer_data/active_accounts.db",
                "pattern": {
                    "frequency": 100,
                    "days_since_access": 0,
                    "size_bytes": 1024 * 1024 * 1024 * 10,  # 10GB
                    "current_tier": TierType.CAPACITY
                }
            },
            {
                "name": "Time-sensitive trading data",
                "path": "time-sensitive/market_data/live_feed.db",
                "pattern": {
                    "frequency": 1000,
                    "days_since_access": 0,
                    "size_bytes": 1024 * 1024 * 100,  # 100MB
                    "current_tier": TierType.PERFORMANCE
                }
            },
            {
                "name": "Old archive data",
                "path": "archive/2022/q1_reports.zip",
                "pattern": {
                    "frequency": 0,
                    "days_since_access": 180,
                    "size_bytes": 1024 * 1024 * 1024 * 50,  # 50GB
                    "current_tier": TierType.CAPACITY
                }
            },
            {
                "name": "ML-managed standard data",
                "path": "standard/user_uploads/dataset.parquet",
                "pattern": {
                    "frequency": 10,
                    "days_since_access": 5,
                    "size_bytes": 1024 * 1024 * 1024,  # 1GB
                    "current_tier": TierType.CAPACITY
                }
            }
        ]

        for test_case in test_cases:
            logger.info(f"\nEvaluating {test_case['name']}:")
            decision = self.evaluate_data_placement(
                test_case["path"],
                test_case["pattern"]
            )
            logger.info(f"Path: {test_case['path']}")
            logger.info(f"Decision: {decision}")

    def analyze_cost_impact(self):
        """Analyze cost impact of policy decisions"""
        tier_costs = {
            TierType.PERFORMANCE: 0.15,
            TierType.CAPACITY: 0.05,
            TierType.COLD: 0.01,
            TierType.ARCHIVE: 0.004
        }

        total_cost_before = 0
        total_cost_after = 0

        test_data = [
            {
                "path": "standard/data1.db",
                "size_gb": 100,
                "current_tier": TierType.PERFORMANCE,
                "access_pattern": {
                    "frequency": 1,
                    "days_since_access": 30,
                    "size_bytes": 1024 * 1024 * 1024 * 100,
                    "current_tier": TierType.PERFORMANCE
                }
            },
            {
                "path": "high-priority/data2.db",
                "size_gb": 50,
                "current_tier": TierType.CAPACITY,
                "access_pattern": {
                    "frequency": 100,
                    "days_since_access": 0,
                    "size_bytes": 1024 * 1024 * 1024 * 50,
                    "current_tier": TierType.CAPACITY
                }
            }
        ]

        for data in test_data:
            # Calculate current cost
            current_cost = data["size_gb"] * tier_costs[data["current_tier"]]
            total_cost_before += current_cost

            # Get policy decision
            decision = self.evaluate_data_placement(
                data["path"],
                data["access_pattern"]
            )

            # Calculate new cost
            new_tier = decision.parameters["target_tier"]
            new_cost = data["size_gb"] * tier_costs[new_tier]
            total_cost_after += new_cost

            logger.info(f"\nCost analysis for {data['path']}:")
            logger.info(f"Current tier: {data['current_tier']}, cost: ${current_cost:.2f}")
            logger.info(f"New tier: {new_tier}, cost: ${new_cost:.2f}")
            logger.info(f"Monthly savings: ${current_cost - new_cost:.2f}")

        total_savings = total_cost_before - total_cost_after
        savings_percent = (total_savings / total_cost_before) * 100

        logger.info(f"\nTotal monthly cost impact:")
        logger.info(f"Before: ${total_cost_before:.2f}")
        logger.info(f"After: ${total_cost_after:.2f}")
        logger.info(f"Savings: ${total_savings:.2f} ({savings_percent:.1f}%)")

def main():
    example = CustomPolicyExample()

    logger.info("Running policy examples...")
    example.run_examples()

    logger.info("\nAnalyzing cost impact...")
    example.analyze_cost_impact()

if __name__ == "__main__":
    main()
