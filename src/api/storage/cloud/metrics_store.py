"""Module for storing and retrieving cloud provider metrics."""
import sqlite3
import json
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from src.api.storage.cloud.types import ProviderHealth

logger = logging.getLogger(__name__)

class MetricsStore:
    """Class for storing and retrieving cloud provider metrics."""

    def __init__(self, db_path: str):
        """Initialize the metrics store.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS provider_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider_name TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        latency_ms TEXT,
                        health_status TEXT,
                        error_count INTEGER,
                        success_count INTEGER,
                        cost_per_gb REAL,
                        UNIQUE(provider_name, timestamp)
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize metrics database: {e}")
            raise

    def store_metrics(self, provider_name: str, metrics: Dict[str, Any]) -> bool:
        """Store metrics for a provider.
        
        Args:
            provider_name: Name of the cloud provider
            metrics: Dictionary containing provider metrics
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO provider_metrics (
                        provider_name, timestamp, latency_ms, health_status,
                        error_count, success_count, cost_per_gb
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    provider_name,
                    datetime.now().isoformat(),
                    json.dumps(metrics['latency_ms']),
                    metrics['health_status'],
                    metrics['error_count'],
                    metrics['success_count'],
                    metrics['cost_per_gb']
                ))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to store metrics for provider {provider_name}: {e}")
            return False

    def get_provider_metrics(
        self,
        provider_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get metrics for a provider within a time range.
        
        Args:
            provider_name: Name of the cloud provider
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            
        Returns:
            List of metrics dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT timestamp, latency_ms, health_status,
                           error_count, success_count, cost_per_gb
                    FROM provider_metrics
                    WHERE provider_name = ?
                """
                params = [provider_name]
                
                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())
                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                return [{
                    'timestamp': datetime.fromisoformat(row[0]),
                    'latency_ms': json.loads(row[1]),
                    'health_status': row[2],
                    'error_count': row[3],
                    'success_count': row[4],
                    'cost_per_gb': row[5]
                } for row in rows]
                
        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve metrics for provider {provider_name}: {e}")
            return []

    def get_provider_stats(
        self,
        provider_name: str,
        timeframe: str
    ) -> Dict[str, Union[str, int, float]]:
        """Get aggregated statistics for a provider.
        
        Args:
            provider_name: Name of the cloud provider
            timeframe: Time range for statistics (e.g., "24h", "7d", "30d")
            
        Returns:
            Dictionary containing aggregated statistics
            
        Raises:
            ValueError: If timeframe is invalid
        """
        # Convert timeframe to timedelta
        try:
            if timeframe.endswith('h'):
                delta = timedelta(hours=int(timeframe[:-1]))
            elif timeframe.endswith('d'):
                delta = timedelta(days=int(timeframe[:-1]))
            else:
                raise ValueError(f"Invalid timeframe format: {timeframe}")
        except ValueError as e:
            logger.error(f"Invalid timeframe: {timeframe}")
            raise ValueError(f"Invalid timeframe: {timeframe}") from e
        
        start_time = datetime.now() - delta
        metrics = self.get_provider_metrics(
            provider_name,
            start_time=start_time
        )
        
        if not metrics:
            return {
                'timeframe': timeframe,
                'total_errors': 0,
                'total_successes': 0,
                'avg_cost': 0.0,
                'success_rate': 0.0
            }
        
        total_errors = sum(m['error_count'] for m in metrics)
        total_successes = sum(m['success_count'] for m in metrics)
        avg_cost = sum(m['cost_per_gb'] for m in metrics) / len(metrics)
        
        total_ops = total_errors + total_successes
        success_rate = total_successes / total_ops if total_ops > 0 else 0.0
        
        return {
            'timeframe': timeframe,
            'total_errors': total_errors,
            'total_successes': total_successes,
            'avg_cost': avg_cost,
            'success_rate': success_rate
        }
