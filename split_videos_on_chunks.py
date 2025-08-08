import subprocess
import click
from pathlib import Path
import multiprocessing
from tqdm import tqdm

def process_video(
    video_path: Path, 
    output_dir: Path, 
    width: int, 
    height: int, 
    fps: int, 
    chunk_length: int
):
    """
    Processes a single video file to resize, change FPS, and split into precise chunks.

    Args:
        video_path (Path): Path to the input video file.
        output_dir (Path): The specific directory to save the processed chunks.
        width (int): Target width for resizing.
        height (int): Target height for resizing.
        fps (int): Target frames per second.
        chunk_length (int): The exact length of each video chunk in seconds.
    """
    try:
        output_pattern = output_dir / f"{video_path.stem}-chunk-%03d.mp4"
        vf_filter = f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2"

        # --- CHANGE: Keyframe expression is now dynamic based on chunk_length ---
        keyframe_expr = f'expr:gte(t,n_forced*{chunk_length})'

        ffmpeg_cmd = [
            'ffmpeg',
            '-y',
            '-i', str(video_path),

            '-vf', vf_filter,
            '-r', str(fps),

            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',

            '-c:a', 'aac',
            '-b:a', '128k',

            # --- Segmentation Settings ---
            '-f', 'segment',
            '-segment_time', str(chunk_length),  # Use the parameter here
            '-reset_timestamps', '1',
            
            # --- CHANGE: This is the critical fix for precise chunk length ---
            '-force_key_frames', keyframe_expr, # Force keyframes at exact cut points
            
            str(output_pattern)
        ]

        subprocess.run(
            ffmpeg_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"\nFailed to process {video_path.name}. Check FFmpeg command. Error: {e}", err=True)
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
    help="The BASE directory where the output folder will be created."
)
@click.option('--width', type=int, default=480, show_default=True, help="Target width for resizing.")
@click.option('--height', type=int, default=832, show_default=True, help="Target height for resizing.")
@click.option('--fps', type=int, default=16, show_default=True, help="Target frames per second.")
# --- CHANGE: Added chunk_length option ---
@click.option(
    '--chunk-length', '-l',
    type=int,
    default=5,
    show_default=True,
    help="The maximum length of each video chunk in seconds."
)
def batch_process_cli(
    input_dir: Path, 
    output_dir: Path, 
    width: int, 
    height: int, 
    fps: int, 
    chunk_length: int
):
    """
    A tool to batch process videos with custom resolution, FPS, and precise chunk length.
    """
    # --- CHANGE: Directory name now includes chunk length ---
    final_output_dir = output_dir / f"clips_{width}x{height}_{fps}fps_{chunk_length}s"
    final_output_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Output will be saved in: {final_output_dir}")

    video_files = list(input_dir.glob("*.mp4"))
    if not video_files:
        click.echo(f"No .mp4 videos found in '{input_dir}'.")
        return

    click.echo(f"Found {len(video_files)} videos to process. Starting...")

    # --- CHANGE: Pass chunk_length to the processing tasks ---
    tasks = [(video_path, final_output_dir, width, height, fps, chunk_length) for video_path in video_files]

    with multiprocessing.Pool() as pool:
        with tqdm(total=len(tasks), desc="Processing Videos") as pbar:
            for _ in pool.starmap(process_video, tasks):
                pbar.update()

    click.echo("\n🎉 Batch processing complete!")
    click.echo(f"All processed videos are saved in: {final_output_dir}")

if __name__ == '__main__':
    batch_process_cli()