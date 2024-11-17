import asyncio
import aiohttp
import random
import logging
import pytest
from datetime import datetime
import docker
from tests.test_utils import create_mock_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
async def dfs_test_setup():
    """Setup test environment"""
    docker_client = docker.from_env()
    core_nodes = [
        "distributedfilesystem-node1-1",
        "distributedfilesystem-node2-1",
        "distributedfilesystem-node3-1"
    ]
    edge_nodes = [
        "distributedfilesystem-edge1-1",
        "distributedfilesystem-edge2-1"
    ]
    test_data = b"Test data content " * 1000
    mock_provider = create_mock_provider()

    setup_data = {
        "docker_client": docker_client,
        "core_nodes": core_nodes,
        "edge_nodes": edge_nodes,
        "test_data": test_data,
        "mock_provider": mock_provider
    }

    return setup_data

@pytest.mark.asyncio
async def test_basic_operations(dfs_test_setup):
    """Test basic operations using S3-compatible API"""
    logger.info("Testing basic operations...")
    setup_data = await dfs_test_setup
    test_data = setup_data["test_data"]

    async with aiohttp.ClientSession() as session:
        bucket_name = f"test-bucket-{random.randint(1, 1000)}"
        object_key = f"test-object-{random.randint(1, 1000)}"

        # Create bucket
        try:
            async with session.put(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
            ) as create_bucket_response:
                assert create_bucket_response.status == 200, "Bucket creation failed"
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {e}")
            pytest.fail("Failed to connect to the server")

        # Upload object
        headers = {
            'Content-Type': 'application/octet-stream',
            'X-Consistency-Level': 'strong'  # Use strong consistency for basic operations
        }
        async with session.put(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            data=test_data,
            headers=headers
        ) as upload_response:
            assert upload_response.status == 200, "Object upload failed"
            assert 'ETag' in upload_response.headers, "ETag missing in upload response"

        # Get object
        async with session.get(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            headers={'X-Consistency-Level': 'strong'}
        ) as get_response:
            assert get_response.status == 200, "Object retrieval failed"
            assert 'Last-Modified' in get_response.headers, "Last-Modified header missing"
            assert 'ETag' in get_response.headers, "ETag missing in get response"
            response_data = await get_response.read()
            assert response_data == test_data, "Retrieved data does not match uploaded data"

        # Delete object
        async with session.delete(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}"
        ) as delete_response:
            assert delete_response.status == 204, "Object deletion failed"

        # Delete bucket
        async with session.delete(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
        ) as delete_bucket_response:
            assert delete_bucket_response.status == 204, "Bucket deletion failed"

    logger.info("Basic operations test passed!")

@pytest.mark.asyncio
async def test_consistency_levels(dfs_test_setup):
    """Test different consistency levels"""
    logger.info("Testing consistency levels...")
    setup_data = await dfs_test_setup
    test_data = setup_data["test_data"]

    async with aiohttp.ClientSession() as session:
        bucket_name = f"test-bucket-{random.randint(1, 1000)}"
        object_key = f"test-object-{random.randint(1, 1000)}"

        # Create bucket
        async with session.put(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
        ) as create_bucket_response:
            assert create_bucket_response.status == 200, "Bucket creation failed"

        # Test strong consistency
        headers = {
            'Content-Type': 'application/octet-stream',
            'X-Consistency-Level': 'strong'
        }

        # Upload with strong consistency
        async with session.put(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            data=test_data,
            headers=headers
        ) as upload_response:
            assert upload_response.status == 200, "Strong consistency upload failed"
            assert 'ETag' in upload_response.headers, "ETag missing in upload response"

        # Read with strong consistency
        async with session.get(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            headers={'X-Consistency-Level': 'strong'}
        ) as get_response:
            assert get_response.status == 200, "Strong consistency get failed"
            assert 'Last-Modified' in get_response.headers, "Last-Modified header missing"
            response_data = await get_response.read()
            assert response_data == test_data, "Strong consistency data verification failed"

        # Test eventual consistency
        eventual_object_key = f"{object_key}-eventual"
        headers['X-Consistency-Level'] = 'eventual'

        # Upload with eventual consistency
        async with session.put(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{eventual_object_key}",
            data=test_data,
            headers=headers
        ) as upload_response:
            assert upload_response.status == 200, "Eventual consistency upload failed"

        # Read with eventual consistency
        async with session.get(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{eventual_object_key}",
            headers={'X-Consistency-Level': 'eventual'}
        ) as get_response:
            assert get_response.status == 200, "Eventual consistency get failed"
            response_data = await get_response.read()
            assert response_data == test_data, "Eventual consistency data verification failed"

        # Cleanup
        for key in [object_key, eventual_object_key]:
            async with session.delete(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{key}"
            ) as delete_response:
                assert delete_response.status == 204, f"Object deletion failed for {key}"

        async with session.delete(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
        ) as delete_bucket_response:
            assert delete_bucket_response.status == 204, "Bucket deletion failed"

    logger.info("Consistency levels test passed!")

@pytest.mark.asyncio
async def test_edge_computing(dfs_test_setup):
    """Test edge computing scenarios"""
    logger.info("Testing edge computing scenarios...")
    setup_data = await dfs_test_setup
    test_data = setup_data["test_data"]
    edge_nodes = setup_data["edge_nodes"]

    async with aiohttp.ClientSession() as session:
        bucket_name = f"test-bucket-{random.randint(1, 1000)}"
        object_key = f"test-object-{random.randint(1, 1000)}"

        # Create bucket
        async with session.put(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
        ) as create_bucket_response:
            assert create_bucket_response.status == 200, "Bucket creation failed"

        # Upload object to edge node
        headers = {
            'Content-Type': 'application/octet-stream',
            'X-Edge-Node': edge_nodes[0]  # Use first edge node
        }

        async with session.put(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            data=test_data,
            headers=headers
        ) as upload_response:
            assert upload_response.status == 200, "Edge node upload failed"

        # Read from different edge node
        headers = {
            'X-Edge-Node': edge_nodes[1]  # Use second edge node
        }

        async with session.get(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            headers=headers
        ) as get_response:
            assert get_response.status == 200, "Edge node retrieval failed"
            response_data = await get_response.read()
            assert response_data == test_data, "Edge node data verification failed"

        # Test edge node computation
        headers = {
            'X-Edge-Node': edge_nodes[0],
            'X-Edge-Compute': 'true',
            'X-Compute-Function': 'data_transform'  # Example edge function
        }

        async with session.get(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            headers=headers
        ) as compute_response:
            assert compute_response.status == 200, "Edge computation failed"
            compute_result = await compute_response.read()
            assert compute_result is not None, "Edge computation returned no result"

        # Cleanup
        async with session.delete(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}"
        ) as delete_response:
            assert delete_response.status == 204, "Object deletion failed"

        async with session.delete(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
        ) as delete_bucket_response:
            assert delete_bucket_response.status == 204, "Bucket deletion failed"

    logger.info("Edge computing test passed!")

@pytest.mark.asyncio
async def test_failure_scenarios(dfs_test_setup):
    """Test system behavior during failures"""
    logger.info("Testing failure scenarios...")
    setup_data = await dfs_test_setup
    test_data = setup_data["test_data"]
    docker_client = setup_data["docker_client"]
    core_nodes = setup_data["core_nodes"]
    mock_provider = setup_data["mock_provider"]

    async with aiohttp.ClientSession() as session:
        bucket_name = f"test-bucket-{random.randint(1, 1000)}"
        object_key = f"test-object-{random.randint(1, 1000)}"

        # Create bucket
        try:
            async with session.put(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
            ) as create_bucket_response:
                assert create_bucket_response.status == 200, "Bucket creation failed"
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {e}")
            pytest.fail("Failed to connect to the server")

        # Upload initial object
        headers = {
            'Content-Type': 'application/octet-stream',
            'X-Consistency-Level': 'strong'
        }
        async with session.put(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            data=test_data,
            headers=headers
        ) as upload_response:
            assert upload_response.status == 200, "Initial upload failed"

        # Stop one of the core nodes
        container = docker_client.containers.get(core_nodes[1])
        container.stop()
        await asyncio.sleep(5)  # Wait for the system to detect the failure

        try:
            # Try to read with strong consistency - should fail
            async with session.get(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
                headers={'X-Consistency-Level': 'strong'}
            ) as get_response:
                assert get_response.status in [503, 500], "Strong consistency read should fail with node down"

            # Read with eventual consistency - should succeed
            async with session.get(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
                headers={'X-Consistency-Level': 'eventual'}
            ) as get_response:
                assert get_response.status == 200, "Eventual consistency read failed"
                response_data = await get_response.read()
                assert response_data == test_data, "Data verification failed"

            # Try to write with strong consistency - should fail
            new_data = b"Updated test data"
            async with session.put(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
                data=new_data,
                headers={'Content-Type': 'application/octet-stream', 'X-Consistency-Level': 'strong'}
            ) as upload_response:
                assert upload_response.status in [503, 500], "Strong consistency write should fail with node down"

            # Write with eventual consistency - should succeed
            async with session.put(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
                data=new_data,
                headers={'Content-Type': 'application/octet-stream', 'X-Consistency-Level': 'eventual'}
            ) as upload_response:
                assert upload_response.status == 200, "Eventual consistency write failed"

        finally:
            # Restart the stopped node
            container.start()
            await asyncio.sleep(5)  # Wait for the node to recover

            # Verify system returns to normal
            async with session.get(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
                headers={'X-Consistency-Level': 'strong'}
            ) as get_response:
                assert get_response.status == 200, "System did not recover properly"

            # Cleanup
            async with session.delete(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}"
            ) as delete_response:
                assert delete_response.status == 204, "Object deletion failed"

            async with session.delete(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
            ) as delete_bucket_response:
                assert delete_bucket_response.status == 204, "Bucket deletion failed"

    logger.info("Failure scenarios test passed!")

@pytest.mark.asyncio
async def test_performance(dfs_test_setup):
    """Test system performance"""
    logger.info("Testing performance metrics...")
    setup_data = await dfs_test_setup
    test_data = setup_data["test_data"]
    mock_provider = setup_data["mock_provider"]

    async with aiohttp.ClientSession() as session:
        bucket_name = f"test-bucket-{random.randint(1, 1000)}"
        base_object_key = f"test-object-{random.randint(1, 1000)}"

        # Create bucket
        try:
            async with session.put(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
            ) as create_bucket_response:
                assert create_bucket_response.status == 200, "Bucket creation failed"
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {e}")
            pytest.fail("Failed to connect to the server")

        # Test parallel uploads
        upload_tasks = []
        num_objects = 10

        async def upload_object(index):
            object_key = f"{base_object_key}-{index}"
            headers = {
                'Content-Type': 'application/octet-stream',
                'X-Consistency-Level': 'eventual'  # Use eventual consistency for better performance
            }
            async with session.put(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
                data=test_data,
                headers=headers
            ) as response:
                assert response.status == 200, f"Upload failed for object {index}"
                return object_key

        start_time = datetime.now()
        for i in range(num_objects):
            upload_tasks.append(upload_object(i))
        uploaded_objects = await asyncio.gather(*upload_tasks)
        upload_duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"Parallel upload performance: {num_objects/upload_duration:.2f} objects/second")

        # Test parallel downloads
        download_tasks = []

        async def download_object(object_key):
            headers = {'X-Consistency-Level': 'eventual'}
            async with session.get(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
                headers=headers
            ) as response:
                assert response.status == 200, f"Download failed for object {object_key}"
                data = await response.read()
                assert len(data) == len(test_data), "Downloaded data size mismatch"

        start_time = datetime.now()
        for object_key in uploaded_objects:
            download_tasks.append(download_object(object_key))
        await asyncio.gather(*download_tasks)
        download_duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"Parallel download performance: {num_objects/download_duration:.2f} objects/second")

        # Test list objects performance
        start_time = datetime.now()
        async with session.get(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
        ) as list_response:
            assert list_response.status == 200, "List objects failed"
            objects = await list_response.json()
            assert len(objects.get('Contents', [])) >= num_objects, "Not all objects listed"
        list_duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"List objects performance: {list_duration:.3f} seconds")

        # Cleanup
        delete_tasks = []

        async def delete_object(object_key):
            async with session.delete(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}"
            ) as response:
                assert response.status == 204, f"Delete failed for object {object_key}"

        for object_key in uploaded_objects:
            delete_tasks.append(delete_object(object_key))
        await asyncio.gather(*delete_tasks)

        async with session.delete(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
        ) as delete_bucket_response:
            assert delete_bucket_response.status == 204, "Bucket deletion failed"

    logger.info("Performance test passed!")

@pytest.mark.asyncio
async def test_offline_mode(dfs_test_setup):
    """Test edge node offline operation"""
    logger.info("Testing offline mode operation...")
    setup_data = await dfs_test_setup
    test_data = setup_data["test_data"]
    docker_client = setup_data["docker_client"]
    edge_nodes = setup_data["edge_nodes"]
    mock_provider = setup_data["mock_provider"]

    async with aiohttp.ClientSession() as session:
        bucket_name = f"test-bucket-{random.randint(1, 1000)}"
        object_key = f"test-object-{random.randint(1, 1000)}"

        # Create bucket
        try:
            async with session.put(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
            ) as create_bucket_response:
                assert create_bucket_response.status == 200, "Bucket creation failed"
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {e}")
            pytest.fail("Failed to connect to the server")

        # Upload object to edge node
        headers = {
            'Content-Type': 'application/octet-stream',
            'X-Edge-Node': edge_nodes[0],  # Use first edge node
            'X-Cache-Control': 'cache'  # Indicate this should be cached at edge
        }

        async with session.put(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            data=test_data,
            headers=headers
        ) as upload_response:
            assert upload_response.status == 200, "Edge node upload failed"

        # Verify the object is cached at edge
        headers = {
            'X-Edge-Node': edge_nodes[0],
            'X-Cache-Info': 'query'
        }
        async with session.head(
            f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
            headers=headers
        ) as cache_response:
            assert cache_response.status == 200, "Cache verification failed"
            if 'X-Cache-Status' not in cache_response.headers:
                logger.warning("Cache status header missing")
            else:
                assert cache_response.headers['X-Cache-Status'] == 'hit', "Object not cached at edge"

        # Simulate network partition by stopping core nodes
        core_containers = []
        for node in setup_data["core_nodes"]:
            container = docker_client.containers.get(node)
            container.stop()
            core_containers.append(container)

        await asyncio.sleep(5)  # Wait for the system to detect the partition

        try:
            # Try to read from edge node in offline mode
            headers = {
                'X-Edge-Node': edge_nodes[0],
                'X-Offline-Mode': 'true'
            }
            async with session.get(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{object_key}",
                headers=headers
            ) as offline_response:
                assert offline_response.status == 200, "Offline mode read failed"
                response_data = await offline_response.read()
                assert response_data == test_data, "Offline mode data verification failed"

            # Try to write to edge node in offline mode
            new_data = b"Offline update"
            headers['Content-Type'] = 'application/octet-stream'
            async with session.put(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/offline-{object_key}",
                data=new_data,
                headers=headers
            ) as offline_write_response:
                assert offline_write_response.status == 200, "Offline mode write failed"
                assert 'X-Offline-Operation-Id' in offline_write_response.headers, "Offline operation ID missing"

        finally:
            # Restart core nodes
            for container in core_containers:
                container.start()
            await asyncio.sleep(5)  # Wait for core nodes to recover

            # Verify offline operations are synchronized
            async with session.get(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/offline-{object_key}"
            ) as sync_response:
                assert sync_response.status == 200, "Offline operation sync failed"
                sync_data = await sync_response.read()
                assert sync_data == new_data, "Offline operation data verification failed"

            # Cleanup
            for key in [object_key, f"offline-{object_key}"]:
                async with session.delete(
                    f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}/objects/{key}"
                ) as delete_response:
                    assert delete_response.status == 204, f"Object deletion failed for {key}"

            async with session.delete(
                f"http://localhost:8001/api/v1/s3/buckets/{bucket_name}"
            ) as delete_bucket_response:
                assert delete_bucket_response.status == 204, "Bucket deletion failed"

    logger.info("Offline mode test passed!")
