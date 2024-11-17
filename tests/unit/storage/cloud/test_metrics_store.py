"""Unit tests for metrics persistence."""
import unittest
import tempfile
import os
from datetime import datetime, timedelta
from src.api.storage.cloud.metrics_store import MetricsStore
from src.api.storage.cloud.hybrid import ProviderHealth
import sqlite3
import json

class TestMetricsStore(unittest.TestCase):
    """Test cases for metrics persistence."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary database file
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_metrics.db")
        self.metrics_store = MetricsStore(self.db_path)
        
        # Sample metrics data
        self.sample_metrics = {
            'latency_ms': [50, 45, 60],
            'error_count': 1,
            'success_count': 100,
            'health_status': ProviderHealth.HEALTHY.value,
            'cost_per_gb': 0.023
        }
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)
    
    def test_store_metrics(self):
        """Test storing metrics in the database."""
        # Store metrics
        success = self.metrics_store.store_metrics("aws", self.sample_metrics)
        self.assertTrue(success)
        
        # Retrieve metrics
        metrics = self.metrics_store.get_provider_metrics("aws")
        self.assertEqual(len(metrics), 1)
        
        stored_metrics = metrics[0]
        self.assertEqual(stored_metrics['latency_ms'], self.sample_metrics['latency_ms'])
        self.assertEqual(stored_metrics['error_count'], self.sample_metrics['error_count'])
        self.assertEqual(stored_metrics['success_count'], self.sample_metrics['success_count'])
        self.assertEqual(stored_metrics['health_status'], self.sample_metrics['health_status'])
        self.assertAlmostEqual(stored_metrics['cost_per_gb'], self.sample_metrics['cost_per_gb'])
    
    def test_get_provider_metrics_time_range(self):
        """Test retrieving metrics within a time range."""
        # Store metrics with different timestamps
        now = datetime.now()
        
        # Old metrics (8 days ago)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            old_time = (now - timedelta(days=8)).isoformat()
            cursor.execute("""
                INSERT INTO provider_metrics (
                    provider_name, timestamp, latency_ms, health_status,
                    error_count, success_count, cost_per_gb
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                "aws",
                old_time,
                json.dumps([50, 45, 60]),
                ProviderHealth.HEALTHY.value,
                2,  # error_count
                100,
                0.023
            ))
            
            # Recent metrics (1 day ago)
            recent_time = (now - timedelta(days=1)).isoformat()
            cursor.execute("""
                INSERT INTO provider_metrics (
                    provider_name, timestamp, latency_ms, health_status,
                    error_count, success_count, cost_per_gb
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                "aws",
                recent_time,
                json.dumps([50, 45, 60]),
                ProviderHealth.HEALTHY.value,
                1,  # error_count
                100,
                0.023
            ))
            conn.commit()
        
        # Get metrics for last 7 days
        metrics = self.metrics_store.get_provider_metrics(
            "aws",
            start_time=now - timedelta(days=7),
            end_time=now
        )
        
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]['error_count'], 1)
    
    def test_get_provider_stats(self):
        """Test retrieving aggregated provider statistics."""
        # Store multiple metrics entries
        for _ in range(3):
            self.metrics_store.store_metrics("aws", self.sample_metrics)
        
        # Get stats for last 24 hours
        stats = self.metrics_store.get_provider_stats("aws", "24h")
        
        self.assertEqual(stats['timeframe'], "24h")
        self.assertEqual(stats['total_errors'], 3)  # 1 error * 3 entries
        self.assertEqual(stats['total_successes'], 300)  # 100 successes * 3 entries
        self.assertAlmostEqual(stats['avg_cost'], 0.023, places=6)
        self.assertAlmostEqual(stats['success_rate'], 0.99, places=2)
    
    def test_invalid_timeframe(self):
        """Test handling of invalid timeframe."""
        with self.assertRaises(ValueError):
            self.metrics_store.get_provider_stats("aws", "invalid")
