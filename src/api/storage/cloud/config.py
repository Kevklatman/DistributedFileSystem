"""Configuration classes for cloud storage providers."""
from dataclasses import dataclass
from typing import Optional

@dataclass
class TransferConfig:
    """Configuration for file transfer operations."""
    # Multipart upload settings
    multipart_threshold: int = 100 * 1024 * 1024  # 100MB
    multipart_chunksize: int = 10 * 1024 * 1024   # 10MB
    max_concurrency: int = 10
    
    # Retry settings
    max_attempts: int = 5
    initial_retry_delay: float = 1.0  # seconds
    max_retry_delay: float = 30.0     # seconds
    retry_mode: str = "exponential"   # "exponential" or "fixed"
    
    # Bandwidth settings
    upload_bandwidth_limit: Optional[int] = None   # bytes per second
    download_bandwidth_limit: Optional[int] = None # bytes per second
    
    # Cost optimization settings
    storage_class: str = "STANDARD"  # STANDARD, INFREQUENT_ACCESS, ARCHIVE, etc.
    use_transfer_acceleration: bool = False
    use_regional_endpoint: bool = True
