"""Mock protobuf classes for testing."""


class CreateVolumeRequest:
    def __init__(self, name=None, capacity_range=None, parameters=None):
        self.name = name
        self.capacity_range = capacity_range
        self.parameters = parameters or {}


class DeleteVolumeRequest:
    def __init__(self, volume_id=None):
        self.volume_id = volume_id


class CapacityRange:
    def __init__(self, required_bytes=None, limit_bytes=None):
        self.required_bytes = required_bytes
        self.limit_bytes = limit_bytes


class VolumeCapability:
    def __init__(self, access_mode=None, mount=None):
        self.access_mode = access_mode
        self.mount = mount


class CreateVolumeResponse:
    def __init__(self, volume=None):
        self.volume = volume


class DeleteVolumeResponse:
    pass


class Volume:
    def __init__(self, volume_id=None, capacity_bytes=None):
        self.volume_id = volume_id
        self.capacity_bytes = capacity_bytes
