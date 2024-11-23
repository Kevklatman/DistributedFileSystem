import random
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
#r
@dataclass
class DataBlock:
    """Represents a block of data in the distributed system"""
    block_id: str
    data_size: int  # Size in bytes
    content_hash: str
    replicas: List[str]  # List of node IDs storing this block

class DataStore:
    """Simulates data storage and management in the distributed system"""
    def __init__(self, base_dir: str = "simulated_data"):
        self.base_dir = base_dir
        self.blocks: Dict[str, DataBlock] = {}
        self.node_data: Dict[str, List[str]] = {}  # Maps node_id to list of block_ids

        # Create base directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)

    def write_block(self, data_size: int, replicas: List[str]) -> DataBlock:
        """
        Simulate writing a new data block

        Args:
            data_size: Size of data in bytes
            replicas: List of node IDs to store replicas

        Returns:
            DataBlock object representing the stored data
        """
        # Generate unique block ID and content hash
        block_id = f"block_{random.randint(0, 1000000):06d}"
        content_hash = f"hash_{random.randint(0, 1000000):06d}"

        # Create block
        block = DataBlock(
            block_id=block_id,
            data_size=data_size,
            content_hash=content_hash,
            replicas=replicas
        )

        # Store block metadata
        self.blocks[block_id] = block

        # Update node data mappings
        for node_id in replicas:
            if node_id not in self.node_data:
                self.node_data[node_id] = []
            self.node_data[node_id].append(block_id)

        # Save block metadata to file
        self._save_block_metadata(block)

        return block

    def read_block(self, block_id: str, node_id: str) -> Optional[DataBlock]:
        """
        Simulate reading a data block

        Args:
            block_id: ID of block to read
            node_id: ID of node attempting to read

        Returns:
            DataBlock if available, None if not found
        """
        block = self.blocks.get(block_id)
        if block and node_id in block.replicas:
            return block
        return None

    def get_node_blocks(self, node_id: str) -> List[DataBlock]:
        """Get all blocks stored on a specific node"""
        block_ids = self.node_data.get(node_id, [])
        return [self.blocks[block_id] for block_id in block_ids if block_id in self.blocks]

    def get_block_locations(self, block_id: str) -> List[str]:
        """Get all nodes storing a specific block"""
        block = self.blocks.get(block_id)
        return block.replicas if block else []

    def remove_node_data(self, node_id: str):
        """Remove all data from a node (e.g., when simulating failure)"""
        if node_id in self.node_data:
            block_ids = self.node_data[node_id]
            for block_id in block_ids:
                if block_id in self.blocks:
                    block = self.blocks[block_id]
                    block.replicas.remove(node_id)
            del self.node_data[node_id]

    def _save_block_metadata(self, block: DataBlock):
        """Save block metadata to a file"""
        metadata_file = os.path.join(self.base_dir, f"{block.block_id}.json")
        metadata = {
            "block_id": block.block_id,
            "data_size": block.data_size,
            "content_hash": block.content_hash,
            "replicas": block.replicas
        }
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    def get_storage_stats(self) -> Dict[str, Dict]:
        """Get storage statistics for all nodes"""
        stats = {}
        for node_id in self.node_data:
            blocks = self.get_node_blocks(node_id)
            total_size = sum(block.data_size for block in blocks)
            stats[node_id] = {
                "block_count": len(blocks),
                "total_size": total_size,
                "blocks": [block.block_id for block in blocks]
            }
        return stats
