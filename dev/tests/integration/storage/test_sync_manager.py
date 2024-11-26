"""Unit tests for sync manager."""

import unittest
import time
from unittest.mock import Mock, patch
from storage.infrastructure.data.cache_store import CacheStore, ConsistencyLevel
from storage.infrastructure.data.sync_manager import SyncManager


class TestSyncManager(unittest.TestCase):
    """Test cases for sync manager."""

    def setUp(self):
        """Set up test environment."""
        self.cache = CacheStore(
            max_size=5, ttl_seconds=1, consistency_level=ConsistencyLevel.EVENTUAL
        )
        self.sync_manager = SyncManager(
            cache=self.cache,
            sync_interval=0.1,  # Short interval for testing
            max_retries=2,
        )

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, "sync_manager"):
            self.sync_manager.stop()

    def test_sync_callback_registration(self):
        """Test registering sync callbacks."""
        callback = Mock(return_value=True)
        self.sync_manager.register_sync_callback("test_provider", callback)

        # Add a dirty entry
        self.cache.put("key1", "value1", ConsistencyLevel.EVENTUAL)

        # Start sync manager and wait for sync
        self.sync_manager.start()
        time.sleep(0.3)  # Wait for sync cycle

        # Verify callback was called
        callback.assert_called()

    def test_sync_retry_logic(self):
        """Test retry logic for failed syncs."""
        callback = Mock(side_effect=[False, True])  # Fail first, succeed second
        self.sync_manager.register_sync_callback("test_provider", callback)

        # Add a dirty entry
        self.cache.put("key1", "value1", ConsistencyLevel.EVENTUAL)

        # Start sync manager and wait for retries
        self.sync_manager.start()
        time.sleep(1.5)  # Wait for retry cycle + delay

        # Verify callback was called twice
        self.assertEqual(callback.call_count, 2)

    def test_multiple_providers(self):
        """Test syncing with multiple providers."""
        callback1 = Mock(return_value=True)
        callback2 = Mock(return_value=True)

        self.sync_manager.register_sync_callback("provider1", callback1)
        self.sync_manager.register_sync_callback("provider2", callback2)

        # Add a dirty entry
        self.cache.put("key1", "value1", ConsistencyLevel.EVENTUAL)

        # Start sync manager and wait for sync
        self.sync_manager.start()
        time.sleep(0.3)  # Wait for sync cycle

        # Verify both callbacks were called
        callback1.assert_called()
        callback2.assert_called()

    def test_sync_error_handling(self):
        """Test handling of sync errors."""
        callback = Mock(side_effect=Exception("Sync error"))
        self.sync_manager.register_sync_callback("test_provider", callback)

        # Add a dirty entry
        self.cache.put("key1", "value1", ConsistencyLevel.EVENTUAL)

        # Start sync manager and wait for sync attempts
        self.sync_manager.start()
        time.sleep(1.5)  # Wait for retry cycles + delays

        # Verify callback was called max_retries times
        self.assertEqual(callback.call_count, 2)  # max_retries=2

        # Entry should still be dirty
        dirty_entries = self.cache.get_dirty_entries()
        self.assertEqual(len(dirty_entries), 1)

    def test_stop_and_restart(self):
        """Test stopping and restarting the sync manager."""
        callback = Mock(return_value=True)
        self.sync_manager.register_sync_callback("test_provider", callback)

        # Start and add entry
        self.sync_manager.start()
        self.cache.put("key1", "value1", ConsistencyLevel.EVENTUAL)
        time.sleep(0.3)  # Wait for sync cycle

        # Stop and verify no more calls
        self.sync_manager.stop()
        call_count = callback.call_count

        # Add another entry and wait
        self.cache.put("key2", "value2", ConsistencyLevel.EVENTUAL)
        time.sleep(0.3)  # Wait to verify no sync happens

        # Verify no new calls while stopped
        self.assertEqual(callback.call_count, call_count)

        # Restart and verify new syncs
        self.sync_manager.start()
        time.sleep(0.3)  # Wait for sync cycle
        self.assertGreater(callback.call_count, call_count)
