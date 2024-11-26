"""Unit tests for the Load Manager component."""

import pytest
import time
from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from typing import NamedTuple

from storage.infrastructure.load_manager import LoadManager, LoadMetrics

class MockDiskIO(NamedTuple):
    read_bytes: int
    write_bytes: int

class MockNetIO(NamedTuple):
    bytes_sent: int
    bytes_recv: int

class MockMemory(NamedTuple):
    percent: float

@pytest.fixture
def load_manager():
    """Create a LoadManager instance with default settings."""
    return LoadManager()

@pytest.fixture
def custom_load_manager():
    """Create a LoadManager instance with custom thresholds."""
    return LoadManager(
        max_cpu_threshold=70.0,
        max_memory_threshold=75.0,
        max_requests_per_second=500.0
    )

class TestLoadManager:
    def test_initialization(self, load_manager, custom_load_manager):
        """Test LoadManager initialization with default and custom values."""
        # Test default values
        assert load_manager.max_cpu_threshold == 80.0
        assert load_manager.max_memory_threshold == 80.0
        assert load_manager.max_requests_per_second == 1000.0

        # Test custom values
        assert custom_load_manager.max_cpu_threshold == 70.0
        assert custom_load_manager.max_memory_threshold == 75.0
        assert custom_load_manager.max_requests_per_second == 500.0

    def test_record_request(self, load_manager):
        """Test request recording and cleanup."""
        # Record some requests
        load_manager.record_request()
        load_manager.record_request()
        
        assert len(load_manager.request_timestamps) == 2
        
        # Verify timestamps are recent
        current_time = time.time()
        for ts in load_manager.request_timestamps:
            assert current_time - ts < 1.0

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_io_counters')
    @patch('psutil.net_io_counters')
    def test_get_current_metrics(self, mock_net_io, mock_disk_io, mock_memory, mock_cpu, load_manager):
        """Test metrics collection."""
        # Mock system metrics
        mock_cpu.return_value = 50.0
        mock_memory.return_value = MockMemory(percent=60.0)
        mock_disk_io.return_value = MockDiskIO(read_bytes=1000, write_bytes=2000)
        mock_net_io.return_value = MockNetIO(bytes_sent=3000, bytes_recv=4000)

        # Get metrics
        metrics = load_manager.get_current_metrics()

        # Verify metrics
        assert isinstance(metrics, LoadMetrics)
        assert metrics.cpu_usage == 50.0
        assert metrics.memory_usage == 60.0
        assert metrics.timestamp > 0

        # Verify metrics history
        assert len(load_manager.metrics_history) > 0
        assert metrics.timestamp in load_manager.metrics_history

    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_io_counters')
    @patch('psutil.net_io_counters')
    def test_can_handle_request(self, mock_net_io, mock_disk_io, mock_memory, mock_cpu, load_manager):
        """Test request handling capacity check."""
        # Mock metrics below thresholds
        mock_cpu.return_value = 70.0
        mock_memory.return_value = MockMemory(percent=70.0)
        mock_disk_io.return_value = MockDiskIO(read_bytes=1000, write_bytes=2000)
        mock_net_io.return_value = MockNetIO(bytes_sent=3000, bytes_recv=4000)

        # Should be able to handle request
        assert load_manager.can_handle_request() is True

        # Mock metrics above thresholds
        mock_cpu.return_value = 90.0
        mock_memory.return_value = MockMemory(percent=90.0)

        # Should not be able to handle request
        assert load_manager.can_handle_request() is False

    def test_get_current_load(self, load_manager):
        """Test load calculation."""
        with patch.object(load_manager, 'get_current_metrics') as mock_metrics:
            mock_metrics.return_value = LoadMetrics(
                cpu_usage=50.0,
                memory_usage=60.0,
                disk_io=70.0,
                network_io=80.0,
                request_rate=100.0,
                timestamp=time.time()
            )

            load = load_manager.get_current_load()
            assert 0 <= load <= 1.0

    def test_get_capacity(self, load_manager):
        """Test capacity calculation."""
        with patch.object(load_manager, 'get_current_load') as mock_load:
            mock_load.return_value = 0.7
            capacity = load_manager.get_capacity()
            assert abs(capacity - 0.3) < 0.0001  # Use floating point comparison

    def test_predict_load_trend(self, load_manager):
        """Test load trend prediction."""
        # Add some historical metrics
        current_time = time.time()
        
        metrics1 = LoadMetrics(
            cpu_usage=50.0,
            memory_usage=60.0,
            disk_io=70.0,
            network_io=80.0,
            request_rate=100.0,
            timestamp=current_time - 30
        )
        
        metrics2 = LoadMetrics(
            cpu_usage=60.0,
            memory_usage=70.0,
            disk_io=80.0,
            network_io=90.0,
            request_rate=150.0,
            timestamp=current_time
        )

        load_manager.metrics_history[metrics1.timestamp] = metrics1
        load_manager.metrics_history[metrics2.timestamp] = metrics2

        trend = load_manager.predict_load_trend(window_seconds=60.0)
        assert trend is not None
        # Trend should be positive since load increased
        assert trend > 0

    def test_metrics_history_cleanup(self, load_manager):
        """Test cleanup of old metrics."""
        current_time = time.time()
        
        # Add old metrics (> 5 minutes old)
        old_metrics = LoadMetrics(
            cpu_usage=50.0,
            memory_usage=60.0,
            disk_io=70.0,
            network_io=80.0,
            request_rate=100.0,
            timestamp=current_time - 400  # > 5 minutes old
        )
        
        # Add recent metrics
        recent_metrics = LoadMetrics(
            cpu_usage=60.0,
            memory_usage=70.0,
            disk_io=80.0,
            network_io=90.0,
            request_rate=150.0,
            timestamp=current_time
        )

        load_manager.metrics_history[old_metrics.timestamp] = old_metrics
        load_manager.metrics_history[recent_metrics.timestamp] = recent_metrics

        # Get current metrics to trigger cleanup
        load_manager.get_current_metrics()

        # Verify old metrics were cleaned up
        assert old_metrics.timestamp not in load_manager.metrics_history
        assert recent_metrics.timestamp in load_manager.metrics_history
