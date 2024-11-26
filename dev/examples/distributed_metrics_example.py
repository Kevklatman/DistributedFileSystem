import asyncio
import logging

from simulation.simulated_collector import SimulatedMetricsCollector, NodeLocation

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Example: Simulated distributed system metrics
    # Define nodes in different regions/providers
    nodes = {
        "node1": NodeLocation("us-east", "us-east-1a", "aws", 5),
        "node2": NodeLocation("us-west", "us-west-1b", "aws", 5),
        "node3": NodeLocation("eu-west", "eu-west-1a", "aws", 8),
        "node4": NodeLocation("ap-south", "ap-south-1a", "aws", 12),
        "edge1": NodeLocation("us-east", "mobile-east", "edge", 20),
        "gcp1": NodeLocation("us-east", "us-east1-b", "gcp", 6),
        "azure1": NodeLocation("eu-west", "westeurope", "azure", 7),
    }

    sim_metrics = SimulatedMetricsCollector(nodes)

    # Simulate some operations
    async def run_operations():
        # Simulate file transfers between nodes
        operations = [
            ("node1", "node2", "write", 1024 * 1024),  # 1MB write US-East to US-West
            ("node2", "node3", "write", 5 * 1024 * 1024),  # 5MB write US-West to EU
            ("node3", "edge1", "read", 512 * 1024),  # 512KB read EU to Edge
            ("gcp1", "azure1", "write", 2 * 1024 * 1024),  # 2MB write GCP to Azure
        ]

        for source, dest, op, size in operations:
            logger.info(f"Simulating {op} operation from {source} to {dest}")
            duration = await sim_metrics.simulate_operation(source, dest, op, size)
            logger.info(f"Operation took {duration:.2f} seconds")

            # Get metrics for source and dest nodes
            source_metrics = sim_metrics.get_node_metrics(source)
            dest_metrics = sim_metrics.get_node_metrics(dest)

            logger.info(
                f"{source} metrics: CPU {source_metrics.cpu_usage:.1f}%, "
                f"Network Out: {source_metrics.network_out / 1024 / 1024:.2f}MB"
            )
            logger.info(
                f"{dest} metrics: CPU {dest_metrics.cpu_usage:.1f}%, "
                f"Network In: {dest_metrics.network_in / 1024 / 1024:.2f}MB"
            )

            # Get network latency
            latency = sim_metrics.get_network_latency(source, dest)
            logger.info(f"Network latency between {source} and {dest}: {latency:.1f}ms")

            await asyncio.sleep(1)  # Wait between operations

    # Run simulated operations
    await run_operations()

    # Get overall system view
    all_metrics = sim_metrics.get_all_metrics()
    logger.info("\nFinal System State:")
    for node_id, metrics in all_metrics.items():
        logger.info(f"\nNode: {node_id}")
        logger.info(
            f"Location: {metrics.location.region} ({metrics.location.provider})"
        )
        logger.info(f"CPU Usage: {metrics.cpu_usage:.1f}%")
        logger.info(f"Memory Usage: {metrics.memory_usage:.1f}%")
        logger.info(f"Disk Usage: {metrics.disk_usage:.1f}%")
        logger.info(f"Network In: {metrics.network_in / 1024 / 1024:.2f}MB")
        logger.info(f"Network Out: {metrics.network_out / 1024 / 1024:.2f}MB")
        logger.info(f"Operation Count: {metrics.operation_count}")


if __name__ == "__main__":
    asyncio.run(main())
