The service wraps ComfyUI in a Docker container and exposes it through a FastAPI interface, allowing you to generate videos from images via HTTP requests. This is particularly useful for batch processing and integration with other applications.

## Prerequisites

- Docker with GPU support (nvidia-docker2)
- NVIDIA GPU with sufficient VRAM
- Docker Buildx (for multi-platform builds)
- ComfyUI models directory
- ComfyUI workflow configuration file (`workflow_api.json`)

## Quick Start

1. **Build the Docker image:**
   ```bash
   ./scripts/build.sh
   ```

2. **Run the service:**
   ```bash
   ./scripts/run.sh \
       --models /path/to/your/comfyui/models \
       --workflow /path/to/workflow_api.json \
       --output /path/to/output/directory \
       --port 5528
   ```

3. **Test the API:**
   ```bash
   curl -X POST http://localhost:5528/generate-video \
       -F "image=@test_image.jpg" \
       -F "prompt=Your generation prompt" \
       -F "negative_prompt=unwanted elements"
   ```

## Script Documentation

### Core Container Management

#### `build.sh`
Builds the Docker image for the ComfyUI service.

```bash
./scripts/build.sh
```

**What it does:**
- Builds Docker image named `comfy-i2v-service`
- Uses the parent directory as build context
- Includes all necessary dependencies for ComfyUI and FastAPI

#### `run.sh`
Starts the ComfyUI service container with proper volume mounts and configuration.

```bash
./scripts/run.sh --models MODELS_DIR --workflow WORKFLOW_FILE --output OUTPUT_DIR [--port PORT]
```

**Required Arguments:**
- `--models, -m`: Absolute path to ComfyUI models directory
- `--workflow, -w`: Absolute path to `workflow_api.json` file  
- `--output, -o`: Absolute path to output directory for generated videos

**Optional Arguments:**
- `--port, -p`: API port (default: 5528)

**Features:**
- Validates all paths before starting
- Checks for existing containers with the same name
- Creates output directory if it doesn't exist
- Mounts GPU support automatically
- Uses `--rm` flag for automatic cleanup

#### `stop.sh`
Stops and removes the running container.

```bash
./scripts/stop.sh
```

#### `start.sh`
Internal startup script that runs inside the container. This script:
- Creates symbolic links for model directories
- Starts ComfyUI server in background
- Launches FastAPI wrapper on foreground

### Container Utilities

#### `logs.sh`
Displays real-time logs from the running container.

```bash
./scripts/logs.sh
```

**Usage:**
- Tails logs in real-time
- Press Ctrl+C to exit
- Useful for debugging and monitoring

#### `shell.sh`
Opens an interactive bash shell inside the running container.

```bash
./scripts/shell.sh
```

**Use cases:**
- Debugging container issues
- Installing additional packages
- Examining file structure
- Manual testing

### Batch Processing

#### `experiments.sh`
Processes all images in a directory through the video generation API.

```bash
./scripts/experiments.sh FOLDER_PATH [OPTIONS]
```

**Arguments:**
- `FOLDER_PATH`: Directory containing images to process

**Options:**
- `--prompt, -p`: Positive prompt (default: POV-specific prompt)
- `--negative, -n`: Negative prompt (default: quality filters)
- `--url, -u`: API URL (default: http://localhost:5528/generate-video)
- `--help, -h`: Show help message

**Features:**
- Supports multiple image formats (jpg, jpeg, png, gif, bmp, webp)
- Progress tracking with success/failure counts
- Error handling and reporting
- Batch processing with status updates

**Example:**
```bash
./scripts/experiments.sh /path/to/images \
    --prompt "A woman laying on ..." \
    --negative "blurry, low quality, distorted"
```

## Complete Workflow Example

```bash
# 1. Build the Docker image
./scripts/build.sh

# 2. Start the service
./scripts/run.sh \
    --models /home/user/ComfyUI/models \
    --workflow /home/user/workflow_api.json \
    --output /home/user/generated_videos \
    --port 5528

# 3. Monitor logs (in another terminal)
./scripts/logs.sh

# 4. Run batch experiments
./scripts/experiments.sh /path/to/test/images \
    --prompt "POV: A woman in elegant dress" \
    --negative "blurry, distorted, low quality"

# 5. Access container shell if needed
./scripts/shell.sh

# 6. Stop the service when done
./scripts/stop.sh
```

## API Endpoints

The FastAPI wrapper exposes the following endpoint:

### POST `/generate-video`

Generates a video from an input image using the configured ComfyUI workflow.

**Request:**
- `image`: Image file (multipart/form-data)
- `prompt`: Text prompt for generation
- `negative_prompt`: Negative prompt to avoid unwanted elements

**Response:**
```json
{
    "generated_video_path": "/path/to/generated/video.mp4",
    "status": "success"
}
```

**Error Response:**
```json
{
    "error": "Error description",
    "status": "failed"
}
```

## Directory Structure

```
project/
├── scripts/
│   ├── build.sh           # Build Docker image
│   ├── run.sh             # Start container
│   ├── stop.sh            # Stop container
│   ├── start.sh           # Internal startup script
│   ├── logs.sh            # View container logs
│   ├── shell.sh           # Access container shell
│   └── experiments.sh     # Batch processing script
├── Dockerfile             # Container definition
├── run_api.py            # FastAPI wrapper
```

## Configuration Requirements

### Models Directory
Your ComfyUI models directory should contain:
- Checkpoints
- VAE models
- ControlNet models
- Any other required model files

### Workflow File
The `workflow_api.json` should be exported from ComfyUI and contain:
- Complete node configuration
- Input/output specifications
- Model references

## Troubleshooting

**Container won't start:**
- Check if required directories exist
- Verify Docker has GPU access
- Ensure no other container uses the same name

**API not responding:**
- Check logs with `./scripts/logs.sh`
- Verify ComfyUI started successfully
- Check if workflow file is valid

**GPU not detected:**
- Ensure nvidia-docker2 is installed
- Verify GPU drivers are compatible
- Check Docker GPU runtime configuration

**Memory issues:**
- Reduce batch size in workflow
- Use lighter models
- Monitor VRAM usage with `nvidia-smi`

## Development

To modify the service:

1. **Update the API:** Edit `run_api.py`
2. **Change container behavior:** Modify `start.sh`
4. **Debug issues:** Use `./scripts/shell.sh` for interactive debugging

## Notes

- The container automatically removes itself when stopped (`--rm` flag)
- All generated videos are saved to the mounted output directory
- The service supports concurrent requests (FastAPI handles async operations)
- Model loading happens once at startup for better performance
- Scripts are designed to be idempotent and safe to re-run