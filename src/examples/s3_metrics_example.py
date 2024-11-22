"""
Example script demonstrating how to use the metrics collection system with AWS S3.
This is a development tool for quick testing and demonstration purposes.
For proper tests, see tests/unit/ and tests/integration/.
"""

import os
import time
from src.storage.core.providers import AWSS3Provider
from src.storage.metrics.visualizer import MetricsVisualizer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def demonstrate_s3_metrics():
    """Demonstrate metrics collection with basic S3 operations."""
    # Initialize S3 provider with credentials from .env
    s3_provider = AWSS3Provider(
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('AWS_SECRET_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-2')
    )

    # Test bucket and object names
    test_bucket = "kevinklatman"
    test_object = "example-object.txt"
    test_data = b"Hello, World! This is a test file for metrics collection."

    print("Starting S3 operations example...")

    # Upload file
    print("\nUploading file...")
    s3_provider.upload_file(test_data, test_object, test_bucket)

    # Download file
    print("Downloading file...")
    downloaded_data = s3_provider.download_file(test_object, test_bucket)

    # List objects
    print("Listing objects...")
    objects = s3_provider.list_objects(test_bucket)

    # Delete object
    print("Deleting object...")
    s3_provider.delete_object(test_object, test_bucket)

    # Generate metrics report
    print("\nGenerating metrics report...")
    visualizer = MetricsVisualizer(s3_provider.metrics)

    # Create reports directory if it doesn't exist
    os.makedirs("metrics_reports", exist_ok=True)

    # Generate report with timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_dir = f"metrics_reports/s3_example_{timestamp}"
    visualizer.generate_report(report_dir)

    print(f"\nMetrics report generated in: {report_dir}")
    print("You can find the following files:")
    print("- system_metrics.png")
    print("- operation_latencies.png")
    print("- cache_performance.png")
    print("- metrics_summary.txt")

if __name__ == "__main__":
    demonstrate_s3_metrics()
