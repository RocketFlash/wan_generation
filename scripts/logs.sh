#!/bin/bash
set -e

# This name MUST match the CONTAINER_NAME in run.sh
CONTAINER_NAME="my-comfy-api"

echo "--- Tailing logs for container: $CONTAINER_NAME ---"
echo "--- Press Ctrl+C to exit ---"
docker logs -f $CONTAINER_NAME