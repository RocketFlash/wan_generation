#!/bin/bash

API_URL="http://localhost:5528/generate-video"
DEFAULT_PROMPT="POV, Woman lying on her back. The action presented on screen is pov_anal_missionary."
DEFAULT_NEGATIVE_PROMPT="Overexposure, subtitles, paintings, poorly drawn hands/faces, deformed limbs, cluttered background, low quality, blurry, distorted"

usage() {
    echo "Usage: $0 FOLDER_PATH [OPTIONS]"
    echo ""
    echo "Process all images in FOLDER_PATH through the video generation API"
    echo ""
    echo "Options:"
    echo "  -p, --prompt TEXT        Positive prompt (default: '$DEFAULT_PROMPT')"
    echo "  -n, --negative TEXT      Negative prompt (default: '$DEFAULT_NEGATIVE_PROMPT')"
    echo "  -u, --url URL            API URL (default: $API_URL)"
    echo "  -h, --help               Display this help message"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

FOLDER_PATH="$1"
shift  # Remove folder path from arguments

# Check if folder exists
if [ ! -d "$FOLDER_PATH" ]; then
    echo "Error: Directory '$FOLDER_PATH' does not exist"
    exit 1
fi

PROMPT="$DEFAULT_PROMPT"
NEGATIVE_PROMPT="$DEFAULT_NEGATIVE_PROMPT"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--prompt)
            PROMPT="$2"
            shift 2
            ;;
        -n|--negative)
            NEGATIVE_PROMPT="$2"
            shift 2
            ;;
        -u|--url)
            API_URL="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

echo "Starting video generation process:"
echo "Folder: $FOLDER_PATH"
echo "API URL: $API_URL"
echo "Prompt: $PROMPT"
echo "Negative Prompt: $NEGATIVE_PROMPT"
echo ""

TOTAL_IMAGES=$(find "$FOLDER_PATH" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.webp" \) | wc -l)
echo "Found $TOTAL_IMAGES images to process"
echo ""

PROCESSED=0
SUCCESS=0
FAILED=0
SUCCESSFUL_VIDEOS=()

find "$FOLDER_PATH" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.webp" \) | while read -r IMAGE_PATH; do
    FILENAME=$(basename "$IMAGE_PATH")
    PROCESSED=$((PROCESSED + 1))
    
    echo "[$PROCESSED/$TOTAL_IMAGES] Processing: $FILENAME"
    
    RESPONSE=$(curl -s -X POST "$API_URL" \
        -F "image=@$IMAGE_PATH" \
        -F "prompt=$PROMPT" \
        -F "negative_prompt=$NEGATIVE_PROMPT")
    
    # Check if the response contains a generated_video_path
    if echo "$RESPONSE" | grep -q "generated_video_path"; then
        VIDEO_PATH=$(echo "$RESPONSE" | sed -n 's/.*"generated_video_path":"\([^"]*\)".*/\1/p')
        echo "✓ Success: $VIDEO_PATH"
        SUCCESS=$((SUCCESS + 1))
        SUCCESSFUL_VIDEOS+=("$VIDEO_PATH")
    else
        ERROR=$(echo "$RESPONSE" | sed -n 's/.*"error":"\([^"]*\)".*/\1/p')
        if [ -z "$ERROR" ]; then
            ERROR="Unknown error"
        fi
        echo "✗ Failed: $ERROR"
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
done

exit 0