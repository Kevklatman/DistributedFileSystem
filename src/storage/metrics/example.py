import time
import random
import sys
import os

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from collector import SystemMetricsCollector
from visualizer import MetricsVisualizer

def simulate_operations(collector: SystemMetricsCollector, num_ops: int = 100):
    """Simulate some file system operations to generate metrics."""
    operations = ['read', 'write', 'delete', 'list']

    for _ in range(num_ops):
        # Simulate operation latency
        op = random.choice(operations)
        duration = random.uniform(0.01, 0.5)  # Random duration between 10ms and 500ms
        collector.record_operation_latency(op, duration)

        # Simulate cache operations
        hit = random.random() > 0.3  # 70% cache hit rate
        collector.record_cache_operation(op, hit)

        # Small delay between operations
        time.sleep(0.1)

def main():
    # Initialize collector and visualizer
    collector = SystemMetricsCollector(history_window=60)  # Keep 1 minute of history
    visualizer = MetricsVisualizer(collector)

    print("Starting metrics collection simulation...")
    print("This will run for about 10 seconds to generate sample metrics.")

    # Simulate some operations
    simulate_operations(collector)

    # Generate reports
    print("\nGenerating metrics report...")
    visualizer.generate_report("./metrics_report")

    print("\nMetrics report generated! You can find the following files in ./metrics_report:")
    print("- system_metrics_[timestamp].png")
    print("- operation_latencies_[timestamp].png")
    print("- cache_performance_[timestamp].png")
    print("- metrics_summary_[timestamp].txt")

if __name__ == "__main__":
    main()
