"""Performance tests for hybrid storage system."""
import os
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pytest
import json
import logging
import datetime
from pathlib import Path

from ..common.hybrid_storage_fixtures import (
    aws_credentials,
    s3_client,
    hybrid_storage_manager,
    haproxy_container,
    storage_protocol_context
)

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.performance, pytest.mark.slow]

class TestHybridStoragePerformance:
    """Performance tests for hybrid storage functionality."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test environment before each test."""
        self.performance_metrics = {}
        self.test_dir = "/tmp/hybrid_storage_test"

    @pytest.mark.asyncio
    async def test_protocol_performance(self, hybrid_storage_manager):
        """Test performance of different storage protocols."""
        file_sizes = [1024, 1024*1024, 10*1024*1024]  # 1KB, 1MB, 10MB
        protocols = ["iscsi", "nfs", "cifs"]
        results = {}

        for size in file_sizes:
            test_data = os.urandom(size)
            for protocol in protocols:
                write_times = []
                read_times = []
                
                # Perform multiple iterations for statistical significance
                for _ in range(10):
                    file_path = f"perf_test_{size}_{time.time()}.bin"
                    
                    # Measure write performance
                    start_time = time.time()
                    await hybrid_storage_manager.write_file(file_path, test_data, protocol=protocol)
                    write_time = time.time() - start_time
                    write_times.append(write_time)
                    
                    # Measure read performance
                    start_time = time.time()
                    await hybrid_storage_manager.read_file(file_path, protocol=protocol)
                    read_time = time.time() - start_time
                    read_times.append(read_time)
                
                results[f"{protocol}_{size}"] = {
                    "write_avg": statistics.mean(write_times),
                    "write_std": statistics.stdev(write_times),
                    "read_avg": statistics.mean(read_times),
                    "read_std": statistics.stdev(read_times),
                    "throughput_write": size / statistics.mean(write_times),
                    "throughput_read": size / statistics.mean(read_times)
                }
        
        return results

    @pytest.mark.asyncio
    async def test_concurrent_performance(self, hybrid_storage_manager):
        """Test performance under concurrent load."""
        concurrent_levels = [10, 50, 100]
        file_size = 1024 * 1024  # 1MB
        test_data = os.urandom(file_size)
        results = {}

        for num_concurrent in concurrent_levels:
            async def worker():
                file_path = f"concurrent_perf_{time.time()}.bin"
                start_time = time.time()
                await hybrid_storage_manager.write_file(file_path, test_data)
                await hybrid_storage_manager.read_file(file_path)
                return time.time() - start_time

            # Create concurrent tasks
            tasks = [worker() for _ in range(num_concurrent)]
            completion_times = await asyncio.gather(*tasks)
            
            results[f"concurrent_{num_concurrent}"] = {
                "avg_time": statistics.mean(completion_times),
                "std_time": statistics.stdev(completion_times),
                "throughput": (file_size * num_concurrent) / max(completion_times)
            }
        
        return results

    @pytest.mark.asyncio
    async def test_tiering_performance(self, hybrid_storage_manager):
        """Test performance of cloud tiering operations."""
        file_sizes = [1024*1024, 10*1024*1024, 100*1024*1024]  # 1MB, 10MB, 100MB
        results = {}

        for size in file_sizes:
            test_data = os.urandom(size)
            file_path = f"tier_test_{size}.bin"
            
            # Measure write to local
            start_time = time.time()
            await hybrid_storage_manager.write_file(file_path, test_data)
            local_write_time = time.time() - start_time
            
            # Wait for tiering
            time.sleep(5)
            
            # Measure read from cloud
            start_time = time.time()
            await hybrid_storage_manager.read_file(file_path)
            cloud_read_time = time.time() - start_time
            
            results[f"tier_{size}"] = {
                "local_write_time": local_write_time,
                "cloud_read_time": cloud_read_time,
                "local_write_throughput": size / local_write_time,
                "cloud_read_throughput": size / cloud_read_time
            }
        
        return results

    @pytest.mark.asyncio
    async def test_protocol_switching_overhead(self, hybrid_storage_manager):
        """Test performance overhead of switching between protocols."""
        file_name = "switch_test.bin"
        data = os.urandom(1024 * 1024)  # 1MB test file
        
        # Write initial file with iSCSI
        await hybrid_storage_manager.write_file(file_name, data, protocol="iscsi")
        
        # Measure time to switch protocols
        start_time = time.time()
        await hybrid_storage_manager.switch_protocol(file_name, "iscsi", "nfs")
        switch_time = time.time() - start_time
        
        # Verify data integrity
        nfs_data = await hybrid_storage_manager.read_file(file_name, protocol="nfs")
        assert nfs_data == data, "Data integrity check failed after protocol switch"
        
        # Log performance metrics
        logger.info(f"Protocol switch time: {switch_time:.4f} seconds")
        self.performance_metrics["protocol_switch_time"] = switch_time

    @pytest.mark.asyncio
    async def test_failover_performance(self, hybrid_storage_manager, haproxy_container):
        """Test performance of storage failover."""
        file_name = "failover_test.bin"
        data = os.urandom(1024 * 1024)  # 1MB test file
        
        # Write to primary protocol
        await hybrid_storage_manager.write_file(file_name, data, protocol="iscsi")
        
        # Test failover performance
        start_time = time.time()
        failover_data = await hybrid_storage_manager.failover(file_name, "iscsi", "nfs")
        failover_time = time.time() - start_time
        
        # Verify data integrity
        assert failover_data == data, "Data integrity check failed during failover"
        
        # Log performance metrics
        logger.info(f"Failover time: {failover_time:.4f} seconds")
        self.performance_metrics["failover_time"] = failover_time

    @pytest.mark.asyncio
    async def test_generate_performance_report(self, tmp_path, hybrid_storage_manager, haproxy_container):
        """Generate comprehensive performance report."""
        # Ensure all performance tests have run
        await self.test_protocol_performance(hybrid_storage_manager)
        await self.test_concurrent_performance(hybrid_storage_manager)
        await self.test_tiering_performance(hybrid_storage_manager)
        await self.test_protocol_switching_overhead(hybrid_storage_manager)
        await self.test_failover_performance(hybrid_storage_manager, haproxy_container)
        
        # Generate report
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "metrics": self.performance_metrics,
            "summary": {
                "avg_write_speed": sum(self.performance_metrics.get("write_speeds", [])) / len(self.performance_metrics.get("write_speeds", [1])),
                "avg_read_speed": sum(self.performance_metrics.get("read_speeds", [])) / len(self.performance_metrics.get("read_speeds", [1])),
                "protocol_switch_overhead": self.performance_metrics.get("protocol_switch_time", 0),
                "failover_time": self.performance_metrics.get("failover_time", 0)
            }
        }
        
        # Save report to file
        report_path = Path(tmp_path) / "performance_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Performance report generated: {report_path}")
