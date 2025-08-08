#!/bin/bash
set -e

# --- Script Defaults ---
# The default port if none is provided via arguments.
DEFAULT_PORT=5528
# The name for the Docker image you built
IMAGE_NAME="comfy-i2v-service"
# A name for the running container
CONTAINER_NAME="my-comfy-api"

# --- Help Message ---
usage() {
    echo "Usage: $0 -m <models_dir> -w <workflow_file> -o <output_dir> [-p <port>]"
    echo "  -m, --models     Absolute path to the ComfyUI models directory. (Required)"
    echo "  -w, --workflow   Absolute path to the workflow_api.json file. (Required)"
    echo "  -o, --output     Absolute path to the directory for generated outputs. (Required)"
    echo "  -p, --port       Optional. Port to expose the API on. Default: $DEFAULT_PORT"
    echo "  -h, --help       Display this help message."
    exit 1
}

# --- Parse Command-Line Arguments ---
# Initialize variables
MODELS_DIR=""
WORKFLOW_FILE=""
OUTPUT_DIR=""
PORT=$DEFAULT_PORT

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -m|--models) MODELS_DIR="$2"; shift ;;
        -w|--workflow) WORKFLOW_FILE="$2"; shift ;;
        -o|--output) OUTPUT_DIR="$2"; shift ;;
        -p|--port) PORT="$2"; shift ;;
        -h|--help) usage ;;
        *) echo "Unknown parameter passed: $1"; usage ;;
    esac
    shift
done

# --- Pre-run Checks ---
echo "--- Performing pre-run checks ---"
# Check if mandatory arguments were provided
if [ -z "$MODELS_DIR" ] || [ -z "$WORKFLOW_FILE" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Error: Missing one or more required arguments."
    usage
fi

# Check if a container with the same name is already running
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo "Error: A container named '$CONTAINER_NAME' is already running."
    echo "Please run 'scripts/stop.sh' first."
    exit 1
fi

# Check if the required directories and files exist on your host machine
if [ ! -d "$MODELS_DIR" ]; then
    echo "Error: Models directory not found at '$MODELS_DIR'"
    exit 1
fi
if [ ! -f "$WORKFLOW_FILE" ]; then
    echo "Error: Workflow file not found at '$WORKFLOW_FILE'"
    exit 1
fi
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Warning: Output directory not found at '$OUTPUT_DIR'. Creating it now."
    mkdir -p "$OUTPUT_DIR"
fi
echo "--- Checks passed ---"
echo "--- Configuration ---"
echo "  Models dir:    $MODELS_DIR"
echo "  Workflow file: $WORKFLOW_FILE"
echo "  Output dir:    $OUTPUT_DIR"
echo "  API Port:      $PORT"
echo "-------------------"


# --- Run Docker Container ---
echo "--- Starting container: $CONTAINER_NAME ---"
docker run -d -p "$PORT:$PORT" \
  --gpus all \
  -v "$MODELS_DIR":/models \
  -v "$WORKFLOW_FILE":/workflow/workflow_api.json \
  -v "$OUTPUT_DIR":/app/ComfyUI/output \
  --name $CONTAINER_NAME \
  --rm \
  $IMAGE_NAME

echo "--- Container started successfully ---"
echo "API will be available on port $PORT"
echo "To see logs, run: ./scripts/logs.sh"
echo "To stop, run: ./scripts/stop.sh"