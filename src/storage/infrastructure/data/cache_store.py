"""Module for advanced caching in the distributed file system."""

from typing import Any, Dict, Optional, Set, Tuple
from datetime import datetime
import threading
from enum import Enum
from dataclasses import dataclass
from ..interfaces import CacheInterface


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    value: Any
    version: int
    timestamp: datetime
    session_id: Optional[str] = None


class ConsistencyLevel(Enum):
    """Cache consistency levels."""

    STRONG = "strong"
    EVENTUAL = "eventual"
    WEAK = "weak"


class CacheStore(CacheInterface):
    """Thread-safe cache store with consistency levels."""

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600):
        """Initialize cache store.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live in seconds
        """
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

        self._cache: Dict[str, CacheEntry] = {}
        self._dirty_keys: Set[str] = set()
        self._version = 0

        # Use RLock to allow recursive locking
        self._lock = threading.RLock()
        self._write_lock = threading.RLock()

    def get(self, key: str, consistency_level: Optional[str] = None) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key
            consistency_level: Consistency level for this operation

        Returns:
            Value if found, None if not found
        """
        with (
            self._write_lock
            if consistency_level == ConsistencyLevel.STRONG.value
            else self._lock
        ):
            entry = self._cache.get(key)
            if entry is None:
                return None

            # Check TTL
            if (datetime.now() - entry.timestamp).total_seconds() > self._ttl_seconds:
                del self._cache[key]
                if key in self._dirty_keys:
                    self._dirty_keys.remove(key)
                return None

            return entry.value

    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Put value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if entry was added
        """
        with self._write_lock:
            if len(self._cache) >= self._max_size:
                # Evict oldest entry
                oldest_key = min(self._cache.items(), key=lambda x: x[1].timestamp)[0]
                del self._cache[oldest_key]
                if oldest_key in self._dirty_keys:
                    self._dirty_keys.remove(oldest_key)

            self._version += 1
            self._cache[key] = CacheEntry(
                value=value, version=self._version, timestamp=datetime.now()
            )
            return True

    def delete(self, key: str) -> bool:
        """Delete cache entry.

        Args:
            key: Cache key

        Returns:
            True if entry was found and deleted
        """
        with self._write_lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._dirty_keys:
                    self._dirty_keys.remove(key)
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._write_lock:
            self._cache.clear()
            self._dirty_keys.clear()
            self._version = 0

    def get_dirty_keys(self) -> Set[str]:
        """Get keys that have been modified but not synced."""
        return self._dirty_keys.copy()

    def mark_dirty(self, key: str) -> None:
        """Mark a key as dirty (needs syncing)."""
        with self._lock:
            if key in self._cache:
                self._dirty_keys.add(key)

    def mark_clean(self, key: str) -> None:
        """Mark a key as clean (synced)."""
        with self._lock:
            self._dirty_keys.discard(key)

    def get_dirty_entries(self) -> Dict[str, CacheEntry]:
        """Get all dirty cache entries that need to be synced.

        Returns:
            Dict mapping keys to cache entries that are marked as dirty
        """
        with self._lock:
            return {
                key: self._cache[key] for key in self._dirty_keys if key in self._cache
            }
