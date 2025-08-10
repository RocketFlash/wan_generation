import click
from pathlib import Path
import random
import shutil
from collections import defaultdict
from tqdm import tqdm
import cv2
import sys 

@click.command()
@click.option(
    '--input-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path),
    required=True,
    help="The directory containing all the generated video chunks."
)
@click.option(
    '--output-dir',
    type=click.Path(file_okay=False, writable=True, path_type=Path),
    required=True,
    help="The directory where the final training dataset will be created."
)
@click.option(
    '--num-chunks', '-n',
    type=int,
    default=1,
    show_default=True,
    help="The maximum number of chunks to select per original source video."
)
@click.option(
    '--min-len-threshold',
    type=float,
    default=3,
    help="Minimum video length in seconds. Chunks shorter than this will be ignored."
)
@click.option(
    '--max-len-threshold',
    type=float,
    default=5,
    help="Maximum video length in seconds. Chunks longer than this will be ignored."
)
@click.option(
    '--seed',
    type=int,
    default=42,
    show_default=True,
    help="A random seed to ensure the dataset is reproducible."
)
def create_dataset_cli(
    input_dir: Path, 
    output_dir: Path, 
    num_chunks: int, 
    min_len_threshold: float, 
    max_len_threshold: float, 
    seed: int
):
    """
    Filters video chunks by length, then selects a reproducible random sample
    of N chunks per original video source to create a final training dataset.
    """
    random.seed(seed)
    click.echo(f"Using random seed: {seed}")

    output_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Searching for video chunks in: {input_dir}")

    min_len = min_len_threshold if min_len_threshold is not None else 0.0
    max_len = max_len_threshold if max_len_threshold is not None else sys.float_info.max

    all_video_files = list(input_dir.glob("*.mp4"))
    if not all_video_files:
        click.echo(f"No .mp4 files found in '{input_dir}'.", err=True)
        return

    click.echo(f"Found {len(all_video_files)} total video files. Analyzing and filtering by length...")
    
    valid_videos = []
    for video_path in tqdm(all_video_files, desc="Analyzing all videos"):
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                continue
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()

            if fps > 0 and frame_count > 0:
                duration = frame_count / fps
                # Filter by length thresholds
                if min_len <= duration <= max_len:
                    valid_videos.append({'path': video_path, 'duration': duration})
        except Exception as e:
            click.echo(f"Warning: Could not analyze video {video_path}: {e}", err=True)
    
    click.echo(f"Found {len(valid_videos)} videos that meet the length criteria.")

    grouped_clips = defaultdict(list)
    for video_info in valid_videos:
        clip_path = video_info['path']
        base_name = clip_path.stem.rsplit('-chunk-', 1)[0]
        grouped_clips[base_name].append(video_info)

    num_sources = len(grouped_clips)
    click.echo(f"Grouped into {num_sources} unique sources.")
    click.echo(f"Selecting a maximum of {num_chunks} chunk(s) per source with new rules...")

    selected_videos_info = []
    for base_name, clips_info_list in grouped_clips.items():
        # Sort by path to ensure chronological order ('...-001', '...-002')
        clips_info_list.sort(key=lambda x: x['path'])
        
        num_available = len(clips_info_list)
        eligible_for_sampling = []

        # New selection logic based on the number of chunks
        if num_available > 2:
            # If more than 2 chunks, ignore the first and the last
            eligible_for_sampling = clips_info_list[1:-1]
        elif num_available == 2:
            # If exactly 2 chunks, ignore the last one
            eligible_for_sampling = clips_info_list[:-1]
        else: # num_available is 1
            # If only 1 chunk, it's eligible
            eligible_for_sampling = clips_info_list
            
        # Determine how many clips to sample from the eligible list
        k = min(num_chunks, len(eligible_for_sampling))
        
        if k > 0:
            selected = random.sample(eligible_for_sampling, k)
            selected_videos_info.extend(selected)

    total_selected = len(selected_videos_info)
    click.echo(f"\nTotal clips selected for training dataset: {total_selected}")

    if total_selected == 0:
        click.echo("No files were selected. Exiting.")
        return

    video_lengths = []
    selected_file_paths = [info['path'] for info in selected_videos_info]
    video_lengths = [info['duration'] for info in selected_videos_info] # Already calculated

    click.echo(f"\nCopying files to '{output_dir}'...")
    for f in tqdm(selected_file_paths, desc="Copying Files"):
        try:
            shutil.copy(f, output_dir)
        except Exception as e:
            click.echo(f"Error copying {f}: {e}", err=True)
    
    click.echo(f"\n🎉 Successfully created dataset in: {output_dir}")

    # Display the final calculated statistics
    avg_len = sum(video_lengths) / len(video_lengths)
    min_len = min(video_lengths)
    max_len = max(video_lengths)

    click.echo("\n--- Dataset Statistics ---")
    click.echo(f"Average Video Length: {avg_len:.2f} seconds")
    click.echo(f"Minimum Video Length: {min_len:.2f} seconds")
    click.echo(f"Maximum Video Length: {max_len:.2f} seconds")
    click.echo("--------------------------")

if __name__ == '__main__':
    create_dataset_cli()