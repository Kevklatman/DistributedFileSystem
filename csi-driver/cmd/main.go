package main

import (
	"flag"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/kevinklatman/DistributedFileSystem/csi-driver/pkg/driver"
)

func main() {
	var (
		endpoint = flag.String("endpoint", "unix:///tmp/csi.sock", "CSI endpoint")
		nodeID   = flag.String("nodeid", "", "node id")
	)
	flag.Parse()

	if *nodeID == "" {
		fmt.Println("node id is required")
		os.Exit(1)
	}

	drv, err := driver.NewDFSDriver(*nodeID, *endpoint)
	if err != nil {
		fmt.Printf("Failed to create driver: %s\n", err)
		os.Exit(1)
	}

	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-c
		drv.Stop()
		os.Exit(0)
	}()

	if err := drv.Run(); err != nil {
		fmt.Printf("Failed to run driver: %s\n", err)
		os.Exit(1)
	}
}
