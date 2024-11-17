"""Unit tests for hybrid cloud management."""
import unittest
from unittest.mock import Mock, patch
import io
from datetime import datetime
from src.api.storage.cloud.hybrid import (
    HybridCloudManager,
    ProviderPriority,
    ProviderHealth,
    RoutingStrategy,
    ProviderMetrics
)
from src.api.storage.cloud.providers import CloudStorageProvider

class TestHybridCloudManager(unittest.TestCase):
    """Test cases for hybrid cloud management."""
    
    def setUp(self):
        """Set up test environment."""
        self.manager = HybridCloudManager(RoutingStrategy.BALANCED)
        
        # Create mock providers
        self.aws_provider = Mock(spec=CloudStorageProvider)
        self.azure_provider = Mock(spec=CloudStorageProvider)
        self.gcp_provider = Mock(spec=CloudStorageProvider)
        
        # Add providers with different priorities and costs
        self.manager.add_provider("aws", self.aws_provider, ProviderPriority.PRIMARY, 0.023)
        self.manager.add_provider("azure", self.azure_provider, ProviderPriority.SECONDARY, 0.018)
        self.manager.add_provider("gcp", self.gcp_provider, ProviderPriority.FALLBACK, 0.026)
    
    def test_cost_optimized_routing(self):
        """Test cost-optimized provider selection."""
        manager = HybridCloudManager(RoutingStrategy.COST_OPTIMIZED)
        manager.add_provider("aws", self.aws_provider, ProviderPriority.PRIMARY, 0.023)
        manager.add_provider("azure", self.azure_provider, ProviderPriority.SECONDARY, 0.018)
        
        # Azure should be selected as it has lower cost
        test_data = b"test data"
        manager.upload_file(test_data, "test.txt", "test-bucket")
        
        self.azure_provider.upload_file.assert_called_once()
        self.aws_provider.upload_file.assert_not_called()
    
    def test_latency_optimized_routing(self):
        """Test latency-optimized provider selection."""
        manager = HybridCloudManager(RoutingStrategy.LATENCY_OPTIMIZED)
        manager.add_provider("aws", self.aws_provider, ProviderPriority.PRIMARY, 0.023)
        manager.add_provider("azure", self.azure_provider, ProviderPriority.SECONDARY, 0.018)
        
        # Update latency metrics
        manager.metrics["aws"].update_latency(50)  # 50ms
        manager.metrics["azure"].update_latency(100)  # 100ms
        
        # AWS should be selected as it has lower latency
        test_data = b"test data"
        manager.upload_file(test_data, "test.txt", "test-bucket")
        
        self.aws_provider.upload_file.assert_called_once()
        self.azure_provider.upload_file.assert_not_called()
    
    def test_availability_optimized_routing(self):
        """Test availability-optimized provider selection."""
        manager = HybridCloudManager(RoutingStrategy.AVAILABILITY_OPTIMIZED)
        manager.add_provider("aws", self.aws_provider, ProviderPriority.PRIMARY, 0.023)
        manager.add_provider("azure", self.azure_provider, ProviderPriority.SECONDARY, 0.018)
        
        # Make AWS unhealthy
        manager.metrics["aws"].record_error("Test error")
        manager.metrics["aws"].record_error("Another error")
        
        # Azure should be selected as AWS is unhealthy
        test_data = b"test data"
        manager.upload_file(test_data, "test.txt", "test-bucket")
        
        self.azure_provider.upload_file.assert_called_once()
        self.aws_provider.upload_file.assert_not_called()
    
    def test_replication(self):
        """Test data replication across providers."""
        self.manager.enable_replication(True)
        test_data = b"test data"
        
        # Configure all providers to succeed
        self.aws_provider.upload_file.return_value = True
        self.azure_provider.upload_file.return_value = True
        self.gcp_provider.upload_file.return_value = True
        
        self.manager.upload_file(test_data, "test.txt", "test-bucket")
        
        # Verify all providers were called
        self.aws_provider.upload_file.assert_called_once()
        self.azure_provider.upload_file.assert_called_once()
        self.gcp_provider.upload_file.assert_called_once()
    
    def test_failover(self):
        """Test failover to backup providers."""
        test_data = b"test data"
        
        # Make primary provider fail
        self.aws_provider.upload_file.return_value = False
        self.azure_provider.upload_file.return_value = True
        
        success = self.manager.upload_file(test_data, "test.txt", "test-bucket")
        
        self.assertTrue(success)
        self.aws_provider.upload_file.assert_called_once()
        self.azure_provider.upload_file.assert_called_once()
    
    def test_metrics_tracking(self):
        """Test provider metrics tracking."""
        test_data = b"test data"
        
        # Successful upload
        self.aws_provider.upload_file.return_value = True
        self.manager.upload_file(test_data, "test.txt", "test-bucket")
        
        # Failed upload
        self.aws_provider.upload_file.side_effect = Exception("Test error")
        self.manager.upload_file(test_data, "test2.txt", "test-bucket")
        
        metrics = self.manager.get_provider_health()["aws"]
        self.assertEqual(metrics["success_count"], 1)
        self.assertEqual(metrics["error_count"], 1)
        self.assertEqual(metrics["last_error"], "Test error")
    
    def test_replication_status(self):
        """Test replication status checking."""
        # Configure mock responses
        self.aws_provider.download_file.return_value = b"data"
        self.azure_provider.download_file.return_value = b"data"
        self.gcp_provider.download_file.return_value = None
        
        status = self.manager.get_replication_status("test.txt", "test-bucket")
        
        self.assertTrue(status["aws"])
        self.assertTrue(status["azure"])
        self.assertFalse(status["gcp"])
    
    def test_balanced_routing(self):
        """Test balanced routing strategy."""
        manager = HybridCloudManager(RoutingStrategy.BALANCED)
        manager.add_provider("aws", self.aws_provider, ProviderPriority.PRIMARY, 0.023)
        manager.add_provider("azure", self.azure_provider, ProviderPriority.SECONDARY, 0.018)
        
        # Update metrics
        manager.metrics["aws"].update_latency(50)  # Good latency
        manager.metrics["aws"].record_success()    # Good health
        
        manager.metrics["azure"].update_latency(40)  # Better latency
        manager.metrics["azure"].record_error("Test error")  # Poor health
        
        # AWS should be selected due to balanced scoring
        test_data = b"test data"
        manager.upload_file(test_data, "test.txt", "test-bucket")
        
        self.aws_provider.upload_file.assert_called_once()
        self.azure_provider.upload_file.assert_not_called()

if __name__ == '__main__':
    unittest.main()
