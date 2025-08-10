#!/bin/bash

# Video Compilation to Training Dataset Pipeline
# This script processes horizontally concatenated compilation videos into training datasets

set -e  # Exit on any error

# Default values
WIDTH=480
HEIGHT=832
FPS=16
CHUNK_LENGTH=5
NUM_CHUNKS=1
MIN_LEN_THRESHOLD=3.0
MAX_LEN_THRESHOLD=5.0
SEED=42
TRIGGER_WORD="pov_anal_missionary"
CAPTION_FPS=1
MAX_TOKENS=256
CLEANUP=true

# Function to display usage
show_help() {
    cat << EOF
Video Compilation to Training Dataset Pipeline

USAGE:
    $0 --input-video INPUT_VIDEO --output-dir OUTPUT_DIR [OPTIONS]

REQUIRED ARGUMENTS:
    --input-video PATH      Path to the horizontally concatenated input video
    --output-dir PATH       Base directory where all outputs will be saved

OPTIONAL ARGUMENTS:
    Video Processing:
        --width INT             Target width for video chunks (default: 480)
        --height INT            Target height for video chunks (default: 832)
        --fps INT               Target frames per second (default: 16)
        --chunk-length INT      Maximum chunk length in seconds (default: 5)

    Dataset Creation:
        --num-chunks INT        Max chunks per source video (default: 1)
        --min-len FLOAT         Minimum chunk length in seconds (default: 3.0)
        --max-len FLOAT         Maximum chunk length in seconds (default: 5.0)
        --seed INT              Random seed for reproducibility (default: 42)

    Caption Generation:
        --trigger-word STRING   Word to start each caption (default: "A woman")
        --caption-fps INT       Processing FPS for captioning (default: 1)
        --max-tokens INT        Maximum caption length in tokens (default: 256)

    Other:
        --no-cleanup            Keep intermediate files (default: cleanup enabled)
        --help, -h              Show this help message

EXAMPLES:
    # Basic usage with defaults:
    $0 --input-video video.mp4 --output-dir ./results

    # Custom resolution and settings:
    $0 --input-video video.mp4 --output-dir ./results \\
       --width 512 --height 768 --fps 24 \\
       --trigger-word "A person" --no-cleanup

    # High-quality dataset with multiple chunks:
    $0 --input-video video.mp4 --output-dir ./results \\
       --num-chunks 2 --min-len 4.0 --max-len 6.0

EOF
}

# Function to log messages with timestamps
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to log errors
log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# Function to check if a command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed or not in PATH"
        exit 1
    fi
}

# Function to check if Python script exists
check_script() {
    if [[ ! -f "$1" ]]; then
        log_error "Script not found: $1"
        log_error "Make sure all Python scripts are in the same directory as this bash script"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --input-video)
            INPUT_VIDEO="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --width)
            WIDTH="$2"
            shift 2
            ;;
        --height)
            HEIGHT="$2"
            shift 2
            ;;
        --fps)
            FPS="$2"
            shift 2
            ;;
        --chunk-length)
            CHUNK_LENGTH="$2"
            shift 2
            ;;
        --num-chunks)
            NUM_CHUNKS="$2"
            shift 2
            ;;
        --min-len)
            MIN_LEN_THRESHOLD="$2"
            shift 2
            ;;
        --max-len)
            MAX_LEN_THRESHOLD="$2"
            shift 2
            ;;
        --seed)
            SEED="$2"
            shift 2
            ;;
        --trigger-word)
            TRIGGER_WORD="$2"
            shift 2
            ;;
        --caption-fps)
            CAPTION_FPS="$2"
            shift 2
            ;;
        --max-tokens)
            MAX_TOKENS="$2"
            shift 2
            ;;
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$INPUT_VIDEO" ]]; then
    log_error "Input video path is required (--input-video)"
    echo "Use --help for usage information"
    exit 1
fi

if [[ -z "$OUTPUT_DIR" ]]; then
    log_error "Output directory is required (--output-dir)"
    echo "Use --help for usage information"
    exit 1
fi

# Validate input video exists
if [[ ! -f "$INPUT_VIDEO" ]]; then
    log_error "Input video file does not exist: $INPUT_VIDEO"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if required commands exist
log "Checking dependencies..."
check_command "python"
check_command "ffmpeg"
check_command "ffprobe"

# Check if Python scripts exist
check_script "$SCRIPT_DIR/split_compilation_video.py"
check_script "$SCRIPT_DIR/split_videos_on_chunks.py"
check_script "$SCRIPT_DIR/create_dataset.py"
check_script "$SCRIPT_DIR/generate_captions.py"

# Create output directory
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"  # Convert to absolute path

# Define intermediate directories
PROCESSING_DIR="$OUTPUT_DIR/processing"
CHUNKS_DIR="$OUTPUT_DIR/chunks"
DATASET_DIR="$OUTPUT_DIR/final_dataset"

log "Starting Video Compilation to Training Dataset Pipeline"
log "Input video: $INPUT_VIDEO"
log "Output directory: $OUTPUT_DIR"
log "Settings: ${WIDTH}x${HEIGHT}, ${FPS}fps, ${CHUNK_LENGTH}s chunks"

# Step 1: Split compilation video
log "=== Step 1/4: Splitting compilation video ==="
log "Splitting video into parts and detecting scenes..."

if [[ "$CLEANUP" == "true" ]]; then
    python "$SCRIPT_DIR/split_compilation_video.py" \
        --input-video "$INPUT_VIDEO" \
        --output-dir "$PROCESSING_DIR" \
        --cleanup
else
    python "$SCRIPT_DIR/split_compilation_video.py" \
        --input-video "$INPUT_VIDEO" \
        --output-dir "$PROCESSING_DIR" \
        --no-cleanup
fi

# Check if scenes were created
if [[ ! -d "$PROCESSING_DIR/all_scenes" ]] || [[ -z "$(ls -A "$PROCESSING_DIR/all_scenes" 2>/dev/null)" ]]; then
    log_error "No scenes were detected in Step 1. Check your input video."
    exit 1
fi

SCENE_COUNT=$(find "$PROCESSING_DIR/all_scenes" -name "*.mp4" | wc -l)
log "✅ Step 1 complete. Detected $SCENE_COUNT scenes."

# Step 2: Split videos on chunks
log "=== Step 2/4: Creating standardized chunks ==="
log "Processing scenes into ${WIDTH}x${HEIGHT} chunks at ${FPS}fps..."

python "$SCRIPT_DIR/split_videos_on_chunks.py" \
    --input-dir "$PROCESSING_DIR/all_scenes" \
    --output-dir "$CHUNKS_DIR" \
    --width "$WIDTH" \
    --height "$HEIGHT" \
    --fps "$FPS" \
    --chunk-length "$CHUNK_LENGTH"

# Check if chunks were created
CHUNK_FOLDER="$CHUNKS_DIR/clips_${WIDTH}x${HEIGHT}_${FPS}fps_${CHUNK_LENGTH}s"
if [[ ! -d "$CHUNK_FOLDER" ]] || [[ -z "$(ls -A "$CHUNK_FOLDER" 2>/dev/null)" ]]; then
    log_error "No chunks were created in Step 2."
    exit 1
fi

CHUNK_COUNT=$(find "$CHUNK_FOLDER" -name "*.mp4" | wc -l)
log "✅ Step 2 complete. Created $CHUNK_COUNT chunks."

# Step 3: Create dataset
log "=== Step 3/4: Creating balanced training dataset ==="
log "Filtering chunks (${MIN_LEN_THRESHOLD}s-${MAX_LEN_THRESHOLD}s) and selecting up to $NUM_CHUNKS per source..."

python "$SCRIPT_DIR/create_dataset.py" \
    --input-dir "$CHUNK_FOLDER" \
    --output-dir "$DATASET_DIR" \
    --num-chunks "$NUM_CHUNKS" \
    --min-len-threshold "$MIN_LEN_THRESHOLD" \
    --max-len-threshold "$MAX_LEN_THRESHOLD" \
    --seed "$SEED"

# Check if dataset was created
if [[ ! -d "$DATASET_DIR" ]] || [[ -z "$(ls -A "$DATASET_DIR" 2>/dev/null)" ]]; then
    log_error "No files were selected for the final dataset in Step 3."
    log_error "Try adjusting --min-len and --max-len thresholds."
    exit 1
fi

DATASET_COUNT=$(find "$DATASET_DIR" -name "*.mp4" | wc -l)
log "✅ Step 3 complete. Final dataset contains $DATASET_COUNT videos."

# Step 4: Generate captions
log "=== Step 4/4: Generating captions ==="
log "Creating captions with trigger word: '$TRIGGER_WORD'..."

python "$SCRIPT_DIR/generate_captions.py" \
    --input-folder "$DATASET_DIR" \
    --trigger-word "$TRIGGER_WORD" \
    --fps "$CAPTION_FPS" \
    --max_tokens "$MAX_TOKENS"

# Verify captions were created
CAPTION_COUNT=$(find "$DATASET_DIR" -name "*.txt" | wc -l)
if [[ $CAPTION_COUNT -ne $DATASET_COUNT ]]; then
    log_error "Caption generation incomplete. Expected $DATASET_COUNT captions, got $CAPTION_COUNT."
    exit 1
fi

log "✅ Step 4 complete. Generated $CAPTION_COUNT captions."

# Optional cleanup of intermediate files
if [[ "$CLEANUP" == "true" ]]; then
    log "Cleaning up intermediate files..."
    rm -rf "$PROCESSING_DIR" "$CHUNKS_DIR"
    log "✅ Cleanup complete."
fi

# Final summary
log ""
log "🎉 Pipeline completed successfully!"
log ""
log "=== SUMMARY ==="
log "Input video: $INPUT_VIDEO"
log "Output directory: $OUTPUT_DIR"
log "Final dataset: $DATASET_DIR"
log "Videos in dataset: $DATASET_COUNT"
log "Captions generated: $CAPTION_COUNT"
log "Video settings: ${WIDTH}x${HEIGHT}, ${FPS}fps, ${CHUNK_LENGTH}s chunks"
log "Dataset settings: ${MIN_LEN_THRESHOLD}s-${MAX_LEN_THRESHOLD}s, max $NUM_CHUNKS per source"
log "Caption trigger: '$TRIGGER_WORD'"
log ""
log "Ready for LoRA training! 🚀"

# Display final structure
log "Final dataset structure:"
find "$DATASET_DIR" -type f \( -name "*.mp4" -o -name "*.txt" \) | head -10 | while read -r file; do
    log "  $(basename "$file")"
done

if [[ $DATASET_COUNT -gt 10 ]]; then
    log "  ... and $((DATASET_COUNT - 10)) more video/caption pairs"
fi