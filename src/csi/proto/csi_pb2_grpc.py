"""Mock gRPC service definitions for testing."""

class IdentityServicer:
    """Mock Identity service."""
    def GetPluginInfo(self, request, context):
        pass

    def GetPluginCapabilities(self, request, context):
        pass

    def Probe(self, request, context):
        pass

class ControllerServicer:
    """Mock Controller service."""
    def CreateVolume(self, request, context):
        pass

    def DeleteVolume(self, request, context):
        pass

    def ControllerPublishVolume(self, request, context):
        pass

    def ControllerUnpublishVolume(self, request, context):
        pass

    def ValidateVolumeCapabilities(self, request, context):
        pass

    def ListVolumes(self, request, context):
        pass

    def GetCapacity(self, request, context):
        pass

    def ControllerGetCapabilities(self, request, context):
        pass

class NodeServicer:
    """Mock Node service."""
    def NodeStageVolume(self, request, context):
        pass

    def NodeUnstageVolume(self, request, context):
        pass

    def NodePublishVolume(self, request, context):
        pass

    def NodeUnpublishVolume(self, request, context):
        pass

    def NodeGetVolumeStats(self, request, context):
        pass

    def NodeExpandVolume(self, request, context):
        pass

    def NodeGetCapabilities(self, request, context):
        pass

    def NodeGetInfo(self, request, context):
        pass
