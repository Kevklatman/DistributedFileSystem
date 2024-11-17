"""
Intelligent cloud data tiering with cost optimization and automated data temperature analysis
"""
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import json
import logging
from enum import Enum

from .models import (
    Volume,
    StoragePool,
    StorageLocation,
    TieringPolicy,
    DataTemperature
)

class TierType(Enum):
    PERFORMANCE = "performance"  # NVMe/SSD
    CAPACITY = "capacity"      # HDD
    COLD = "cold"             # S3/Azure Blob
    ARCHIVE = "archive"       # Glacier/Archive

@dataclass
class TierCost:
    cost_per_gb_month: float
    retrieval_cost_per_gb: float
    minimum_storage_days: int

class TieringManager:
    """Manages intelligent data tiering between storage tiers"""
    
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.logger = logging.getLogger(__name__)
        
        # Define tier costs (example values)
        self.tier_costs = {
            TierType.PERFORMANCE: TierCost(0.15, 0.0, 0),
            TierType.CAPACITY: TierCost(0.05, 0.0, 0),
            TierType.COLD: TierCost(0.01, 0.02, 30),
            TierType.ARCHIVE: TierCost(0.004, 0.05, 90)
        }
        
        # Access pattern tracking
        self.access_history: Dict[str, List[datetime]] = {}
        self.temperature_cache: Dict[str, DataTemperature] = {}
        
    def analyze_data_temperature(self, volume: Volume) -> None:
        """Analyze data temperature and update tiering decisions"""
        for file_path in self._scan_volume_files(volume):
            temp_data = self._calculate_temperature(volume, file_path)
            self.temperature_cache[file_path] = temp_data
            
            if self._should_change_tier(temp_data, volume.tiering_policy):
                self._initiate_tier_movement(volume, file_path, temp_data)
                
    def _scan_volume_files(self, volume: Volume) -> List[str]:
        """Scan volume for files to analyze"""
        volume_path = self.data_path / volume.primary_pool_id / volume.id
        files = []
        for path in volume_path.rglob('*'):
            if path.is_file():
                files.append(str(path.relative_to(volume_path)))
        return files
        
    def _calculate_temperature(self, volume: Volume, file_path: str) -> DataTemperature:
        """Calculate data temperature based on access patterns and size"""
        full_path = self.data_path / volume.primary_pool_id / volume.id / file_path
        stats = full_path.stat()
        
        # Get access history
        file_key = f"{volume.id}:{file_path}"
        access_times = self.access_history.get(file_key, [])
        
        # Calculate temperature metrics
        now = datetime.now()
        last_access = datetime.fromtimestamp(stats.st_atime)
        access_frequency = len([t for t in access_times if t > now - timedelta(days=30)])
        
        # Calculate temperature score (0-1)
        time_factor = min(1.0, (now - last_access).days / 90)
        frequency_factor = min(1.0, access_frequency / 10)
        size_factor = min(1.0, stats.st_size / (1024 * 1024 * 1024))  # GB
        
        temperature_score = (
            0.4 * (1 - time_factor) +    # More recent = hotter
            0.4 * frequency_factor +      # More access = hotter
            0.2 * (1 - size_factor)       # Smaller = hotter
        )
        
        # Determine temperature category
        if temperature_score > 0.7:
            tier = TierType.PERFORMANCE
        elif temperature_score > 0.4:
            tier = TierType.CAPACITY
        elif temperature_score > 0.1:
            tier = TierType.COLD
        else:
            tier = TierType.ARCHIVE
            
        return DataTemperature(
            last_access=last_access,
            access_frequency=access_frequency,
            size_bytes=stats.st_size,
            temperature_score=temperature_score,
            recommended_tier=tier
        )
        
    def _should_change_tier(self, temp_data: DataTemperature, policy: TieringPolicy) -> bool:
        """Determine if data should be moved to a different tier"""
        current_tier = policy.current_tier
        target_tier = temp_data.recommended_tier
        
        if current_tier == target_tier:
            return False
            
        # Check minimum storage duration
        if (datetime.now() - temp_data.last_access).days < \
           self.tier_costs[current_tier].minimum_storage_days:
            return False
            
        # Calculate cost benefit
        current_cost = self._calculate_storage_cost(temp_data, current_tier)
        target_cost = self._calculate_storage_cost(temp_data, target_tier)
        
        # Include transition cost
        transition_cost = self._calculate_transition_cost(temp_data, current_tier, target_tier)
        
        # Move if cost benefit over 3 months exceeds transition cost
        return (current_cost - target_cost) * 3 > transition_cost
        
    def _calculate_storage_cost(self, temp_data: DataTemperature, tier: TierType) -> float:
        """Calculate monthly storage cost for data in a tier"""
        size_gb = temp_data.size_bytes / (1024 * 1024 * 1024)
        tier_cost = self.tier_costs[tier]
        
        # Basic storage cost
        cost = size_gb * tier_cost.cost_per_gb_month
        
        # Add estimated retrieval cost based on access frequency
        if tier in [TierType.COLD, TierType.ARCHIVE]:
            monthly_retrievals = temp_data.access_frequency / 30
            cost += size_gb * monthly_retrievals * tier_cost.retrieval_cost_per_gb
            
        return cost
        
    def _calculate_transition_cost(self, temp_data: DataTemperature,
                                 from_tier: TierType, to_tier: TierType) -> float:
        """Calculate cost of transitioning data between tiers"""
        size_gb = temp_data.size_bytes / (1024 * 1024 * 1024)
        
        # Cost includes retrieval from source and write to destination
        retrieval_cost = size_gb * self.tier_costs[from_tier].retrieval_cost_per_gb
        write_cost = size_gb * self.tier_costs[to_tier].retrieval_cost_per_gb
        
        return retrieval_cost + write_cost
        
    def _initiate_tier_movement(self, volume: Volume, file_path: str,
                              temp_data: DataTemperature) -> None:
        """Initiate data movement to new tier"""
        self.logger.info(f"Moving {file_path} to {temp_data.recommended_tier}")
        
        # Implementation would:
        # 1. Create movement job
        # 2. Update metadata
        # 3. Initiate async transfer
        # 4. Update tiering policy
        
    def record_access(self, volume_id: str, file_path: str) -> None:
        """Record file access for temperature calculation"""
        file_key = f"{volume_id}:{file_path}"
        if file_key not in self.access_history:
            self.access_history[file_key] = []
            
        self.access_history[file_key].append(datetime.now())
        
        # Cleanup old history (keep 90 days)
        cutoff = datetime.now() - timedelta(days=90)
        self.access_history[file_key] = [
            t for t in self.access_history[file_key] if t > cutoff
        ]
        
    def get_tier_metrics(self, volume: Volume) -> Dict:
        """Get tiering metrics for a volume"""
        metrics = {tier: 0 for tier in TierType}
        costs = {tier: 0.0 for tier in TierType}
        
        for file_path, temp_data in self.temperature_cache.items():
            tier = temp_data.recommended_tier
            metrics[tier] += temp_data.size_bytes
            costs[tier] += self._calculate_storage_cost(temp_data, tier)
            
        return {
            "distribution": {
                tier.value: bytes_count
                for tier, bytes_count in metrics.items()
            },
            "monthly_costs": {
                tier.value: cost
                for tier, cost in costs.items()
            }
        }
