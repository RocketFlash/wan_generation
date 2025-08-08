#!/bin/bash
set -e

# The name for your Docker image
IMAGE_NAME="comfy-i2v-service"

echo "--- Building Docker image: $IMAGE_NAME ---"
# We navigate to the parent directory (..) to ensure the Docker build context is correct
docker build -t $IMAGE_NAME "$(dirname "$0")/.."
echo "--- Build complete ---"