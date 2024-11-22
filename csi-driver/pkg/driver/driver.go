package driver

import (
	"context"
	"fmt"
	"net"
	"net/url"
	"os"
	"path/filepath"
	"sync"

	"github.com/container-storage-interface/spec/lib/go/csi"
	"github.com/google/uuid"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"syscall"
)

const (
	DriverName = "dfs.csi.k8s.io"
	Version    = "1.0.0"
)

type DFSDriver struct {
	name     string
	version  string
	nodeID   string
	endpoint string

	srv     *grpc.Server
	mounter Mounter

	// Track volumes and their mounts
	volumes  map[string]*Volume
	mounts   map[string]*Mount
	volLock  sync.RWMutex
	mountLock sync.RWMutex
}

type Volume struct {
	VolID       string
	VolName     string
	VolSize     int64
	VolPath     string
	NodeID      string
	AccessMode  csi.VolumeCapability_AccessMode_Mode
}

type Mount struct {
	VolID     string
	TargetPath string
	FSType    string
	ReadOnly  bool
}

type Mounter interface {
	Mount(source string, target string, fstype string, opts []string) error
	Unmount(target string) error
}

func NewDFSDriver(nodeID, endpoint string) (*DFSDriver, error) {
	return &DFSDriver{
		name:     DriverName,
		version:  Version,
		nodeID:   nodeID,
		endpoint: endpoint,
		volumes:  make(map[string]*Volume),
		mounts:   make(map[string]*Mount),
	}, nil
}

func (d *DFSDriver) Run() error {
	scheme, addr, err := parseEndpoint(d.endpoint)
	if err != nil {
		return err
	}

	listener, err := net.Listen(scheme, addr)
	if err != nil {
		return err
	}

	logErr := func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		resp, err := handler(ctx, req)
		if err != nil {
			fmt.Printf("GRPC error: %v\n", err)
		}
		return resp, err
	}

	opts := []grpc.ServerOption{
		grpc.UnaryInterceptor(logErr),
	}

	d.srv = grpc.NewServer(opts...)

	csi.RegisterIdentityServer(d.srv, d)
	csi.RegisterControllerServer(d.srv, d)
	csi.RegisterNodeServer(d.srv, d)

	return d.srv.Serve(listener)
}

func (d *DFSDriver) Stop() {
	if d.srv != nil {
		d.srv.Stop()
	}
}

func parseEndpoint(endpoint string) (string, string, error) {
	u, err := url.Parse(endpoint)
	if err != nil {
		return "", "", fmt.Errorf("could not parse endpoint: %v", err)
	}

	var addr string
	if u.Host == "" {
		addr = u.Path
	} else {
		addr = u.Host
	}

	return u.Scheme, addr, nil
}

// Identity Server Implementation
func (d *DFSDriver) GetPluginInfo(ctx context.Context, req *csi.GetPluginInfoRequest) (*csi.GetPluginInfoResponse, error) {
	return &csi.GetPluginInfoResponse{
		Name:          d.name,
		VendorVersion: d.version,
	}, nil
}

func (d *DFSDriver) GetPluginCapabilities(ctx context.Context, req *csi.GetPluginCapabilitiesRequest) (*csi.GetPluginCapabilitiesResponse, error) {
	return &csi.GetPluginCapabilitiesResponse{
		Capabilities: []*csi.PluginCapability{
			{
				Type: &csi.PluginCapability_Service_{
					Service: &csi.PluginCapability_Service{
						Type: csi.PluginCapability_Service_CONTROLLER_SERVICE,
					},
				},
			},
		},
	}, nil
}

func (d *DFSDriver) Probe(ctx context.Context, req *csi.ProbeRequest) (*csi.ProbeResponse, error) {
	return &csi.ProbeResponse{}, nil
}

// Controller Server Implementation
func (d *DFSDriver) CreateVolume(ctx context.Context, req *csi.CreateVolumeRequest) (*csi.CreateVolumeResponse, error) {
	// Validate request
	if req.Name == "" {
		return nil, status.Error(codes.InvalidArgument, "Volume name is required")
	}
	if req.VolumeCapabilities == nil || len(req.VolumeCapabilities) == 0 {
		return nil, status.Error(codes.InvalidArgument, "Volume capabilities are required")
	}

	d.volLock.Lock()
	defer d.volLock.Unlock()

	// Check if volume already exists
	for _, vol := range d.volumes {
		if vol.VolName == req.Name {
			// Volume already exists, check if compatible
			return &csi.CreateVolumeResponse{
				Volume: &csi.Volume{
					VolumeId:      vol.VolID,
					CapacityBytes: vol.VolSize,
					VolumeContext: req.Parameters,
				},
			}, nil
		}
	}

	// Create new volume
	volID := uuid.New().String()
	volPath := filepath.Join("/var/lib/dfs/volumes", volID)

	// Create volume directory
	if err := os.MkdirAll(volPath, 0750); err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to create volume directory: %s", err)
	}

	// Calculate volume size
	var volSize int64 = 1 * 1024 * 1024 * 1024 // Default 1GB
	if req.CapacityRange != nil && req.CapacityRange.RequiredBytes > 0 {
		volSize = req.CapacityRange.RequiredBytes
	}

	// Store volume metadata
	vol := &Volume{
		VolID:      volID,
		VolName:    req.Name,
		VolSize:    volSize,
		VolPath:    volPath,
		AccessMode: req.VolumeCapabilities[0].GetMount().GetMountFlags()[0],
	}
	d.volumes[volID] = vol

	return &csi.CreateVolumeResponse{
		Volume: &csi.Volume{
			VolumeId:      volID,
			CapacityBytes: volSize,
			VolumeContext: req.Parameters,
		},
	}, nil
}

func (d *DFSDriver) DeleteVolume(ctx context.Context, req *csi.DeleteVolumeRequest) (*csi.DeleteVolumeResponse, error) {
	if req.VolumeId == "" {
		return nil, status.Error(codes.InvalidArgument, "Volume ID is required")
	}

	d.volLock.Lock()
	defer d.volLock.Unlock()

	vol, exists := d.volumes[req.VolumeId]
	if !exists {
		// Volume already deleted or doesn't exist
		return &csi.DeleteVolumeResponse{}, nil
	}

	// Check if volume is mounted
	d.mountLock.RLock()
	for _, mount := range d.mounts {
		if mount.VolID == req.VolumeId {
			d.mountLock.RUnlock()
			return nil, status.Error(codes.FailedPrecondition, "Volume is still mounted")
		}
	}
	d.mountLock.RUnlock()

	// Delete volume directory
	if err := os.RemoveAll(vol.VolPath); err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to delete volume directory: %s", err)
	}

	// Remove volume from map
	delete(d.volumes, req.VolumeId)

	return &csi.DeleteVolumeResponse{}, nil
}

func (d *DFSDriver) ControllerPublishVolume(ctx context.Context, req *csi.ControllerPublishVolumeRequest) (*csi.ControllerPublishVolumeResponse, error) {
	return &csi.ControllerPublishVolumeResponse{}, nil
}

func (d *DFSDriver) ControllerUnpublishVolume(ctx context.Context, req *csi.ControllerUnpublishVolumeRequest) (*csi.ControllerUnpublishVolumeResponse, error) {
	return &csi.ControllerUnpublishVolumeResponse{}, nil
}

func (d *DFSDriver) ValidateVolumeCapabilities(ctx context.Context, req *csi.ValidateVolumeCapabilitiesRequest) (*csi.ValidateVolumeCapabilitiesResponse, error) {
	if req.VolumeId == "" {
		return nil, status.Error(codes.InvalidArgument, "Volume ID is required")
	}

	d.volLock.RLock()
	_, exists := d.volumes[req.VolumeId]
	d.volLock.RUnlock()

	if !exists {
		return nil, status.Error(codes.NotFound, "Volume not found")
	}

	// Check each capability
	for _, cap := range req.VolumeCapabilities {
		switch cap.GetAccessType().(type) {
		case *csi.VolumeCapability_Mount:
			// We support mount volumes
		default:
			return &csi.ValidateVolumeCapabilitiesResponse{
				Message: "Unsupported access type",
			}, nil
		}

		// Check access mode
		switch cap.GetAccessMode().GetMode() {
		case csi.VolumeCapability_AccessMode_SINGLE_NODE_WRITER,
			csi.VolumeCapability_AccessMode_SINGLE_NODE_READER_ONLY,
			csi.VolumeCapability_AccessMode_MULTI_NODE_READER_ONLY:
			// These modes are supported
		default:
			return &csi.ValidateVolumeCapabilitiesResponse{
				Message: "Unsupported access mode",
			}, nil
		}
	}

	return &csi.ValidateVolumeCapabilitiesResponse{
		Confirmed: &csi.ValidateVolumeCapabilitiesResponse_Confirmed{
			VolumeCapabilities: req.VolumeCapabilities,
		},
	}, nil
}

func (d *DFSDriver) ListVolumes(ctx context.Context, req *csi.ListVolumesRequest) (*csi.ListVolumesResponse, error) {
	return &csi.ListVolumesResponse{}, nil
}

func (d *DFSDriver) GetCapacity(ctx context.Context, req *csi.GetCapacityRequest) (*csi.GetCapacityResponse, error) {
	return &csi.GetCapacityResponse{}, nil
}

func (d *DFSDriver) ControllerGetCapabilities(ctx context.Context, req *csi.ControllerGetCapabilitiesRequest) (*csi.ControllerGetCapabilitiesResponse, error) {
	return &csi.ControllerGetCapabilitiesResponse{
		Capabilities: []*csi.ControllerServiceCapability{
			{
				Type: &csi.ControllerServiceCapability_Rpc{
					Rpc: &csi.ControllerServiceCapability_RPC{
						Type: csi.ControllerServiceCapability_RPC_CREATE_DELETE_VOLUME,
					},
				},
			},
			{
				Type: &csi.ControllerServiceCapability_Rpc{
					Rpc: &csi.ControllerServiceCapability_RPC{
						Type: csi.ControllerServiceCapability_RPC_PUBLISH_UNPUBLISH_VOLUME,
					},
				},
			},
			{
				Type: &csi.ControllerServiceCapability_Rpc{
					Rpc: &csi.ControllerServiceCapability_RPC{
						Type: csi.ControllerServiceCapability_RPC_LIST_VOLUMES,
					},
				},
			},
			{
				Type: &csi.ControllerServiceCapability_Rpc{
					Rpc: &csi.ControllerServiceCapability_RPC{
						Type: csi.ControllerServiceCapability_RPC_GET_CAPACITY,
					},
				},
			},
			{
				Type: &csi.ControllerServiceCapability_Rpc{
					Rpc: &csi.ControllerServiceCapability_RPC{
						Type: csi.ControllerServiceCapability_RPC_EXPAND_VOLUME,
					},
				},
			},
		},
	}, nil
}

func (d *DFSDriver) ControllerExpandVolume(ctx context.Context, req *csi.ControllerExpandVolumeRequest) (*csi.ControllerExpandVolumeResponse, error) {
	if req.VolumeId == "" {
		return nil, status.Error(codes.InvalidArgument, "Volume ID is required")
	}

	if req.CapacityRange == nil {
		return nil, status.Error(codes.InvalidArgument, "Capacity range is required")
	}

	d.volLock.Lock()
	vol, exists := d.volumes[req.VolumeId]
	if !exists {
		d.volLock.Unlock()
		return nil, status.Error(codes.NotFound, "Volume not found")
	}

	// Update volume size
	vol.VolSize = req.CapacityRange.RequiredBytes
	d.volumes[req.VolumeId] = vol
	d.volLock.Unlock()

	return &csi.ControllerExpandVolumeResponse{
		CapacityBytes:         req.CapacityRange.RequiredBytes,
		NodeExpansionRequired: true,
	}, nil
}

func (d *DFSDriver) ControllerGetVolume(ctx context.Context, req *csi.ControllerGetVolumeRequest) (*csi.ControllerGetVolumeResponse, error) {
	d.volLock.RLock()
	vol, exists := d.volumes[req.VolumeId]
	d.volLock.RUnlock()

	if !exists {
		return nil, status.Error(codes.NotFound, "Volume not found")
	}

	return &csi.ControllerGetVolumeResponse{
		Volume: &csi.Volume{
			VolumeId:      vol.VolID,
			CapacityBytes: vol.VolSize,
		},
		Status: &csi.ControllerGetVolumeResponse_VolumeStatus{
			PublishedNodeIds: []string{vol.NodeID},
		},
	}, nil
}

func (d *DFSDriver) CreateSnapshot(ctx context.Context, req *csi.CreateSnapshotRequest) (*csi.CreateSnapshotResponse, error) {
	return nil, status.Error(codes.Unimplemented, "CreateSnapshot is not supported")
}

func (d *DFSDriver) DeleteSnapshot(ctx context.Context, req *csi.DeleteSnapshotRequest) (*csi.DeleteSnapshotResponse, error) {
	return nil, status.Error(codes.Unimplemented, "DeleteSnapshot is not supported")
}

func (d *DFSDriver) ListSnapshots(ctx context.Context, req *csi.ListSnapshotsRequest) (*csi.ListSnapshotsResponse, error) {
	return nil, status.Error(codes.Unimplemented, "ListSnapshots is not supported")
}

// Node Server Implementation
func (d *DFSDriver) NodeStageVolume(ctx context.Context, req *csi.NodeStageVolumeRequest) (*csi.NodeStageVolumeResponse, error) {
	return &csi.NodeStageVolumeResponse{}, nil
}

func (d *DFSDriver) NodeUnstageVolume(ctx context.Context, req *csi.NodeUnstageVolumeRequest) (*csi.NodeUnstageVolumeResponse, error) {
	return &csi.NodeUnstageVolumeResponse{}, nil
}

func (d *DFSDriver) NodePublishVolume(ctx context.Context, req *csi.NodePublishVolumeRequest) (*csi.NodePublishVolumeResponse, error) {
	// Validate request
	if req.VolumeId == "" || req.TargetPath == "" {
		return nil, status.Error(codes.InvalidArgument, "Volume ID and target path are required")
	}

	d.volLock.RLock()
	vol, exists := d.volumes[req.VolumeId]
	d.volLock.RUnlock()
	if !exists {
		return nil, status.Error(codes.NotFound, "Volume not found")
	}

	d.mountLock.Lock()
	defer d.mountLock.Unlock()

	// Check if already mounted
	for _, mount := range d.mounts {
		if mount.VolID == req.VolumeId && mount.TargetPath == req.TargetPath {
			return &csi.NodePublishVolumeResponse{}, nil
		}
	}

	// Create target directory if it doesn't exist
	if err := os.MkdirAll(req.TargetPath, 0750); err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to create target directory: %s", err)
	}

	// Mount the volume
	mountFlags := []string{}
	if req.Readonly {
		mountFlags = append(mountFlags, "ro")
	}

	if err := d.mounter.Mount(vol.VolPath, req.TargetPath, "bind", mountFlags); err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to mount volume: %s", err)
	}

	// Record mount
	d.mounts[req.TargetPath] = &Mount{
		VolID:      req.VolumeId,
		TargetPath: req.TargetPath,
		ReadOnly:   req.Readonly,
	}

	return &csi.NodePublishVolumeResponse{}, nil
}

func (d *DFSDriver) NodeUnpublishVolume(ctx context.Context, req *csi.NodeUnpublishVolumeRequest) (*csi.NodeUnpublishVolumeResponse, error) {
	d.mountLock.Lock()
	defer d.mountLock.Unlock()

	// Check if volume is mounted
	for _, mount := range d.mounts {
		if mount.TargetPath == req.TargetPath {
			// Unmount the volume
			if err := d.mounter.Unmount(req.TargetPath); err != nil {
				return nil, status.Errorf(codes.Internal, "Failed to unmount volume: %s", err)
			}

			// Remove mount record
			delete(d.mounts, req.TargetPath)
			return &csi.NodeUnpublishVolumeResponse{}, nil
		}
	}

	return nil, status.Errorf(codes.NotFound, "Volume not found")
}

func (d *DFSDriver) NodeGetVolumeStats(ctx context.Context, req *csi.NodeGetVolumeStatsRequest) (*csi.NodeGetVolumeStatsResponse, error) {
	if req.VolumeId == "" || req.VolumePath == "" {
		return nil, status.Error(codes.InvalidArgument, "Volume ID and volume path are required")
	}

	var stat syscall.Statfs_t
	if err := syscall.Statfs(req.VolumePath, &stat); err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to get volume stats: %v", err)
	}

	available := stat.Bavail * uint64(stat.Bsize)
	total := stat.Blocks * uint64(stat.Bsize)
	used := (stat.Blocks - stat.Bfree) * uint64(stat.Bsize)

	return &csi.NodeGetVolumeStatsResponse{
		Usage: []*csi.VolumeUsage{
			{
				Available: int64(available),
				Total:     int64(total),
				Used:      int64(used),
				Unit:      csi.VolumeUsage_BYTES,
			},
			{
				Available: int64(stat.Ffree),
				Total:     int64(stat.Files),
				Used:      int64(stat.Files - stat.Ffree),
				Unit:      csi.VolumeUsage_INODES,
			},
		},
	}, nil
}

func (d *DFSDriver) NodeExpandVolume(ctx context.Context, req *csi.NodeExpandVolumeRequest) (*csi.NodeExpandVolumeResponse, error) {
	if req.VolumeId == "" || req.VolumePath == "" {
		return nil, status.Error(codes.InvalidArgument, "Volume ID and volume path are required")
	}

	d.volLock.Lock()
	vol, exists := d.volumes[req.VolumeId]
	if !exists {
		d.volLock.Unlock()
		return nil, status.Error(codes.NotFound, "Volume not found")
	}

	// Update volume size
	vol.VolSize = req.CapacityRange.RequiredBytes
	d.volumes[req.VolumeId] = vol
	d.volLock.Unlock()

	return &csi.NodeExpandVolumeResponse{
		CapacityBytes: req.CapacityRange.RequiredBytes,
	}, nil
}

func (d *DFSDriver) NodeGetCapabilities(ctx context.Context, req *csi.NodeGetCapabilitiesRequest) (*csi.NodeGetCapabilitiesResponse, error) {
	return &csi.NodeGetCapabilitiesResponse{
		Capabilities: []*csi.NodeServiceCapability{
			{
				Type: &csi.NodeServiceCapability_Rpc{
					Rpc: &csi.NodeServiceCapability_RPC{
						Type: csi.NodeServiceCapability_RPC_STAGE_UNSTAGE_VOLUME,
					},
				},
			},
			{
				Type: &csi.NodeServiceCapability_Rpc{
					Rpc: &csi.NodeServiceCapability_RPC{
						Type: csi.NodeServiceCapability_RPC_GET_VOLUME_STATS,
					},
				},
			},
			{
				Type: &csi.NodeServiceCapability_Rpc{
					Rpc: &csi.NodeServiceCapability_RPC{
						Type: csi.NodeServiceCapability_RPC_EXPAND_VOLUME,
					},
				},
			},
		},
	}, nil
}

func (d *DFSDriver) NodeGetInfo(ctx context.Context, req *csi.NodeGetInfoRequest) (*csi.NodeGetInfoResponse, error) {
	return &csi.NodeGetInfoResponse{
		NodeId: d.nodeID,
		MaxVolumesPerNode: 256, // Reasonable default
		AccessibleTopology: &csi.Topology{
			Segments: map[string]string{
				"kubernetes.io/hostname": d.nodeID,
			},
		},
	}, nil
}
