#!/usr/bin/env python3
"""
Unified node management script for DFS cluster.
Combines functionality for creating, monitoring, and managing storage nodes.
"""

import argparse
import asyncio
import logging
import os
import sys
import time
import yaml
from datetime import datetime
from kubernetes import client, config
from pathlib import Path
from tabulate import tabulate
from typing import Dict, List

# Add src to Python path
src_path = str(Path(__file__).parent.parent)
sys.path.append(src_path)

from storage.infrastructure.cluster_manager import StorageClusterManager
from storage.infrastructure.load_manager import LoadManager
from models.models import NodeState

def setup_logging():
    """Configure logging with consistent format."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def parse_args():
    """Parse command line arguments for all node management functions."""
    parser = argparse.ArgumentParser(description='DFS Node Management Tools')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create node command
    create_parser = subparsers.add_parser('create', help='Create a new storage node')
    create_parser.add_argument('--namespace', default='default',
                           help='Kubernetes namespace to create the node in')
    create_parser.add_argument('--storage-class', default='standard',
                           help='Storage class to use for node volumes')
    create_parser.add_argument('--storage-size', default='100Gi',
                           help='Size of storage volume')
    create_parser.add_argument('--node-selector', default='',
                           help='Node selector labels (key=value,key2=value2)')
    create_parser.add_argument('--zone', default='default',
                           help='Availability zone for the node')

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor node health and metrics')
    monitor_parser.add_argument('--namespace', default='default',
                            help='Kubernetes namespace to monitor')
    monitor_parser.add_argument('--interval', type=int, default=5,
                            help='Monitoring interval in seconds')
    monitor_parser.add_argument('--format', choices=['table', 'json'], default='table',
                            help='Output format')

    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy DFS cluster')
    deploy_parser.add_argument('--namespace', default='default',
                           help='Kubernetes namespace to deploy to')
    deploy_parser.add_argument('--config', type=str, required=True,
                           help='Path to cluster configuration YAML')
    deploy_parser.add_argument('--registry', default='docker.io',
                           help='Container registry to use')
    deploy_parser.add_argument('--tag', default='latest',
                           help='Image tag to deploy')

    return parser.parse_args()

async def get_node_metrics(cluster_manager: StorageClusterManager) -> List[Dict]:
    """Get metrics from all nodes."""
    nodes = cluster_manager._get_current_nodes()
    metrics = []
    
    for node_id, node in nodes.items():
        load_manager = LoadManager()
        
        # Get node metrics
        load = load_manager.get_node_load(node_id)
        capacity = load_manager.get_node_capacity(node_id)
        current_metrics = load_manager.get_current_metrics()
        
        # Calculate time since last heartbeat
        last_heartbeat_age = datetime.now().timestamp() - node.last_heartbeat
        
        metrics.append({
            'node_id': node_id,
            'status': node.status,
            'zone': node.zone,
            'cpu_usage': f"{current_metrics.cpu_usage:.1f}%",
            'memory_usage': f"{current_metrics.memory_usage:.1f}%",
            'disk_io': f"{current_metrics.disk_io / 1024 / 1024:.1f} MB/s",
            'network_io': f"{current_metrics.network_io / 1024 / 1024:.1f} MB/s",
            'request_rate': f"{current_metrics.request_rate:.1f} req/s",
            'capacity': f"{capacity / 1024 / 1024 / 1024:.1f} GB",
            'used': f"{node.used_bytes / 1024 / 1024 / 1024:.1f} GB",
            'last_heartbeat': f"{last_heartbeat_age:.1f}s ago"
        })
    
    return metrics

def print_metrics_table(metrics: List[Dict]):
    """Print metrics in table format."""
    if not metrics:
        print("No nodes found")
        return
        
    headers = metrics[0].keys()
    rows = [m.values() for m in metrics]
    print(tabulate(rows, headers=headers, tablefmt='grid'))

async def monitor_cluster(args):
    """Monitor cluster health and metrics."""
    cluster_manager = StorageClusterManager(namespace=args.namespace)
    
    while True:
        try:
            metrics = await get_node_metrics(cluster_manager)
            
            # Clear screen
            print("\033[2J\033[H", end="")
            
            # Print cluster summary
            status = cluster_manager.get_cluster_status()
            print(f"Cluster Status:")
            print(f"Total Nodes: {status['nodes']}")
            print(f"Healthy Nodes: {status['healthy_nodes']}")
            print(f"Leader Node: {status['leader_node']}")
            print()
            
            # Print node metrics
            if args.format == 'table':
                print_metrics_table(metrics)
            else:
                import json
                print(json.dumps(metrics, indent=2))
                
            await asyncio.sleep(args.interval)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Error monitoring nodes: {e}")
            await asyncio.sleep(args.interval)

def create_node(args):
    """Create a new storage node."""
    # Implementation from create_node.py
    pass

def deploy_cluster(args):
    """Deploy a complete DFS cluster."""
    # Implementation from deploy_cluster.py
    pass

def main():
    """Main entry point for node management tools."""
    setup_logging()
    args = parse_args()
    
    try:
        if args.command == 'monitor':
            asyncio.run(monitor_cluster(args))
        elif args.command == 'create':
            create_node(args)
        elif args.command == 'deploy':
            deploy_cluster(args)
        else:
            logging.error("No command specified. Use --help for usage information.")
            sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Operation stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
