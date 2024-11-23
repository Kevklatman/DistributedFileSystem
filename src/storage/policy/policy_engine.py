"""
Hybrid Policy Engine combining ML-based and manual policy decisions
"""
from typing import Dict, Optional, Any, List, Union
from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
import json

from src.models.models import (
    Volume,
    StorageLocation,
    CloudTieringPolicy as TieringPolicy,
    DataProtection as ReplicationPolicy,
    DataTemperature,
    StoragePool
)

# Define PolicyMode here since it's not in core/models.py
class PolicyMode:
    MANUAL = "manual"
    ML = "ml"
    HYBRID = "hybrid"

@dataclass
class PolicyDecision:
    """Represents a policy decision with explanation"""
    action: str
    parameters: Dict[str, Any]
    confidence: float
    reason: str
    manual_override: bool = False
    ml_factors: Dict[str, float] = field(default_factory=dict)

@dataclass
class PolicyConstraints:
    """Hard constraints that ML cannot override"""
    min_copies: int = 2
    max_copies: int = 5
    minimum_retention_days: int = 30
    forbidden_regions: List[str] = field(default_factory=list)
    required_regions: List[str] = field(default_factory=list)
    max_cost_per_gb: float = 0.15
    force_encryption: bool = False

class HybridPolicyEngine:
    """Central policy engine combining ML and manual policies"""

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.logger = logging.getLogger(__name__)
        self.mode = PolicyMode.HYBRID
        self.ml_model = None  # To be initialized with ML model
        self.constraints = PolicyConstraints()

        # Load manual policy overrides if exists
        self.manual_overrides_path = data_path / "config" / "policy_overrides.json"
        self.manual_overrides = self._load_manual_overrides()

    def _load_manual_overrides(self) -> Dict:
        """Load manual policy overrides from config"""
        if self.manual_overrides_path.exists():
            try:
                return json.loads(self.manual_overrides_path.read_text())
            except json.JSONDecodeError:
                self.logger.error("Failed to load manual overrides")
                return {}
        return {}

    def evaluate_tiering_decision(self,
                                volume: Volume,
                                file_path: str,
                                temp_data: DataTemperature) -> PolicyDecision:
        """Evaluate tiering decision using hybrid approach"""

        # Check for manual overrides first
        override = self._check_manual_override(volume.id, file_path)
        if override:
            return PolicyDecision(
                action="move_tier",
                parameters={"target_tier": override["tier"]},
                confidence=1.0,
                reason="Manual policy override applied",
                manual_override=True
            )

        # Get ML prediction if enabled
        ml_decision = None
        if self.mode in [PolicyMode.ML, PolicyMode.HYBRID] and self.ml_model:
            ml_decision = self._get_ml_tiering_prediction(volume, file_path, temp_data)

        # In manual or low confidence cases, use traditional logic
        if (self.mode == PolicyMode.MANUAL or
            (ml_decision and ml_decision.confidence < 0.7)):
            return self._apply_traditional_tiering_logic(temp_data, volume.tiering_policy)

        return ml_decision or self._apply_traditional_tiering_logic(
            temp_data, volume.tiering_policy
        )

    def evaluate_replication_decision(self,
                                   volume: Volume,
                                   target_location: StorageLocation) -> PolicyDecision:
        """Evaluate replication decision using hybrid approach"""

        # Check compliance requirements first
        if self._requires_compliance_replication(volume):
            return PolicyDecision(
                action="replicate",
                parameters={
                    "target_location": target_location,
                    "priority": "high"
                },
                confidence=1.0,
                reason="Compliance requirement",
                manual_override=True
            )

        # Get ML prediction if enabled
        ml_decision = None
        if self.mode in [PolicyMode.ML, PolicyMode.HYBRID] and self.ml_model:
            ml_decision = self._get_ml_replication_prediction(volume, target_location)

        # Apply constraints
        decision = ml_decision or self._apply_traditional_replication_logic(
            volume, target_location
        )
        decision = self._apply_constraints(decision)

        return decision

    def _check_manual_override(self, volume_id: str, file_path: str) -> Optional[Dict]:
        """Check if manual override exists for path"""
        for override in self.manual_overrides.get("path_overrides", []):
            if (
                volume_id == override.get("volume_id", "*") and
                Path(file_path).match(override["pattern"])
            ):
                return override
        return None

    def _get_ml_tiering_prediction(self,
                                 volume: Volume,
                                 file_path: str,
                                 temp_data: DataTemperature) -> PolicyDecision:
        """Get ML-based tiering prediction"""
        if not self.ml_model:
            return None

        # Extract features for ML
        features = {
            "access_frequency": temp_data.access_frequency,
            "last_access_days": temp_data.days_since_last_access,
            "size_gb": temp_data.size_bytes / (1024**3),
            "current_tier": temp_data.current_tier.value,
            # Add more features as needed
        }

        # Get prediction from ML model
        prediction = self.ml_model.predict(features)
        confidence = self.ml_model.predict_proba(features).max()

        return PolicyDecision(
            action="move_tier",
            parameters={"target_tier": prediction},
            confidence=confidence,
            reason="ML prediction based on access patterns",
            ml_factors=features
        )

    def _apply_traditional_tiering_logic(self,
                                      temp_data: DataTemperature,
                                      policy: TieringPolicy) -> PolicyDecision:
        """Apply traditional tiering logic"""
        # Implement existing tiering logic
        temperature_score = (
            0.4 * (1 - temp_data.days_since_last_access / 90) +
            0.4 * min(1.0, temp_data.access_frequency / 10) +
            0.2 * (1 - min(1.0, temp_data.size_bytes / (1024**3)))
        )

        # Determine tier based on temperature score
        if temperature_score > 0.7:
            target_tier = TierType.PERFORMANCE
        elif temperature_score > 0.4:
            target_tier = TierType.CAPACITY
        elif temperature_score > 0.1:
            target_tier = TierType.COLD
        else:
            target_tier = TierType.ARCHIVE

        return PolicyDecision(
            action="move_tier",
            parameters={"target_tier": target_tier},
            confidence=0.8,  # High confidence in traditional logic
            reason="Traditional temperature-based decision"
        )

    def _apply_constraints(self, decision: PolicyDecision) -> PolicyDecision:
        """Apply policy constraints to decision"""
        modified = False

        # Apply region constraints
        if "target_location" in decision.parameters:
            target_loc = decision.parameters["target_location"]
            if (
                target_loc.region in self.constraints.forbidden_regions or
                (self.constraints.required_regions and
                 target_loc.region not in self.constraints.required_regions)
            ):
                # Find alternative location
                decision.parameters["target_location"] = self._find_compliant_location(
                    target_loc
                )
                modified = True

        # Apply cost constraints
        if "target_tier" in decision.parameters:
            tier_costs = {
                TierType.PERFORMANCE: 0.15,
                TierType.CAPACITY: 0.05,
                TierType.COLD: 0.01,
                TierType.ARCHIVE: 0.004
            }
            target_tier = decision.parameters["target_tier"]
            if tier_costs[target_tier] > self.constraints.max_cost_per_gb:
                # Find cheaper tier
                for tier, cost in sorted(tier_costs.items(), key=lambda x: x[1]):
                    if cost <= self.constraints.max_cost_per_gb:
                        decision.parameters["target_tier"] = tier
                        modified = True
                        break

        if modified:
            decision.reason += " (modified by constraints)"

        return decision

    def update_constraints(self, constraints: Dict[str, Any]) -> None:
        """Update policy constraints"""
        for key, value in constraints.items():
            if hasattr(self.constraints, key):
                setattr(self.constraints, key, value)

    def set_mode(self, mode: PolicyMode) -> None:
        """Set policy evaluation mode"""
        self.mode = mode

    def add_manual_override(self, override: Dict[str, Any]) -> None:
        """Add a manual policy override"""
        if "path_overrides" not in self.manual_overrides:
            self.manual_overrides["path_overrides"] = []
        self.manual_overrides["path_overrides"].append(override)

        # Save to file
        self.manual_overrides_path.parent.mkdir(parents=True, exist_ok=True)
        self.manual_overrides_path.write_text(json.dumps(self.manual_overrides, indent=2))
