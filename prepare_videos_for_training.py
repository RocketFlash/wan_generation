import subprocess
import click
from pathlib import Path
import multiprocessing
from tqdm import tqdm

def process_video(video_path: Path, output_dir: Path):
    """
    Processes a single video file to resize, change FPS, and split into 5-second chunks.

    Args:
        video_path (Path): Path to the input video file.
        output_dir (Path): Directory to save the processed video chunks.
    """
    try:
        # Define a unique output name pattern for the chunks from this video
        # e.g., for "part1-scene-001.mp4", the output will be "part1-scene-001-chunk-001.mp4", etc.
        output_pattern = output_dir / f"{video_path.stem}-chunk-%03d.mp4"

        # Construct the FFmpeg command
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite output files without asking
            '-i', str(video_path),  # Input file

            # --- Video Filters ---
            # 1. Scale video to fit within 480x832, preserving aspect ratio.
            # 2. Ensure final dimensions are divisible by 2 for encoder compatibility.
            '-vf', "scale=w=480:h=832:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2",

            '-r', '16',  # Set output frame rate to 16 fps

            # --- Hardware Accelerated Encoder for macOS ---
            '-c:v', 'h264_videotoolbox',
            '-q:v', '50',  # Set video quality (lower is better, 50 is a good balance)

            # --- Audio Settings ---
            '-c:a', 'aac',    # Use AAC audio codec
            '-b:a', '128k',   # Set audio bitrate

            # --- Segmentation Settings ---
            '-f', 'segment',            # Use the segment muxer to split the video
            '-segment_time', '5',       # Create segments of 5 seconds
            '-reset_timestamps', '1',   # Reset timestamps for each segment
            
            str(output_pattern) # Output file pattern
        ]

        # Run the command, hiding the verbose FFmpeg output
        subprocess.run(
            ffmpeg_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError as e:
        # Print an error if a specific video fails
        click.echo(f"\nFailed to process {video_path.name}. Error: {e}", err=True)
    except Exception as e:
        click.echo(f"\nAn unexpected error occurred with {video_path.name}: {e}", err=True)


@click.command()
@click.option(
    '--input-dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path),
    required=True,
    help="The directory containing the video scenes to process (e.g., 'all_scenes')."
)
@click.option(
    '--output-dir',
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
    help="The directory where the final, processed videos will be saved."
)
def batch_process_cli(input_dir: Path, output_dir: Path):
    """
    A tool to batch process videos: resize, change FPS, and split into 5s chunks.
    This script processes videos in parallel for maximum speed.
    """
    # Create the output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all .mp4 videos in the input directory
    video_files = list(input_dir.glob("*.mp4"))

    if not video_files:
        click.echo(f"No .mp4 videos found in '{input_dir}'.")
        return

    click.echo(f"Found {len(video_files)} videos to process. Starting...")

    # Create a list of tasks for the multiprocessing pool
    tasks = [(video_path, output_dir) for video_path in video_files]

    # Use a multiprocessing pool to process files in parallel
    # The number of processes will default to the number of CPU cores
    with multiprocessing.Pool() as pool:
        # Use tqdm to create a progress bar over the map results
        with tqdm(total=len(tasks), desc="Processing Videos") as pbar:
            for _ in pool.starmap(process_video, tasks):
                pbar.update()

    click.echo("\n🎉 Batch processing complete!")
    click.echo(f"All processed videos are saved in: {output_dir}")


if __name__ == '__main__':
    batch_process_cli()