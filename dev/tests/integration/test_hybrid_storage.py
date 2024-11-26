"""Integration tests for hybrid storage functionality."""
import pytest
import os
from pathlib import Path
import asyncio
import json
import time

from ..common.hybrid_storage_fixtures import storage_protocol_context

pytestmark = pytest.mark.integration

class TestHybridStorage:
    """Test hybrid storage functionality."""

    @pytest.mark.asyncio
    async def test_storage_protocol_switching(self, hybrid_storage_manager):
        """Test automatic switching between storage protocols."""
        # Test data
        test_data = b"Hello, Hybrid Storage!"
        file_path = "test_file.txt"
        
        # Write data using different protocols
        protocols = ["iscsi", "nfs", "cifs"]
        for protocol in protocols:
            await hybrid_storage_manager.write_file(file_path, test_data, protocol=protocol)
            read_data = await hybrid_storage_manager.read_file(file_path, protocol=protocol)
            assert read_data == test_data

    @pytest.mark.asyncio
    async def test_cloud_tiering(self, hybrid_storage_manager, s3_client, test_bucket):
        """Test cloud tiering functionality."""
        # Create large test file
        large_data = os.urandom(10 * 1024 * 1024)  # 10MB
        file_path = "large_file.bin"
        
        # Write to local storage
        await hybrid_storage_manager.write_file(file_path, large_data)
        
        # Wait for tiering policy to trigger
        time.sleep(5)
        
        # Verify file is tiered to S3
        s3_objects = s3_client.list_objects_v2(Bucket=test_bucket)
        assert any(obj["Key"] == file_path for obj in s3_objects.get("Contents", []))
        
        # Read should still work transparently
        read_data = await hybrid_storage_manager.read_file(file_path)
        assert read_data == large_data

    @pytest.mark.asyncio
    async def test_protocol_failover(self, hybrid_storage_manager, haproxy_container):
        """Test failover between storage protocols."""
        test_data = b"Failover Test Data"
        file_path = "failover_test.txt"
        
        # Write using primary protocol
        await hybrid_storage_manager.write_file(file_path, test_data, protocol="iscsi")
        
        # Simulate primary protocol failure
        haproxy_container.exec_run("kill -STOP 1")  # Pause HAProxy
        
        # Read should automatically failover to alternative protocol
        read_data = await hybrid_storage_manager.read_file(file_path)
        assert read_data == test_data
        
        # Restore HAProxy
        haproxy_container.exec_run("kill -CONT 1")

    @pytest.mark.asyncio
    async def test_concurrent_access(self, hybrid_storage_manager):
        """Test concurrent access using different protocols."""
        test_file = "concurrent_test.txt"
        num_operations = 100
        
        async def write_operation(i):
            data = f"Data {i}".encode()
            await hybrid_storage_manager.write_file(f"{test_file}_{i}", data)
            return i
        
        async def read_operation(i):
            data = await hybrid_storage_manager.read_file(f"{test_file}_{i}")
            assert data == f"Data {i}".encode()
            return i
        
        # Create concurrent write operations
        write_tasks = [write_operation(i) for i in range(num_operations)]
        await asyncio.gather(*write_tasks)
        
        # Create concurrent read operations
        read_tasks = [read_operation(i) for i in range(num_operations)]
        await asyncio.gather(*read_tasks)

    @pytest.mark.asyncio
    async def test_data_consistency(self, hybrid_storage_manager):
        """Test data consistency across protocols."""
        test_data = b"Consistency Test Data"
        file_path = "consistency_test.txt"
        
        # Write using one protocol
        await hybrid_storage_manager.write_file(file_path, test_data, protocol="iscsi")
        
        # Read using different protocols
        for protocol in ["nfs", "cifs"]:
            with storage_protocol_context(protocol, share=hybrid_storage_manager.get_share(protocol)):
                read_data = await hybrid_storage_manager.read_file(file_path, protocol=protocol)
                assert read_data == test_data

    @pytest.mark.asyncio
    async def test_large_file_handling(self, hybrid_storage_manager):
        """Test handling of large files."""
        # Create large test file (100MB)
        large_data = os.urandom(100 * 1024 * 1024)
        file_path = "large_test.bin"
        
        # Test different protocols with large file
        for protocol in ["iscsi", "nfs", "cifs"]:
            # Write large file
            await hybrid_storage_manager.write_file(file_path, large_data, protocol=protocol)
            
            # Read in chunks
            chunk_size = 1024 * 1024  # 1MB chunks
            offset = 0
            chunks = []
            
            while offset < len(large_data):
                chunk = await hybrid_storage_manager.read_file(
                    file_path,
                    protocol=protocol,
                    offset=offset,
                    length=chunk_size
                )
                chunks.append(chunk)
                offset += chunk_size
            
            # Verify data integrity
            reconstructed_data = b"".join(chunks)
            assert reconstructed_data == large_data

    @pytest.mark.asyncio
    async def test_metadata_sync(self, hybrid_storage_manager):
        """Test metadata synchronization across protocols."""
        file_path = "metadata_test.txt"
        test_data = b"Metadata Test"
        metadata = {
            "owner": "test_user",
            "permissions": "rw-r--r--",
            "tags": ["test", "hybrid", "storage"]
        }
        
        # Write file with metadata
        await hybrid_storage_manager.write_file(
            file_path,
            test_data,
            metadata=metadata,
            protocol="iscsi"
        )
        
        # Verify metadata across protocols
        for protocol in ["nfs", "cifs"]:
            read_metadata = await hybrid_storage_manager.get_metadata(
                file_path,
                protocol=protocol
            )
            assert read_metadata == metadata

    @pytest.mark.asyncio
    async def test_error_handling(self, hybrid_storage_manager):
        """Test error handling and recovery."""
        test_data = b"Error Handling Test"
        file_path = "error_test.txt"
        
        # Test invalid protocol
        with pytest.raises(ValueError):
            await hybrid_storage_manager.write_file(
                file_path,
                test_data,
                protocol="invalid"
            )
        
        # Test invalid path
        with pytest.raises(FileNotFoundError):
            await hybrid_storage_manager.read_file("nonexistent.txt")
        
        # Test recovery after error
        await hybrid_storage_manager.write_file(file_path, test_data)
        read_data = await hybrid_storage_manager.read_file(file_path)
        assert read_data == test_data
