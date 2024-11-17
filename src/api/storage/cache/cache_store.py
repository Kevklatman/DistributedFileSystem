"""Module for advanced caching in the distributed file system."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import threading
from typing import Any, Dict, Optional, Set, Tuple

class ConsistencyLevel(Enum):
    """Consistency levels for cache operations."""
    STRONG = "strong"      # Immediate consistency with storage
    EVENTUAL = "eventual"  # Eventually consistent with storage
    SESSION = "session"    # Consistent within a session

@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    timestamp: datetime
    version: int
    dirty: bool
    session_id: Optional[str] = None

class CacheStore:
    """Thread-safe cache store with consistency levels."""
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: float = 3600,
        consistency_level: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    ):
        """Initialize cache store.
        
        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live in seconds
            consistency_level: Default consistency level
        """
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._consistency_level = consistency_level
        
        self._cache: Dict[str, CacheEntry] = {}
        self._dirty_keys: Set[str] = set()
        self._version = 0
        
        # Use RLock to allow recursive locking
        self._lock = threading.RLock()
        self._write_lock = threading.RLock()
        
    def put(
        self,
        key: str,
        value: Any,
        consistency: Optional[ConsistencyLevel] = None,
        session_id: Optional[str] = None
    ) -> int:
        """Put value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            consistency: Consistency level for this operation
            session_id: Session identifier for session consistency
            
        Returns:
            Version number of cached entry
        """
        consistency = consistency or self._consistency_level
        
        with self._write_lock if consistency == ConsistencyLevel.STRONG else self._lock:
            version = self._get_next_version()
            
            entry = CacheEntry(
                value=value,
                timestamp=datetime.now(),
                version=version,
                dirty=consistency == ConsistencyLevel.EVENTUAL,  # Only EVENTUAL is dirty
                session_id=session_id
            )
            
            self._evict_if_needed()
            self._cache[key] = entry
            
            if entry.dirty:
                self._dirty_keys.add(key)
                
            return version
            
    def get(
        self,
        key: str,
        consistency: Optional[ConsistencyLevel] = None,
        session_id: Optional[str] = None
    ) -> Optional[Tuple[Any, int]]:
        """Get value from cache.
        
        Args:
            key: Cache key
            consistency: Consistency level for this operation
            session_id: Session identifier for session consistency
            
        Returns:
            Tuple of (value, version) if found, None if not found
        """
        consistency = consistency or ConsistencyLevel.EVENTUAL
        
        with self._write_lock if consistency == ConsistencyLevel.STRONG else self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
                
            # Check TTL
            if (datetime.now() - entry.timestamp).total_seconds() > self._ttl_seconds:
                del self._cache[key]
                if key in self._dirty_keys:
                    self._dirty_keys.remove(key)
                return None
                
            # Check session consistency
            if (
                consistency == ConsistencyLevel.SESSION
                and session_id is not None
                and entry.session_id != session_id
            ):
                return None
                
            return entry.value, entry.version
            
    def invalidate(self, key: str) -> bool:
        """Invalidate cache entry.
        
        Args:
            key: Cache key
            
        Returns:
            True if entry was found and invalidated
        """
        with self._write_lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._dirty_keys:
                    self._dirty_keys.remove(key)
                return True
            return False
            
    def clear(self):
        """Clear all cache entries."""
        with self._write_lock:
            self._cache.clear()
            self._dirty_keys.clear()
            
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "dirty_entries": len(self._dirty_keys)
            }
            
    def get_dirty_entries(self) -> Dict[str, Tuple[Any, int]]:
        """Get all dirty entries.
        
        Returns:
            Dictionary of key -> (value, version) for dirty entries
        """
        with self._lock:
            return {
                key: (self._cache[key].value, self._cache[key].version)
                for key in self._dirty_keys
            }
            
    def mark_synced(self, key: str, version: int) -> bool:
        """Mark entry as synced if version matches.
        
        Args:
            key: Cache key
            version: Version to check
            
        Returns:
            True if entry was found and marked as synced
        """
        with self._write_lock:
            entry = self._cache.get(key)
            if entry is not None and entry.version == version:
                entry.dirty = False
                if key in self._dirty_keys:
                    self._dirty_keys.remove(key)
                return True
            return False
            
    def _get_next_version(self) -> int:
        """Get next version number."""
        self._version += 1
        return self._version
        
    def _evict_if_needed(self):
        """Evict entries if cache is full."""
        while len(self._cache) >= self._max_size:
            # Find oldest entry
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].timestamp
            )
            # Remove it
            del self._cache[oldest_key]
            if oldest_key in self._dirty_keys:
                self._dirty_keys.remove(oldest_key)
