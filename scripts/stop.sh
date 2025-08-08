#!/bin/bash
set -e

# This name MUST match the CONTAINER_NAME in run.sh
CONTAINER_NAME="my-comfy-api"

echo "--- Stopping container: $CONTAINER_NAME ---"
# Using 'docker stop' will also trigger the removal because of the --rm flag in run.sh
docker stop $CONTAINER_NAME
echo "--- Container stopped and removed ---"