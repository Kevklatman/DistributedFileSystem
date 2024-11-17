package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
)

type StorageNode struct {
	nodeID    string
	dataDir   string
	server    *http.Server
}

func NewStorageNode(nodeID, dataDir string) (*StorageNode, error) {
	if err := os.MkdirAll(dataDir, 0750); err != nil {
		return nil, fmt.Errorf("failed to create data directory: %v", err)
	}

	return &StorageNode{
		nodeID:  nodeID,
		dataDir: dataDir,
	}, nil
}

func (n *StorageNode) Start(port int) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/ready", n.handleReady)
	mux.HandleFunc("/health", n.handleHealth)
	mux.HandleFunc("/volumes", n.handleVolumes)

	n.server = &http.Server{
		Addr:    fmt.Sprintf(":%d", port),
		Handler: mux,
	}

	return n.server.ListenAndServe()
}

func (n *StorageNode) Stop() error {
	if n.server != nil {
		return n.server.Shutdown(context.Background())
	}
	return nil
}

func (n *StorageNode) handleReady(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
}

func (n *StorageNode) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
}

func (n *StorageNode) handleVolumes(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodPost:
		// Handle volume creation
		volID := r.URL.Query().Get("id")
		if volID == "" {
			http.Error(w, "volume ID is required", http.StatusBadRequest)
			return
		}

		volPath := filepath.Join(n.dataDir, volID)
		if err := os.MkdirAll(volPath, 0750); err != nil {
			http.Error(w, fmt.Sprintf("failed to create volume directory: %v", err), http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusCreated)

	case http.MethodDelete:
		// Handle volume deletion
		volID := r.URL.Query().Get("id")
		if volID == "" {
			http.Error(w, "volume ID is required", http.StatusBadRequest)
			return
		}

		volPath := filepath.Join(n.dataDir, volID)
		if err := os.RemoveAll(volPath); err != nil {
			http.Error(w, fmt.Sprintf("failed to delete volume: %v", err), http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)

	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func main() {
	var (
		port    = flag.Int("port", 8080, "Port to listen on")
		nodeID  = flag.String("nodeid", "", "Node ID")
		dataDir = flag.String("datadir", "/data", "Data directory")
	)
	flag.Parse()

	if *nodeID == "" {
		log.Fatal("node ID is required")
	}

	node, err := NewStorageNode(*nodeID, *dataDir)
	if err != nil {
		log.Fatalf("Failed to create storage node: %v", err)
	}

	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-c
		if err := node.Stop(); err != nil {
			log.Printf("Error stopping node: %v", err)
		}
		os.Exit(0)
	}()

	log.Printf("Starting storage node %s on port %d", *nodeID, *port)
	if err := node.Start(*port); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Failed to start storage node: %v", err)
	}
}
