"""Test configuration for metrics integration tests."""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock
import asyncio

# Mock prometheus_client before any other imports
prometheus_mock = MagicMock()
prometheus_mock.Counter = MagicMock
prometheus_mock.Gauge = MagicMock
prometheus_mock.Histogram = MagicMock
prometheus_mock.Summary = MagicMock
prometheus_mock.generate_latest = MagicMock
prometheus_mock.CONTENT_TYPE_LATEST = "text/plain"

sys.modules['prometheus_client'] = prometheus_mock
sys.modules['prometheus_client.metrics'] = prometheus_mock
sys.modules['prometheus_client.registry'] = prometheus_mock

# Add project root and simulation directory to Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SIMULATION_PATH = PROJECT_ROOT / "dev"
sys.path.insert(0, str(SIMULATION_PATH))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def test_nodes():
    """Create a test set of nodes in different regions."""
    from simulation import NodeLocation
    return {
        "node1": NodeLocation("us-east", "us-east-1a", "aws", 5),
        "node2": NodeLocation("us-west", "us-west-1b", "aws", 5),
        "edge1": NodeLocation("us-east", "mobile-east", "edge", 20),
    }

@pytest.fixture
async def metrics_collector(test_nodes, event_loop):
    """Create a metrics collector with test nodes."""
    from simulation import SimulatedMetricsCollector
    collector = SimulatedMetricsCollector(test_nodes)
    yield collector
    await collector.cleanup()  # Clean up any resources after tests
