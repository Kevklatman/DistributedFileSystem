"""
Container Storage Interface (CSI) driver implementation
"""
import grpc
from concurrent import futures
import time
from typing import Dict, Optional
import os
import json
from pathlib import Path
import logging

from kubernetes import client, config
from src.csi.proto import csi_pb2, csi_pb2_grpc, IdentityServicer, ControllerServicer, NodeServicer

from src.api.models import Volume, StoragePool
from src.storage.core.hybrid_storage import HybridStorageManager

class CSIDriver(IdentityServicer,
               ControllerServicer,
               NodeServicer):
    """CSI driver implementation for hybrid cloud storage"""

    def __init__(self, storage_manager: HybridStorageManager):
        self.storage_manager = storage_manager
        self.logger = logging.getLogger(__name__)
        self.node_id = os.getenv("NODE_ID", "default-node")
        self.volumes: Dict[str, Volume] = {}

        # Load k8s config
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()

        self.k8s_api = client.CustomObjectsApi()

    def CreateVolume(self, request, context):
        """Create a new volume"""
        try:
            # Extract parameters
            name = request.name
            capacity = request.capacity_range.required_bytes
            parameters = request.parameters

            # Determine storage class and tier
            storage_class = parameters.get("storageClass", "standard")
            tier = parameters.get("tier", "performance")

            # Create volume
            volume = self.storage_manager.create_volume(
                name=name,
                size=capacity,
                storage_class=storage_class,
                tier=tier
            )

            self.volumes[volume.id] = volume

            # Create volume metadata
            topology = {
                "segments": {
                    "kubernetes.io/hostname": self.node_id
                }
            }

            return csi_pb2.CreateVolumeResponse(
                volume={
                    "volume_id": volume.id,
                    "capacity_bytes": capacity,
                    "volume_context": parameters,
                    "accessible_topology": [topology]
                }
            )

        except Exception as e:
            self.logger.error(f"CreateVolume failed: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return csi_pb2.CreateVolumeResponse()

    def DeleteVolume(self, request, context):
        """Delete a volume"""
        try:
            volume_id = request.volume_id
            if volume_id in self.volumes:
                self.storage_manager.delete_volume(volume_id)
                del self.volumes[volume_id]
            return csi_pb2.DeleteVolumeResponse()

        except Exception as e:
            self.logger.error(f"DeleteVolume failed: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return csi_pb2.DeleteVolumeResponse()

    def ControllerPublishVolume(self, request, context):
        """Publish volume to a node"""
        try:
            volume_id = request.volume_id
            node_id = request.node_id

            if volume_id not in self.volumes:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                return csi_pb2.ControllerPublishVolumeResponse()

            # Attach volume to node
            volume = self.volumes[volume_id]
            publish_context = {
                "device_path": str(self.storage_manager.get_volume_path(volume))
            }

            return csi_pb2.ControllerPublishVolumeResponse(
                publish_context=publish_context
            )

        except Exception as e:
            self.logger.error(f"ControllerPublishVolume failed: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return csi_pb2.ControllerPublishVolumeResponse()

    def NodeStageVolume(self, request, context):
        """Stage volume on a node"""
        try:
            volume_id = request.volume_id
            staging_path = request.staging_target_path

            if volume_id not in self.volumes:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                return csi_pb2.NodeStageVolumeResponse()

            # Stage volume
            volume = self.volumes[volume_id]
            os.makedirs(staging_path, exist_ok=True)

            # Mount volume
            device_path = request.publish_context["device_path"]
            self._mount_volume(device_path, staging_path)

            return csi_pb2.NodeStageVolumeResponse()

        except Exception as e:
            self.logger.error(f"NodeStageVolume failed: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return csi_pb2.NodeStageVolumeResponse()

    def NodePublishVolume(self, request, context):
        """Publish volume on a node"""
        try:
            volume_id = request.volume_id
            target_path = request.target_path

            if volume_id not in self.volumes:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                return csi_pb2.NodePublishVolumeResponse()

            # Create mount point
            os.makedirs(target_path, exist_ok=True)

            # Bind mount from staging to target
            staging_path = request.staging_target_path
            self._bind_mount(staging_path, target_path)

            return csi_pb2.NodePublishVolumeResponse()

        except Exception as e:
            self.logger.error(f"NodePublishVolume failed: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return csi_pb2.NodePublishVolumeResponse()

    def GetCapacity(self, request, context):
        """Get storage capacity"""
        try:
            # Get total and available capacity
            total, available = self.storage_manager.get_capacity()

            return csi_pb2.GetCapacityResponse(
                available_capacity=available
            )

        except Exception as e:
            self.logger.error(f"GetCapacity failed: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return csi_pb2.GetCapacityResponse()

    def _mount_volume(self, source: str, target: str) -> None:
        """Mount a volume"""
        os.system(f"mount {source} {target}")

    def _bind_mount(self, source: str, target: str) -> None:
        """Create a bind mount"""
        os.system(f"mount --bind {source} {target}")

def serve(storage_manager: HybridStorageManager,
         endpoint: str = "unix:///csi/csi.sock",
         max_workers: int = 10):
    """Start the CSI driver server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    driver = CSIDriver(storage_manager)
    
    # Register services
    csi_pb2_grpc.add_IdentityServicer_to_server(driver, server)
    csi_pb2_grpc.add_ControllerServicer_to_server(driver, server)
    csi_pb2_grpc.add_NodeServicer_to_server(driver, server)
    
    # Start server
    server.add_insecure_port(endpoint)
    server.start()
    
    return server
