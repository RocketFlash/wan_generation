#!/bin/bash

# ComfyUI Model Downloader Script
# Downloads all necessary models for Wan2.1 VACE Video Generation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default models directory
DEFAULT_MODELS_DIR="./models"

# Function to display usage
show_help() {
    cat << EOF
ComfyUI Model Downloader for Wan2.1 VACE Video Generation

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --models-dir PATH       Directory to download models (default: ./models)
    --skip-existing         Skip downloads if files already exist
    --help, -h              Show this help message

DESCRIPTION:
    This script downloads all necessary models for the Wan2.1 VACE video generation workflow:
    - Wan2.1-VACE-14B model and components from HuggingFace
    - VAE model
    - CLIP encoder
    - LoRA models from CivitAI and HuggingFace
    
    The script creates the proper ComfyUI directory structure automatically.

EXAMPLES:
    # Download to default ./models directory:
    $0
    
    # Download to custom directory:
    $0 --models-dir /path/to/comfyui/models
    
    # Skip existing files:
    $0 --models-dir ./models --skip-existing

EOF
}

# Function to log messages with colors
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $1${NC}" >&2
}

# Function to check if a command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed or not in PATH"
        log_error "Please install $1 and try again"
        exit 1
    fi
}

# Function to download file with progress
download_file() {
    local url="$1"
    local output_path="$2"
    local description="$3"
    
    if [[ "$SKIP_EXISTING" == "true" && -f "$output_path" ]]; then
        log_warning "Skipping $description (file already exists): $output_path"
        return 0
    fi
    
    log "Downloading $description..."
    log "URL: $url"
    log "Output: $output_path"
    
    # Create directory if it doesn't exist
    mkdir -p "$(dirname "$output_path")"
    
    # Download with progress bar
    if command -v wget &> /dev/null; then
        wget --progress=bar:force:noscroll -O "$output_path" "$url"
    elif command -v curl &> /dev/null; then
        curl -L --progress-bar -o "$output_path" "$url"
    else
        log_error "Neither wget nor curl is available"
        exit 1
    fi
    
    # Verify download
    if [[ -f "$output_path" && -s "$output_path" ]]; then
        local file_size=$(du -h "$output_path" | cut -f1)
        log_success "Downloaded $description (${file_size})"
    else
        log_error "Failed to download $description"
        exit 1
    fi
}

# Function to download from HuggingFace
download_huggingface() {
    local repo="$1"
    local filename="$2"
    local output_path="$3"
    local description="$4"
    
    local url="https://huggingface.co/${repo}/resolve/main/${filename}"
    download_file "$url" "$output_path" "$description"
}

# Function to download from CivitAI
download_civitai() {
    local model_version_id="$1"
    local output_path="$2"
    local description="$3"
    
    local url="https://civitai.com/api/download/models/${model_version_id}"
    download_file "$url" "$output_path" "$description"
}

# Parse command line arguments
MODELS_DIR="$DEFAULT_MODELS_DIR"
SKIP_EXISTING="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        --models-dir)
            MODELS_DIR="$2"
            shift 2
            ;;
        --skip-existing)
            SKIP_EXISTING="true"
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

# Check dependencies
log "Checking dependencies..."
if command -v wget &> /dev/null; then
    log_success "wget found"
elif command -v curl &> /dev/null; then
    log_success "curl found"
else
    log_error "Neither wget nor curl is available"
    log_error "Please install wget or curl and try again"
    exit 1
fi

# Convert to absolute path
MODELS_DIR="$(cd "$(dirname "$MODELS_DIR")" 2>/dev/null && pwd)/$(basename "$MODELS_DIR")" || MODELS_DIR="$(realpath "$MODELS_DIR")"

log "Starting model downloads..."
log "Models directory: $MODELS_DIR"
log "Skip existing files: $SKIP_EXISTING"
echo ""

# Create ComfyUI directory structure
log "Creating ComfyUI directory structure..."
mkdir -p "$MODELS_DIR"/{unet,vae,clip,loras,checkpoints,controlnet}
log_success "Directory structure created"

# Define model downloads with CORRECTED paths and filenames
declare -A MODELS

# Wan2.1-VACE-14B model (GGUF format) - CORRECTED filename
MODELS["unet/Wan2.1_14B_VACE-Q8_0.gguf"]="QuantStack/Wan2.1_14B_VACE-GGUF|Wan2.1_14B_VACE-Q8_0.gguf|Wan2.1-VACE-14B UNet model (GGUF)"

# CLIP encoder from city96
MODELS["clip/umt5-xxl-encoder-Q8_0.gguf"]="city96/umt5-xxl-encoder-gguf|umt5-xxl-encoder-Q8_0.gguf|UMT5 XXL CLIP encoder (GGUF)"

# VAE model from Comfy-Org - CORRECTED source and filename
MODELS["vae/wan_2.1_vae.safetensors"]="Comfy-Org/Wan_2.1_ComfyUI_repackaged|split_files/vae/wan_2.1_vae.safetensors|Wan 2.1 VAE model"

# CausVid LoRA from Kijai - NOTE: this file may not exist, will try anyway
MODELS["loras/Wan21_CausVid_14B_T2V_lora_rank32.safetensors"]="Kijai/WanVideo_comfy|Wan21_CausVid_14B_T2V_lora_rank32.safetensors|Wan2.1 CausVid T2V LoRA"

log "Downloading entire Wan2.1-I2V-14B-480P repository..."
if command -v git &> /dev/null; then
    git clone https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-480P "$MODELS_DIR/Wan2.1-I2V-14B-480P"
elif command -v huggingface-cli &> /dev/null; then
    huggingface-cli download Wan-AI/Wan2.1-I2V-14B-480P --local-dir "$MODELS_DIR/Wan2.1-I2V-14B-480P"
else
    log_error "Cannot download repository - need git or huggingface-cli"
fi

# Download models from HuggingFace
log "Downloading models from HuggingFace..."
for model_path in "${!MODELS[@]}"; do
    IFS='|' read -r repo filename description <<< "${MODELS[$model_path]}"
    output_path="$MODELS_DIR/$model_path"
    
    # Special handling for the CausVid LoRA which might not exist
    if [[ "$filename" == "Wan21_CausVid_14B_T2V_lora_rank32.safetensors" ]]; then
        log_warning "Attempting to download CausVid LoRA - this file might not exist in the repository"
        if ! download_huggingface "$repo" "$filename" "$output_path" "$description" 2>/dev/null; then
            log_warning "CausVid LoRA not found at expected location, skipping..."
            continue
        fi
    else
        download_huggingface "$repo" "$filename" "$output_path" "$description"
    fi
    echo ""
done

# Download LoRA from CivitAI
log "Downloading LoRA from CivitAI..."
civitai_lora_path="$MODELS_DIR/loras/pov_anal_missionary.safetensors"
download_civitai "2093069" "$civitai_lora_path" "POV Anal Missionary LoRA"
echo ""

# Verify all downloads (excluding potentially missing CausVid LoRA)
log "Verifying downloads..."
all_files_present=true

expected_files=(
    "unet/Wan2.1_14B_VACE-Q8_0.gguf"
    "clip/umt5-xxl-encoder-Q8_0.gguf" 
    "vae/wan_2.1_vae.safetensors"
    "loras/pov_anal_missionary.safetensors"
)

# Check if CausVid LoRA was downloaded
if [[ -f "$MODELS_DIR/loras/Wan21_CausVid_14B_T2V_lora_rank32.safetensors" ]]; then
    expected_files+=("loras/Wan21_CausVid_14B_T2V_lora_rank32.safetensors")
fi

for file in "${expected_files[@]}"; do
    full_path="$MODELS_DIR/$file"
    if [[ -f "$full_path" && -s "$full_path" ]]; then
        file_size=$(du -h "$full_path" | cut -f1)
        log_success "✓ $file (${file_size})"
    else
        log_error "✗ Missing or empty: $file"
        all_files_present=false
    fi
done

echo ""

if [[ "$all_files_present" == "true" ]]; then
    log_success "🎉 All available models downloaded successfully!"
    echo ""
    log "📁 Models directory structure:"
    tree "$MODELS_DIR" 2>/dev/null || find "$MODELS_DIR" -type f | sort | sed 's|^|  |'
    echo ""
    log "🚀 Ready to use with ComfyUI!"
    echo ""
    log "💡 Usage tips:"
    echo "   - Use this models directory with: ./scripts/run.sh --models $MODELS_DIR"
    echo "   - Update your workflow_api.json to use these exact filenames:"
    echo "     * UNet: Wan2.1_14B_VACE-Q8_0.gguf (note the corrected filename)"
    echo "     * CLIP: umt5-xxl-encoder-Q8_0.gguf"
    echo "     * VAE: wan_2.1_vae.safetensors"
    echo "     * LoRA: pov_anal_missionary.safetensors"
    echo ""
    log "⚠️  Note about your workflow:"
    echo "   - Your current workflow expects: Wan2.1-VACE-14B-Q8_0.gguf"
    echo "   - Downloaded filename is: Wan2.1_14B_VACE-Q8_0.gguf"
    echo "   - You'll need to update your workflow JSON or rename the file"
else
    log_error "❌ Some models failed to download. Please check the errors above and try again."
    exit 1
fi

# Display final summary
echo ""
log "=== DOWNLOAD SUMMARY ==="
total_size=$(du -sh "$MODELS_DIR" | cut -f1)
file_count=$(find "$MODELS_DIR" -type f | wc -l)
log "Total size: $total_size"
log "Total files: $file_count"
log "Location: $MODELS_DIR"

echo ""
log "=== MODEL SOURCES ==="
echo "✓ Wan2.1-VACE-14B GGUF: QuantStack/Wan2.1_14B_VACE-GGUF"
echo "✓ UMT5 CLIP encoder: city96/umt5-xxl-encoder-gguf"  
echo "✓ VAE: Comfy-Org/Wan_2.1_ComfyUI_repackaged"
echo "✓ POV LoRA: CivitAI Model 1849520"
if [[ -f "$MODELS_DIR/loras/Wan21_CausVid_14B_T2V_lora_rank32.safetensors" ]]; then
    echo "✓ CausVid LoRA: Kijai/WanVideo_comfy"
else
    echo "⚠️  CausVid LoRA: Not found (may not exist in repository)"
fi

echo ""
log "=== NEXT STEPS ==="
echo "1. Update your workflow JSON to use the correct UNet filename:"
echo "   Change: 'Wan2.1-VACE-14B-Q8_0.gguf'"
echo "   To: 'Wan2.1_14B_VACE-Q8_0.gguf'"
echo ""
echo "2. Or rename the downloaded file to match your workflow:"
echo "   mv '$MODELS_DIR/unet/Wan2.1_14B_VACE-Q8_0.gguf' '$MODELS_DIR/unet/Wan2.1-VACE-14B-Q8_0.gguf'"
echo ""
echo "3. Use the models directory with your ComfyUI Docker setup:"
echo "   ./scripts/run.sh --models '$MODELS_DIR' --workflow workflow_api.json --output ./output"
echo ""
echo "4. Ensure you have sufficient GPU memory (recommended: 24GB+ VRAM for Q8 models)"
echo ""
log_success "Setup complete! 🎬"