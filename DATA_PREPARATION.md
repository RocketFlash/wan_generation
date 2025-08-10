# Video Compilation to Training Dataset Pipeline

This repository contains a set of Python scripts to process horizontally concatenated compilation videos and convert them into a training dataset with captions for LoRA fine-tuning. The pipeline is designed to handle videos where three sub-videos are placed side-by-side horizontally, with each sub-video containing temporally concatenated clips.

## Pipeline Overview

The processing pipeline consists of four sequential steps:

1. **Split Compilation Video** - Separates the horizontal compilation into individual parts and detects scene changes
2. **Split Videos on Chunks** - Converts scenes into standardized chunks with specific resolution, FPS, and duration
3. **Create Dataset** - Filters and selects the best chunks to create a balanced training dataset
4. **Generate Captions** - Creates descriptive captions for each selected video chunk

## Prerequisites

- Python 3.8+
- FFmpeg installed and accessible in PATH
- CUDA-compatible GPU (recommended for caption generation)
- Required Python packages:
  ```bash
  pip install click opencv-python tqdm scenedetect torch transformers qwen-vl-utils
  ```

## Usage Guide

### Step 1: Split Compilation Video

Splits a horizontally concatenated video into three parts and performs scene detection on each part.

```bash
python split_compilation_video.py \
    --input-video path/to/compilation_video.mp4 \
    --output-dir path/to/output_folder \
    --cleanup  # Optional: removes intermediate files
```

**What it does:**
- Splits the input video into three equal horizontal sections
- Performs scene detection on each section using content-based detection
- Consolidates all detected scenes into a single `all_scenes` folder
- Optionally cleans up intermediate files

**Output:** Individual scene files in `output_folder/all_scenes/`

### Step 2: Split Videos on Chunks

Processes the detected scenes to create standardized video chunks with consistent properties.

```bash
python split_videos_on_chunks.py \
    --input-dir path/to/output_folder/all_scenes \
    --output-dir path/to/chunks_output \
    --width 480 \
    --height 832 \
    --fps 16 \
    --chunk-length 5
```

**Parameters:**
- `--width`, `--height`: Target resolution for all chunks
- `--fps`: Target frame rate
- `--chunk-length`: Maximum duration of each chunk in seconds

**What it does:**
- Resizes videos to specified dimensions while maintaining aspect ratio
- Standardizes frame rate across all chunks
- Splits longer scenes into precise chunks of specified length
- Processes videos in parallel for efficiency

**Output:** Standardized chunks in `chunks_output/clips_{width}x{height}_{fps}fps_{chunk_length}s/`

### Step 3: Create Dataset

Filters chunks by duration and creates a balanced training dataset by selecting representative samples.

```bash
python create_dataset.py \
    --input-dir path/to/chunks_output/clips_480x832_16fps_5s \
    --output-dir path/to/final_dataset \
    --num-chunks 1 \
    --min-len-threshold 3.0 \
    --max-len-threshold 5.0 \
    --seed 42
```

**Parameters:**
- `--num-chunks`: Maximum number of chunks to select per original source video
- `--min-len-threshold`, `--max-len-threshold`: Duration filters in seconds
- `--seed`: Random seed for reproducible dataset creation

**Selection Logic:**
- Filters chunks by duration thresholds
- Groups chunks by original source video
- Applies smart selection rules:
  - If >2 chunks: excludes first and last chunks (transition artifacts)
  - If 2 chunks: excludes last chunk
  - If 1 chunk: includes the single chunk
- Randomly samples from eligible chunks per source

**Output:** Curated dataset with statistics summary

### Step 4: Generate Captions

Creates descriptive captions for each video chunk using a vision-language model.

```bash
python generate_captions.py \
    --input-folder path/to/final_dataset \
    --trigger-word "A woman" \
    --fps 1 \
    --max_tokens 256
```

**Parameters:**
- `--trigger-word`: Word that must appear at the start of each caption
- `--fps`: Processing frame rate for the vision model
- `--max_tokens`: Maximum length of generated captions

**What it does:**
- Uses Qwen2.5-VL model to analyze video content
- Generates captions focusing on:
  - Woman's appearance and features
  - Emotional state and gaze direction
  - Environment and lighting conditions
- Saves captions as `.txt` files alongside video files

**Output:** `.txt` caption files matching each video file

## Complete Example Workflow

```bash
# Step 1: Split compilation video
python split_compilation_video.py \
    --input-video compilation.mp4 \
    --output-dir ./processing \
    --cleanup

# Step 2: Create standardized chunks
python split_videos_on_chunks.py \
    --input-dir ./processing/all_scenes \
    --output-dir ./chunks \
    --width 480 --height 832 --fps 16 --chunk-length 5

# Step 3: Create balanced dataset
python create_dataset.py \
    --input-dir ./chunks/clips_480x832_16fps_5s \
    --output-dir ./final_dataset \
    --num-chunks 1 --min-len-threshold 3.0 --max-len-threshold 5.0

# Step 4: Generate captions
python generate_captions.py \
    --input-folder ./final_dataset \
    --trigger-word "A woman" \
    --fps 1 --max_tokens 256
```

## Output Structure

```
final_dataset/
├── video1-chunk-001.mp4
├── video1-chunk-001.txt
├── video2-chunk-003.mp4
├── video2-chunk-003.txt
└── ...
```

Each video file has a corresponding text file with the same base name containing the generated caption.

## Notes

- The pipeline is optimized for first-person POV video content
- Scene detection works best with content that has clear visual transitions
- Caption generation requires significant GPU memory for the vision-language model
- All scripts support parallel processing where applicable for better performance
- The dataset creation step provides detailed statistics about the final dataset composition