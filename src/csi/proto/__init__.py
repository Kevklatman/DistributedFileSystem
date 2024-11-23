"""CSI protobuf module."""

# Importing generated protobuf files
try:
    from .csi_pb2 import *
    from .csi_pb2_grpc import *
except ImportError:
    # If protobuf files are not generated yet, provide empty stubs
    class IdentityServicer:
        pass
        
    class ControllerServicer:
        pass
        
    class NodeServicer:
        pass
