#!/bin/bash
set -e

# This name MUST match the CONTAINER_NAME in run.sh
CONTAINER_NAME="my-comfy-api"

echo "--- Entering interactive shell for container: $CONTAINER_NAME ---"
echo "--- Type 'exit' to leave the container ---"
docker exec -it $CONTAINER_NAME /bin/bash