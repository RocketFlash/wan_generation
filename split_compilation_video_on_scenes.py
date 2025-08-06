import subprocess
import multiprocessing
import click
from pathlib import Path
from scenedetect import detect, ContentDetector, split_video_ffmpeg

def split_video_with_ffmpeg(input_video_path: Path, output_folder: Path) -> list[Path]:
    """Splits the input video into three horizontal parts using FFmpeg."""
    output_folder.mkdir(parents=True, exist_ok=True)
    ffprobe_cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'csv=p=0', str(input_video_path)
    ]
    try:
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split(','))
        third_width = width // 3
    except (subprocess.CalledProcessError, ValueError) as e:
        click.echo(f"Error getting video dimensions: {e}", err=True)
        return []

    click.echo("Splitting video into three parts using FFmpeg...")
    split_video_paths = [
        output_folder / "part1.mp4",
        output_folder / "part2.mp4",
        output_folder / "part3.mp4",
    ]

    ffmpeg_commands = [
        ['ffmpeg', '-y', '-i', str(input_video_path), '-vf', f'crop={third_width}:{height}:0:0', '-c:v', 'h264_videotoolbox', '-q:v', '50', str(split_video_paths[0])],
        ['ffmpeg', '-y', '-i', str(input_video_path), '-vf', f'crop={third_width}:{height}:{third_width}:0', '-c:v', 'h264_videotoolbox', '-q:v', '50', str(split_video_paths[1])],
        ['ffmpeg', '-y', '-i', str(input_video_path), '-vf', f'crop={third_width}:{height}:{2 * third_width}:0', '-c:v', 'h264_videotoolbox', '-q:v', '50', str(split_video_paths[2])]
    ]
    for cmd in ffmpeg_commands:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    click.echo("✅ Video splitting complete.")
    return split_video_paths

def detect_scenes_for_part(video_path: Path, part_num: int, output_folder: Path):
    """Performs scene detection for a single video part."""
    scenes_folder = output_folder / f"part{part_num}_scenes"
    scenes_folder.mkdir(exist_ok=True)
    click.echo(f"▶️  Starting scene detection for part {part_num}...")
    video_path_str = str(video_path)
    output_template = str(scenes_folder / 'scene-$SCENE_NUMBER.mp4')
    scene_list = detect(video_path_str, ContentDetector())
    if not scene_list:
        click.echo(f"⚠️  No scenes detected in {video_path.name}.")
        return
    split_video_ffmpeg(video_path_str, scene_list, output_file_template=output_template, suppress_output=True)
    click.echo(f"✅ Finished processing scenes for part {part_num}.")

def consolidate_scenes(output_dir: Path, cleanup: bool):
    """
    Consolidates all generated scenes into a single folder and optionally cleans up.
    """
    final_scenes_dir = output_dir / "all_scenes"
    final_scenes_dir.mkdir(exist_ok=True)
    click.echo("\n consolidating all scenes into a single folder...")

    scene_count = 0
    scene_dirs = sorted([p for p in output_dir.iterdir() if p.is_dir() and p.name.endswith('_scenes')])

    for scene_dir in scene_dirs:
        part_prefix = scene_dir.name.replace('_scenes', '')
        for scene_file in sorted(scene_dir.glob("*.mp4")):
            # Create a new unique name to avoid collisions, e.g., "part1-scene-001.mp4"
            new_name = f"{part_prefix}-{scene_file.name}"
            new_path = final_scenes_dir / new_name
            scene_file.rename(new_path) # Move file to the new directory with a new name
            scene_count += 1
    
    click.echo(f"✅ Moved {scene_count} scenes to '{final_scenes_dir}'.")

    if cleanup:
        click.echo("Cleaning up intermediate files...")
        for scene_dir in scene_dirs:
            try:
                # Remove the now-empty 'partX_scenes' directory
                scene_dir.rmdir()
            except OSError as e:
                click.echo(f"Could not remove {scene_dir}: {e}", err=True)

        for part_file in output_dir.glob("part*.mp4"):
            # Remove the intermediate 'partX.mp4' file
            part_file.unlink()
        click.echo("✅ Cleanup complete.")

@click.command()
@click.option('--input-video', type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, path_type=Path), required=True, help="Path to the horizontally concatenated input video.")
@click.option('--output-dir', type=click.Path(file_okay=False, path_type=Path), required=True, help="Directory to save the output.")
@click.option('--cleanup/--no-cleanup', default=True, help="Remove intermediate files (e.g., partX.mp4) after completion.")
def process_video_cli(input_video: Path, output_dir: Path, cleanup: bool):
    # """
    # A tool to split a concatenated video, detect scenes in parallel, and
    # consolidate the results into a single folder.
    # """
    # split_video_paths = split_video_with_ffmpeg(input_video, output_dir)
    # if not split_video_paths:
    #     click.echo("Could not split video. Exiting.", err=True)
    #     return

    # processes = []
    # for i, video_path in enumerate(split_video_paths):
    #     process = multiprocessing.Process(target=detect_scenes_for_part, args=(video_path, i + 1, output_dir))
    #     processes.append(process)
    #     process.start()

    # for process in processes:
    #     process.join()

    # --- NEW STEP: Consolidate all scenes ---
    consolidate_scenes(output_dir, cleanup)

    click.echo("\n🎉 All tasks completed successfully!")
    click.echo(f"Final scenes are located in: {output_dir / 'all_scenes'}")

if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)
    process_video_cli()