#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Preparing model directories ---"
rm -rf /app/ComfyUI/models
ln -s /models /app/ComfyUI/models
echo "--- Symbolic link created: /app/ComfyUI/models -> /models ---"

# 2. Start the ComfyUI server in the background
# --listen makes it accessible on all network interfaces inside the container
# The '&' is crucial to run it in the background
echo "--- Starting ComfyUI in the background ---"
python /app/ComfyUI/main.py --listen &

# 3. Wait for a few seconds to ensure ComfyUI has started before launching the API
echo "--- Waiting for ComfyUI to start ---"
sleep 10

# 4. Start the FastAPI wrapper in the foreground
# It reads the workflow mounted at /workflow/workflow_api.json
# --host 0.0.0.0 makes the API accessible from outside the Docker container
echo "--- Starting FastAPI Wrapper ---"
python run_api.py \
    --workflow /workflow/workflow_api.json \
    --host 0.0.0.0 \
    --port 5528