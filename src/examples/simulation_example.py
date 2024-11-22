import asyncio
import logging
import json
from datetime import datetime

from src.simulation.scenario_config import ScenarioGenerator
from src.simulation.scenario_simulator import ScenarioSimulator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def save_results(scenario_name: str, results: dict):
    """Save simulation results to a file"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"simulation_results_{scenario_name}_{timestamp}.json"

    # Convert results to JSON-serializable format
    serializable_results = {
        'duration': results['duration'],
        'operations': [vars(r) for r in results['results']],
        'metrics_history': results['metrics_history']
    }

    with open(filename, 'w') as f:
        json.dump(serializable_results, f, indent=2)

    logger.info(f"Results saved to {filename}")

def analyze_results(results: dict):
    """Analyze and print simulation results"""
    total_ops = len(results['results'])
    successful_ops = sum(1 for r in results['results'] if r.success)
    failed_ops = total_ops - successful_ops

    total_data = sum(r.data_size for r in results['results'] if r.success)
    total_duration = results['duration']

    logger.info("\nSimulation Results:")
    logger.info(f"Total Operations: {total_ops}")
    logger.info(f"Successful Operations: {successful_ops}")
    logger.info(f"Failed Operations: {failed_ops}")
    logger.info(f"Success Rate: {(successful_ops/total_ops)*100:.2f}%")
    logger.info(f"Total Data Transferred: {total_data/1024/1024:.2f} MB")
    logger.info(f"Average Throughput: {(total_data/1024/1024)/total_duration:.2f} MB/s")

    # Analyze failures
    failure_types = {}
    for result in results['results']:
        if not result.success and result.error:
            failure_types[result.error] = failure_types.get(result.error, 0) + 1

    if failure_types:
        logger.info("\nFailure Analysis:")
        for error, count in failure_types.items():
            logger.info(f"{error}: {count} occurrences")

    # Analyze node metrics
    logger.info("\nNode Performance:")
    for node_id, metrics in results['metrics_history'].items():
        if metrics:  # Check if we have metrics for this node
            avg_cpu = sum(m['cpu_usage'] for m in metrics) / len(metrics)
            avg_memory = sum(m['memory_usage'] for m in metrics) / len(metrics)
            total_network = metrics[-1]['network_in'] + metrics[-1]['network_out']

            logger.info(f"\nNode: {node_id}")
            logger.info(f"Average CPU Usage: {avg_cpu:.1f}%")
            logger.info(f"Average Memory Usage: {avg_memory:.1f}%")
            logger.info(f"Total Network I/O: {total_network/1024/1024:.2f} MB")
            logger.info(f"Total Operations: {metrics[-1]['operations_count']}")
            logger.info(f"Total Errors: {metrics[-1]['errors_count']}")

async def run_scenario(scenario_name: str, duration: int = None):
    """Run a specific scenario"""
    # Get scenario configuration
    if scenario_name == "high_availability":
        config = ScenarioGenerator.generate_high_availability_scenario()
    elif scenario_name == "edge_computing":
        config = ScenarioGenerator.generate_edge_computing_scenario()
    elif scenario_name == "hybrid_cloud":
        config = ScenarioGenerator.generate_hybrid_cloud_scenario()
    else:
        raise ValueError(f"Unknown scenario: {scenario_name}")

    # Override duration if specified
    if duration:
        config.duration = duration

    logger.info(f"\nStarting {scenario_name} simulation:")
    logger.info(f"Duration: {config.duration} seconds")
    logger.info(f"Regions: {', '.join(config.regions.keys())}")
    logger.info(f"Workload Pattern: {config.workload_pattern}")
    logger.info(f"Consistency Level: {config.consistency_level}")
    logger.info(f"Edge Enabled: {config.edge_enabled}")
    logger.info(f"Failure Injection: {config.failure_injection}")

    # Run simulation
    simulator = ScenarioSimulator(config)
    results = await simulator.run()

    # Analyze and save results
    analyze_results(results)
    save_results(scenario_name, results)

async def main():
    """Run all scenarios"""
    scenarios = [
        ("high_availability", 300),  # 5 minutes
        ("edge_computing", 300),     # 5 minutes
        ("hybrid_cloud", 300)        # 5 minutes
    ]

    for scenario_name, duration in scenarios:
        await run_scenario(scenario_name, duration)
        logger.info("\n" + "="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
