"""
Real-world policy scenarios and configuration examples
"""
from pathlib import Path
import logging
from datetime import datetime, timedelta

from src.storage.policy.policy_engine import HybridPolicyEngine, PolicyMode
from src.api.models import Volume, StorageLocation, TieringPolicy, DataTemperature
from src.storage.policy.tiering_manager import TierType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
#h
class PolicyScenarios:
    def __init__(self):
        self.data_path = Path("/Users/kevinklatman/Development/Code/DistributedFileSystem")
        self.engine = HybridPolicyEngine(self.data_path)

    def setup_regulatory_compliance(self):
        """
        Scenario: Healthcare data with HIPAA compliance requirements
        - Must stay in approved regions
        - Requires encryption
        - Minimum retention period
        - Multiple copies required
        """
        # Add healthcare data policy
        self.engine.add_manual_override({
            "pattern": "**/healthcare/**",
            "tier": "performance",  # Fast access for patient data
            "min_copies": 3,        # Multiple copies for redundancy
            "required_regions": ["us-east-2"],  # HIPAA approved regions
            "force_encryption": True,
            "retention_days": 2555,  # 7 years retention
            "reason": "HIPAA compliance requirements"
        })

        # Test with patient data
        volume = Volume(
            id="patient-data-01",
            name="Patient Records 2023",
            size_bytes=1024 * 1024 * 1024 * 500,  # 500GB
            primary_pool_id="pool-1",
            tiering_policy=TieringPolicy(enabled=True)
        )

        file_path = "healthcare/patient_records/patient_001.dcm"
        temp_data = DataTemperature(
            access_frequency=10,
            days_since_last_access=1,
            size_bytes=1024 * 1024 * 50,  # 50MB
            current_tier=TierType.CAPACITY
        )

        decision = self.engine.evaluate_tiering_decision(volume, file_path, temp_data)
        logger.info(f"Healthcare data decision: {decision}")

    def setup_cost_optimization(self):
        """
        Scenario: Development environment with cost constraints
        - Move infrequently accessed data to cheaper tiers
        - Limit number of copies
        - Use cheaper regions
        """
        # Add development environment policy
        self.engine.add_manual_override({
            "pattern": "**/dev/**",
            "tier": "capacity",     # Balance of performance and cost
            "max_copies": 2,        # Limit redundancy for cost
            "required_regions": ["us-east-2"],  # Single region for cost
            "reason": "Development environment cost optimization"
        })

        # Update cost constraints
        self.engine.update_constraints({
            "max_cost_per_gb": 0.08,  # Strict cost limit
            "min_cost_savings_for_move": 0.02
        })

        # Test with dev environment data
        volume = Volume(
            id="dev-env-01",
            name="Development Environment",
            size_bytes=1024 * 1024 * 1024 * 1000,  # 1TB
            primary_pool_id="pool-1",
            tiering_policy=TieringPolicy(enabled=True)
        )

        file_path = "dev/test_data/large_dataset.parquet"
        temp_data = DataTemperature(
            access_frequency=2,
            days_since_last_access=15,
            size_bytes=1024 * 1024 * 1024 * 10,  # 10GB
            current_tier=TierType.PERFORMANCE
        )

        decision = self.engine.evaluate_tiering_decision(volume, file_path, temp_data)
        logger.info(f"Dev environment decision: {decision}")

    def setup_ml_workload(self):
        """
        Scenario: ML workload with dynamic requirements
        - Active training data stays in performance tier
        - Completed experiments move to capacity
        - Archive old versions
        """
        # Switch to ML mode for intelligent decisions
        self.engine.set_mode(PolicyMode.ML)

        # Add ML workload policies
        self.engine.add_manual_override({
            "pattern": "**/ml/active/**",
            "tier": "performance",
            "min_copies": 2,
            "reason": "Active ML training data"
        })

        self.engine.add_manual_override({
            "pattern": "**/ml/completed/**",
            "tier": "capacity",
            "min_copies": 1,
            "reason": "Completed ML experiments"
        })

        self.engine.add_manual_override({
            "pattern": "**/ml/archived/**",
            "tier": "cold",
            "min_copies": 1,
            "reason": "Archived ML experiments"
        })

        # Test with active training data
        volume = Volume(
            id="ml-training-01",
            name="ML Training Data",
            size_bytes=1024 * 1024 * 1024 * 2000,  # 2TB
            primary_pool_id="pool-1",
            tiering_policy=TieringPolicy(enabled=True)
        )

        # Test different ML data paths
        test_cases = [
            ("ml/active/current_model.h5", 50, 0),    # Active model
            ("ml/completed/exp_001.h5", 0, 30),       # Completed experiment
            ("ml/archived/old_model_v1.h5", 0, 90)    # Archived model
        ]

        for file_path, access_freq, days_old in test_cases:
            temp_data = DataTemperature(
                access_frequency=access_freq,
                days_since_last_access=days_old,
                size_bytes=1024 * 1024 * 1024 * 2,  # 2GB
                current_tier=TierType.PERFORMANCE
            )

            decision = self.engine.evaluate_tiering_decision(volume, file_path, temp_data)
            logger.info(f"ML data decision for {file_path}: {decision}")

    def setup_hybrid_cloud(self):
        """
        Scenario: Hybrid cloud deployment
        - Keep sensitive data on-premises
        - Use cloud for overflow and backup
        - Cost-based tiering for cloud storage
        """
        # Add hybrid cloud policies
        self.engine.add_manual_override({
            "pattern": "**/sensitive/**",
            "tier": "performance",
            "required_regions": ["on-prem-dc1"],  # On-premises datacenter
            "force_encryption": True,
            "reason": "Sensitive data must stay on-premises"
        })

        self.engine.add_manual_override({
            "pattern": "**/public/**",
            "tier": "capacity",
            "required_regions": ["us-east-2"],  # Cloud regions
            "reason": "Public data can use cloud storage"
        })

        # Add cloud cost optimization
        self.engine.update_constraints({
            "max_cloud_cost_per_gb": 0.10,
            "min_on_prem_free_space": 0.20  # Keep 20% free on-prem
        })

        # Test with different data types
        volume = Volume(
            id="hybrid-vol-01",
            name="Hybrid Storage",
            size_bytes=1024 * 1024 * 1024 * 5000,  # 5TB
            primary_pool_id="pool-1",
            tiering_policy=TieringPolicy(enabled=True)
        )

        # Test cases for different data types
        test_cases = [
            ("sensitive/customer_data.db", TierType.PERFORMANCE),
            ("public/downloads/package.zip", TierType.CAPACITY),
            ("backups/weekly/backup.tar", TierType.COLD)
        ]

        for file_path, current_tier in test_cases:
            temp_data = DataTemperature(
                access_frequency=5 if "sensitive" in file_path else 1,
                days_since_last_access=1 if "sensitive" in file_path else 30,
                size_bytes=1024 * 1024 * 1024,  # 1GB
                current_tier=current_tier
            )

            decision = self.engine.evaluate_tiering_decision(volume, file_path, temp_data)
            logger.info(f"Hybrid cloud decision for {file_path}: {decision}")

    def setup_dynamic_workload(self):
        """
        Scenario: Dynamic workload with time-based patterns
        - Business hours: Keep active data in performance tier
        - Off hours: Move to capacity tier
        - Weekends: Allow archival of inactive data
        """
        def is_business_hours() -> bool:
            now = datetime.now()
            return (
                now.weekday() < 5 and  # Monday to Friday
                9 <= now.hour < 17      # 9 AM to 5 PM
            )

        # Add time-based policy
        class DynamicPolicy:
            def evaluate(self, file_path: str, temp_data: DataTemperature) -> TierType:
                if is_business_hours():
                    return TierType.PERFORMANCE if temp_data.access_frequency > 0 else TierType.CAPACITY
                else:
                    # Off hours - be more aggressive with tiering
                    if temp_data.access_frequency == 0:
                        return TierType.COLD
                    elif temp_data.access_frequency < 5:
                        return TierType.CAPACITY
                    else:
                        return TierType.PERFORMANCE

        # Register dynamic policy
        self.engine.register_dynamic_policy("workload_hours", DynamicPolicy())

        # Test with current time
        volume = Volume(
            id="dynamic-vol-01",
            name="Dynamic Workload",
            size_bytes=1024 * 1024 * 1024 * 1000,  # 1TB
            primary_pool_id="pool-1",
            tiering_policy=TieringPolicy(enabled=True)
        )

        # Test at different times
        test_times = [
            datetime(2023, 11, 20, 10, 0),  # Monday 10 AM
            datetime(2023, 11, 20, 18, 0),  # Monday 6 PM
            datetime(2023, 11, 25, 12, 0),  # Saturday 12 PM
        ]

        for test_time in test_times:
            # Mock current time
            datetime.now = lambda: test_time

            temp_data = DataTemperature(
                access_frequency=10,
                days_since_last_access=0,
                size_bytes=1024 * 1024 * 100,  # 100MB
                current_tier=TierType.PERFORMANCE
            )

            decision = self.engine.evaluate_tiering_decision(
                volume, "workload/active/data.db", temp_data
            )
            logger.info(f"Dynamic decision at {test_time}: {decision}")

def main():
    scenarios = PolicyScenarios()

    # Run all scenarios
    logger.info("Testing Healthcare Compliance Scenario...")
    scenarios.setup_regulatory_compliance()

    logger.info("\nTesting Cost Optimization Scenario...")
    scenarios.setup_cost_optimization()

    logger.info("\nTesting ML Workload Scenario...")
    scenarios.setup_ml_workload()

    logger.info("\nTesting Hybrid Cloud Scenario...")
    scenarios.setup_hybrid_cloud()

    logger.info("\nTesting Dynamic Workload Scenario...")
    scenarios.setup_dynamic_workload()

if __name__ == "__main__":
    main()
