"""Unit tests for cache store."""
import unittest
import time
from datetime import datetime, timedelta
from src.api.storage.cache.cache_store import CacheStore, ConsistencyLevel

class TestCacheStore(unittest.TestCase):
    """Test cases for cache store."""
    
    def setUp(self):
        """Set up test environment."""
        self.cache = CacheStore(
            max_size=5,
            ttl_seconds=1,
            consistency_level=ConsistencyLevel.EVENTUAL
        )
        
    def test_put_and_get(self):
        """Test basic put and get operations."""
        version = self.cache.put("key1", "value1")
        self.assertIsNotNone(version)
        
        result = self.cache.get("key1")
        self.assertIsNotNone(result)
        value, cached_version = result
        self.assertEqual(value, "value1")
        self.assertEqual(version, cached_version)
        
    def test_ttl_expiration(self):
        """Test that entries expire after TTL."""
        self.cache.put("key1", "value1")
        time.sleep(1.1)  # Wait for TTL to expire
        
        result = self.cache.get("key1")
        self.assertIsNone(result)
        
    def test_lru_eviction(self):
        """Test LRU eviction policy."""
        # Fill cache to max size
        for i in range(5):
            self.cache.put(f"key{i}", f"value{i}")
            
        # Add one more item
        self.cache.put("key5", "value5")
        
        # First item should be evicted
        result = self.cache.get("key0")
        self.assertIsNone(result)
        
        # Last item should still be present
        result = self.cache.get("key5")
        self.assertIsNotNone(result)
        
    def test_strong_consistency(self):
        """Test strong consistency behavior."""
        cache = CacheStore(consistency_level=ConsistencyLevel.STRONG)
        
        # Put with strong consistency
        version = cache.put("key1", "value1", ConsistencyLevel.STRONG)
        
        # Should be immediately available
        result = cache.get("key1", ConsistencyLevel.STRONG)
        self.assertIsNotNone(result)
        value, cached_version = result
        self.assertEqual(value, "value1")
        self.assertEqual(version, cached_version)
        
    def test_session_consistency(self):
        """Test session-level consistency."""
        session_id = "session1"
        
        # Put with session consistency
        version = self.cache.put(
            "key1",
            "value1",
            ConsistencyLevel.SESSION,
            session_id
        )
        
        # Should be available in same session
        result = self.cache.get(
            "key1",
            ConsistencyLevel.SESSION,
            session_id
        )
        self.assertIsNotNone(result)
        
        # Should not be available in different session
        result = self.cache.get(
            "key1",
            ConsistencyLevel.SESSION,
            "different_session"
        )
        self.assertIsNone(result)
        
    def test_dirty_tracking(self):
        """Test tracking of dirty entries."""
        # Put with eventual consistency (should be marked dirty)
        self.cache.put("key1", "value1", ConsistencyLevel.EVENTUAL)
        
        dirty_entries = self.cache.get_dirty_entries()
        self.assertEqual(len(dirty_entries), 1)
        self.assertIn("key1", dirty_entries)
        
        # Mark as synced
        value, version = dirty_entries["key1"]
        self.cache.mark_synced("key1", version)
        
        # Should no longer be dirty
        dirty_entries = self.cache.get_dirty_entries()
        self.assertEqual(len(dirty_entries), 0)
        
    def test_invalidate(self):
        """Test cache invalidation."""
        self.cache.put("key1", "value1")
        self.cache.invalidate("key1")
        
        result = self.cache.get("key1")
        self.assertIsNone(result)
        
    def test_clear(self):
        """Test clearing the entire cache."""
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        
        self.cache.clear()
        
        result1 = self.cache.get("key1")
        result2 = self.cache.get("key2")
        self.assertIsNone(result1)
        self.assertIsNone(result2)
        
    def test_get_stats(self):
        """Test retrieving cache statistics."""
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2", ConsistencyLevel.EVENTUAL)
        
        stats = self.cache.get_stats()
        self.assertEqual(stats["size"], 2)
        self.assertEqual(stats["max_size"], 5)
        self.assertEqual(stats["dirty_entries"], 1)
        self.assertEqual(stats["consistency_level"], "eventual")
