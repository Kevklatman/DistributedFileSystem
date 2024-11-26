from ast import Import
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Any, List
import time
from .collector import SystemMetricsCollector
import logging

logger = logging.getLogger(__name__)


class MetricsVisualizer:
    """Visualizes system metrics collected by SystemMetricsCollector."""

    def __init__(self, collector: SystemMetricsCollector):
        """Initialize visualizer with a metrics collector.

        Args:
            collector: Instance of SystemMetricsCollector to visualize metrics from
        """
        self.collector = collector

    def plot_system_metrics(self, save_path: str = None) -> None:
        """Plot current system metrics.

        Args:
            save_path: Optional path to save the plot to. If None, displays plot.
        """
        metrics = self.collector.get_metrics()

        # Create subplots for different metrics
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle("System Metrics Overview")

        # System metrics
        system = metrics["system"]
        ax1.bar(["CPU Usage"], [system["cpu_usage"]], color="blue")
        ax1.set_ylabel("Percentage")
        ax1.set_title("CPU Usage")

        ax2.bar(["Memory Usage"], [system["memory_usage"]], color="green")
        ax2.set_ylabel("Percentage")
        ax2.set_title("Memory Usage")

        ax3.bar(
            ["Disk I/O Rate"], [system["disk_io_rate"] / 1024 / 1024], color="orange"
        )
        ax3.set_ylabel("MB/s")
        ax3.set_title("Disk I/O Rate")

        ax4.bar(
            ["Network I/O Rate"], [system["network_io_rate"] / 1024 / 1024], color="red"
        )
        ax4.set_ylabel("MB/s")
        ax4.set_title("Network I/O Rate")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()

    def plot_operation_latencies(self, save_path: str = None) -> None:
        """Plot operation latencies.

        Args:
            save_path: Optional path to save the plot to. If None, displays plot.
        """
        metrics = self.collector.get_metrics()
        operations = metrics["operations"]

        if not operations:
            logger.warning("No operation metrics available to plot")
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        fig.suptitle("Operation Latencies")

        # Average latencies
        names = list(operations.keys())
        avg_latencies = [
            op_stats["avg_latency"] * 1000 for op_stats in operations.values()
        ]  # Convert to ms

        ax1.bar(names, avg_latencies)
        ax1.set_ylabel("Average Latency (ms)")
        ax1.set_title("Average Operation Latencies")
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Min/Max latencies
        min_latencies = [
            op_stats["min_latency"] * 1000 for op_stats in operations.values()
        ]
        max_latencies = [
            op_stats["max_latency"] * 1000 for op_stats in operations.values()
        ]

        x = np.arange(len(names))
        width = 0.35

        ax2.bar(x - width / 2, min_latencies, width, label="Min")
        ax2.bar(x + width / 2, max_latencies, width, label="Max")
        ax2.set_xticks(x)
        ax2.set_xticklabels(names)
        ax2.set_ylabel("Latency (ms)")
        ax2.set_title("Min/Max Operation Latencies")
        ax2.legend()
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()

    def plot_cache_performance(self, save_path: str = None) -> None:
        """Plot cache performance metrics.

        Args:
            save_path: Optional path to save the plot to. If None, displays plot.
        """
        metrics = self.collector.get_metrics()
        cache = metrics["cache"]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle("Cache Performance")

        # Hit rate
        ax1.pie(
            [cache["hit_rate"], 1 - cache["hit_rate"]],
            labels=["Hits", "Misses"],
            autopct="%1.1f%%",
            colors=["green", "red"],
        )
        ax1.set_title("Cache Hit Rate")

        # Hit/Miss counts
        ax2.bar(
            ["Hits", "Misses"], [cache["hits"], cache["misses"]], color=["green", "red"]
        )
        ax2.set_title("Cache Operations")
        ax2.set_ylabel("Count")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()

    def generate_report(self, report_dir: str) -> None:
        """Generate a comprehensive metrics report with all plots.

        Args:
            report_dir: Directory to save the report plots
        """
        import os
        from datetime import datetime

        # Create report directory if it doesn't exist
        os.makedirs(report_dir, exist_ok=True)

        # Generate timestamp for report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate and save all plots
        self.plot_system_metrics(
            save_path=os.path.join(report_dir, f"system_metrics_{timestamp}.png")
        )
        self.plot_operation_latencies(
            save_path=os.path.join(report_dir, f"operation_latencies_{timestamp}.png")
        )
        self.plot_cache_performance(
            save_path=os.path.join(report_dir, f"cache_performance_{timestamp}.png")
        )

        # Generate summary text report
        metrics = self.collector.get_metrics()
        with open(
            os.path.join(report_dir, f"metrics_summary_{timestamp}.txt"), "w"
        ) as f:
            f.write("=== System Metrics Summary ===\n\n")

            f.write("System Resources:\n")
            for metric, value in metrics["system"].items():
                f.write(f"  {metric}: {value:.2f}\n")

            f.write("\nOperation Latencies:\n")
            for op, stats in metrics["operations"].items():
                f.write(f"  {op}:\n")
                for stat, value in stats.items():
                    f.write(f"    {stat}: {value:.3f}\n")

            f.write("\nCache Performance:\n")
            for metric, value in metrics["cache"].items():
                f.write(f"  {metric}: {value}\n")
