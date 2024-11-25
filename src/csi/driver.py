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
import argparse

from kubernetes import client, config
from csi.proto import csi_pb2, csi_pb2_grpc

from models.models import Volume, StoragePool
from storage.infrastructure.hybrid_storage import HybridStorageManager

class CSIDriver(csi_pb2_grpc.IdentityServicer,
               csi_pb2_grpc.ControllerServicer,
               csi_pb2_grpc.NodeServicer):
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

    def GetPluginInfo(self, request, context):
        """Return plugin info"""
        return csi_pb2.GetPluginInfoResponse(
            name="dfs.csi.k8s.io",
            vendor_version="v1.0.0"
        )

    def GetPluginCapabilities(self, request, context):
        """Return plugin capabilities"""
        cap = csi_pb2.PluginCapability(
            service=csi_pb2.PluginCapability.Service(
                type=csi_pb2.PluginCapability.Service.CONTROLLER_SERVICE
            )
        )
        return csi_pb2.GetPluginCapabilitiesResponse(capabilities=[cap])

    def Probe(self, request, context):
        """Health check"""
        return csi_pb2.ProbeResponse(ready=True)

    def CreateVolume(self, request, context):
        """Create a new volume"""
        try:
            # Extract parameters
            name = request.name
            capacity = request.capacity_range.required_bytes
            parameters = request.parameters

            # Create volume
            volume = self.storage_manager.create_volume(
                name=name,
                size=capacity,
                parameters=parameters
            )

            return csi_pb2.CreateVolumeResponse(
                volume=csi_pb2.Volume(
                    volume_id=volume.id,
                    capacity_bytes=volume.size,
                    volume_context=volume.parameters
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to create volume: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to create volume: {str(e)}")
            return csi_pb2.CreateVolumeResponse()

    def DeleteVolume(self, request, context):
        """Delete a volume"""
        try:
            volume_id = request.volume_id
            self.storage_manager.delete_volume(volume_id)
            return csi_pb2.DeleteVolumeResponse()
        except Exception as e:
            self.logger.error(f"Failed to delete volume: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to delete volume: {str(e)}")
            return csi_pb2.DeleteVolumeResponse()

    def NodeStageVolume(self, request, context):
        """Stage a volume on a node"""
        try:
            volume_id = request.volume_id
            staging_path = request.staging_target_path
            volume_context = request.volume_context

            # Stage the volume
            self.storage_manager.stage_volume(
                volume_id=volume_id,
                staging_path=staging_path,
                volume_context=volume_context
            )

            return csi_pb2.NodeStageVolumeResponse()
        except Exception as e:
            self.logger.error(f"Failed to stage volume: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to stage volume: {str(e)}")
            return csi_pb2.NodeStageVolumeResponse()

    def NodePublishVolume(self, request, context):
        """Publish a volume on a node"""
        try:
            volume_id = request.volume_id
            target_path = request.target_path
            staging_path = request.staging_target_path
            volume_context = request.volume_context

            # Mount the volume
            self.storage_manager.publish_volume(
                volume_id=volume_id,
                staging_path=staging_path,
                target_path=target_path,
                volume_context=volume_context
            )

            return csi_pb2.NodePublishVolumeResponse()
        except Exception as e:
            self.logger.error(f"Failed to publish volume: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to publish volume: {str(e)}")
            return csi_pb2.NodePublishVolumeResponse()

    def NodeGetCapabilities(self, request, context):
        """Return node capabilities"""
        cap = csi_pb2.NodeServiceCapability(
            rpc=csi_pb2.NodeServiceCapability.RPC(
                type=csi_pb2.NodeServiceCapability.RPC.STAGE_UNSTAGE_VOLUME
            )
        )
        return csi_pb2.NodeGetCapabilitiesResponse(capabilities=[cap])

def serve(mode: str = "node", endpoint: str = "unix:///csi/csi.sock"):
    """Start the CSI driver server"""
    # Create storage manager
    storage_manager = HybridStorageManager()

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    driver = CSIDriver(storage_manager)

    # Add servicers to server
    csi_pb2_grpc.add_IdentityServicer_to_server(driver, server)
    if mode == "controller":
        csi_pb2_grpc.add_ControllerServicer_to_server(driver, server)
    else:
        csi_pb2_grpc.add_NodeServicer_to_server(driver, server)

    # Start server
    server.add_insecure_port(endpoint)
    server.start()

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CSI Driver")
    parser.add_argument("--mode", choices=["controller", "node"], default="node",
                      help="Driver mode (controller or node)")
    parser.add_argument("--endpoint", default="unix:///csi/csi.sock",
                      help="CSI endpoint")
    args = parser.parse_args()

    serve(mode=args.mode, endpoint=args.endpoint)
