"""Utility classes for handling file transfers with advanced features."""
import time
import threading
from typing import Optional, BinaryIO, Callable
from .config import TransferConfig

class BandwidthLimiter:
    """Implements bandwidth throttling for uploads and downloads."""
    
    def __init__(self, bytes_per_second: Optional[int]):
        self.bytes_per_second = bytes_per_second
        self._last_check = time.time()
        self._bytes_sent = 0
        self._lock = threading.Lock()
    
    def throttle(self, bytes_count: int):
        """Throttle the transfer based on bandwidth limit."""
        if not self.bytes_per_second:
            return
            
        with self._lock:
            self._bytes_sent += bytes_count
            elapsed = time.time() - self._last_check
            
            if elapsed > 0:
                current_rate = self._bytes_sent / elapsed
                if current_rate > self.bytes_per_second:
                    sleep_time = (self._bytes_sent / self.bytes_per_second) - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
                self._bytes_sent = 0
                self._last_check = time.time()

class RetryHandler:
    """Implements retry logic with exponential backoff."""
    
    def __init__(self, config: TransferConfig):
        self.config = config
    
    def execute_with_retry(self, operation: Callable, *args, **kwargs):
        """Execute an operation with retry logic."""
        last_exception = None
        delay = self.config.initial_retry_delay
        
        for attempt in range(self.config.max_attempts):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self.config.max_attempts - 1:
                    raise last_exception
                    
                # Calculate delay based on retry mode
                if self.config.retry_mode == "exponential":
                    delay = min(delay * 2, self.config.max_retry_delay)
                
                time.sleep(delay)
        
        raise last_exception

class MultipartUploader:
    """Handles multipart uploads for large files."""
    
    def __init__(self, config: TransferConfig):
        self.config = config
        self.bandwidth_limiter = BandwidthLimiter(config.upload_bandwidth_limit)
    
    def should_use_multipart(self, file_size: int) -> bool:
        """Determine if multipart upload should be used."""
        return file_size >= self.config.multipart_threshold
    
    def get_chunk_size(self, file_size: int) -> int:
        """Calculate optimal chunk size for multipart upload."""
        chunk_size = self.config.multipart_chunksize
        
        # Ensure we don't exceed maximum number of parts
        max_parts = 10000  # AWS limit
        min_chunk_size = file_size // max_parts
        if chunk_size < min_chunk_size:
            chunk_size = min_chunk_size
            
        return chunk_size
    
    def read_chunk(self, file_obj: BinaryIO, chunk_size: int) -> bytes:
        """Read a chunk from file with bandwidth throttling."""
        chunk = file_obj.read(chunk_size)
        if chunk:
            self.bandwidth_limiter.throttle(len(chunk))
        return chunk

class TransferManager:
    """Manages file transfers with all advanced features."""
    
    def __init__(self, config: TransferConfig = None):
        self.config = config or TransferConfig()
        self.retry_handler = RetryHandler(self.config)
        self.multipart_uploader = MultipartUploader(self.config)
        self.download_limiter = BandwidthLimiter(self.config.download_bandwidth_limit)
    
    def get_transfer_config(self) -> dict:
        """Get provider-specific transfer configuration."""
        return {
            "StorageClass": self.config.storage_class,
            "UseAcceleration": self.config.use_transfer_acceleration,
            "UseRegionalEndpoint": self.config.use_regional_endpoint,
        }
    
    def calculate_optimal_part_size(self, file_size: int) -> int:
        """Calculate optimal part size based on file size and constraints."""
        if not self.multipart_uploader.should_use_multipart(file_size):
            return file_size
            
        return self.multipart_uploader.get_chunk_size(file_size)
