#!/bin/bash

# Default values
ENDPOINT=${ENDPOINT:-"unix:///csi/csi.sock"}
MODE=${MODE:-"node"}

# Start the CSI driver with the specified mode
exec python /app/csi/driver.py --endpoint="$ENDPOINT" --mode="$MODE"
