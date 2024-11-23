"""Module for managing cache synchronization with storage backends."""
import threading
import time
import logging
from typing import Callable, Dict, Optional
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .cache_store import CacheStore, ConsistencyLevel

logger = logging.getLogger(__name__)

class SyncManager:
    """Manages synchronization between cache and storage backends."""

    def __init__(
        self,
        cache: CacheStore,
        sync_interval: float = 5.0,
        max_retries: int = 3,
        max_workers: int = 4
    ):
        """Initialize the sync manager.

        Args:
            cache: Cache store instance
            sync_interval: Interval between sync attempts in seconds
            max_retries: Maximum number of sync retries
            max_workers: Maximum number of concurrent sync workers
        """
        self._cache = cache
        self._sync_interval = sync_interval
        self._max_retries = max_retries
        self._stop_event = threading.Event()
        self._sync_thread: Optional[threading.Thread] = None
        self._executor = None  # Initialize executor when starting
        self._sync_callbacks: Dict[str, Callable] = {}
        self._retry_delays = [1, 5, 15]  # Exponential backoff delays
        self._max_workers = max_workers

    def register_sync_callback(
        self,
        provider_name: str,
        callback: Callable[[str, any, int], bool]
    ):
        """Register a callback for syncing with a storage provider.

        Args:
            provider_name: Name of the storage provider
            callback: Function to call for syncing. Should take (key, value, version)
                     and return True if sync successful
        """
        self._sync_callbacks[provider_name] = callback

    def start(self):
        """Start the sync manager."""
        if self._sync_thread is not None:
            return

        self._stop_event.clear()
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._sync_thread = threading.Thread(target=self._sync_loop)
        self._sync_thread.daemon = True
        self._sync_thread.start()
        logger.info("Sync manager started")

    def stop(self):
        """Stop the sync manager."""
        if self._sync_thread is None:
            return

        self._stop_event.set()
        self._sync_thread.join()
        self._sync_thread = None

        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

        logger.info("Sync manager stopped")

    def _sync_loop(self):
        """Main sync loop."""
        while not self._stop_event.is_set():
            try:
                self._sync_dirty_entries()
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")

            self._stop_event.wait(self._sync_interval)

    def _sync_dirty_entries(self):
        """Sync all dirty cache entries."""
        if self._executor is None or self._executor._shutdown:
            return

        dirty_entries = self._cache.get_dirty_entries()
        if not dirty_entries:
            return

        futures = []
        for key, (value, version) in dirty_entries.items():
            for provider_name, callback in self._sync_callbacks.items():
                future = self._executor.submit(
                    self._sync_with_retry,
                    key,
                    value,
                    version,
                    provider_name,
                    callback,
                    0  # Initial retry count
                )
                futures.append(future)

        # Wait for all sync operations to complete
        for future in futures:
            try:
                future.result()
            except Exception as e:
                logger.error(f"Sync operation failed: {e}")

    def _sync_with_retry(
        self,
        key: str,
        value: any,
        version: int,
        provider_name: str,
        callback: Callable,
        retry_count: int
    ):
        """Attempt to sync with retry logic.

        Args:
            key: Cache key
            value: Value to sync
            version: Version number
            provider_name: Name of the storage provider
            callback: Sync callback function
            retry_count: Current retry attempt
        """
        if retry_count >= self._max_retries:
            logger.error(
                f"Failed to sync key {key} with provider {provider_name} "
                f"after {self._max_retries} attempts"
            )
            return False

        try:
            if callback(key, value, version):
                self._cache.mark_synced(key, version)
                logger.info(
                    f"Successfully synced key {key} with provider {provider_name}"
                )
                return True

            logger.warning(
                f"Sync attempt {retry_count + 1} failed for key {key} "
                f"with provider {provider_name}: callback returned False"
            )

        except Exception as e:
            logger.warning(
                f"Sync attempt {retry_count + 1} failed for key {key} "
                f"with provider {provider_name}: {e}"
            )

        # Schedule retry with exponential backoff
        if not self._stop_event.is_set():
            delay = self._retry_delays[min(retry_count, len(self._retry_delays) - 1)]
            time.sleep(delay)
            return self._sync_with_retry(
                key,
                value,
                version,
                provider_name,
                callback,
                retry_count + 1
            )

        return False
