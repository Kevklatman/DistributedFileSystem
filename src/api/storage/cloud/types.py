"""Common types and enums for cloud storage."""
from enum import Enum

class ProviderHealth(Enum):
    """Health status of a cloud provider."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
