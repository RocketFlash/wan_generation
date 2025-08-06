import click
from pathlib import Path
import shutil
from collections import defaultdict
import cv2
import numpy as np
from tqdm import tqdm

def analyze_clip(video_path: Path) -> float:
    """
    Analyzes a video clip and returns a quality score based on motion and clarity.

    Args:
        video_path: Path to the video clip.

    Returns:
        A float representing the quality score of the clip.
    """
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return 0.0

        # Read the first frame
        ret, prev_frame = cap.read()
        if not ret:
            cap.release()
            return 0.0
        
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        
        total_flow = 0
        total_laplacian = 0
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 1. Calculate Motion Score using Farneback Optical Flow
            flow = cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            total_flow += np.mean(magnitude)

            # 2. Calculate Clarity Score using Laplacian Variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            total_laplacian += laplacian_var
            
            prev_gray = gray
            frame_count += 1

        cap.release()

        if frame_count == 0:
            return 0.0

        # Calculate average scores
        avg_flow = total_flow / frame_count
        avg_laplacian = total_laplacian / frame_count

        # Combine scores. We normalize laplacian to prevent it from overpowering flow.
        # These weights can be tuned, but this is a good starting point.
        final_score = avg_flow * (1 + np.log1p(avg_laplacian))
        return final_score

    except Exception:
        return 0.0

@click.command()
@click.option('--input-dir', type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path), required=True, help="Directory with all processed video chunks.")
@click.option('--output-dir', type=click.Path(file_okay=False, writable=True, path_type=Path), required=True, help="Directory to save the selected training clips.")
@click.option('--num-clips', '-n', type=int, default=1, show_default=True, help="The number of clips to select per original source video.")
def select_best_clips_cli(input_dir: Path, output_dir: Path, num_clips: int):
    """
    Analyzes all video clips for motion and clarity, then selects the BEST N clips
    from each original source for I2V LoRA training.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Searching for video clips in: {input_dir}")

    grouped_clips = defaultdict(list)
    video_files = list(input_dir.glob("*.mp4"))
    if not video_files:
        click.echo("No .mp4 files found.", err=True); return

    for clip_path in video_files:
        base_name = clip_path.stem.rsplit('-chunk-', 1)[0]
        grouped_clips[base_name].append(clip_path)

    click.echo(f"Found {len(video_files)} clips from {len(grouped_clips)} unique sources.")
    click.echo("Analyzing clips to find the best ones... (This may take a while)")

    selected_files = []
    # Using tqdm for a progress bar over the groups
    for base_name, clips_list in tqdm(grouped_clips.items(), desc="Analyzing Sources"):
        clip_scores = []
        for clip_path in clips_list:
            score = analyze_clip(clip_path)
            if score > 0:
                clip_scores.append((score, clip_path))
        
        # Sort the clips for this source by score in descending order
        clip_scores.sort(key=lambda x: x[0], reverse=True)
        
        # Select the top N clips
        best_clips = clip_scores[:num_clips]
        for score, path in best_clips:
            selected_files.append(path)

    click.echo(f"\nAnalysis complete. Total clips selected for training: {len(selected_files)}")

    for f in tqdm(selected_files, desc="Copying Best Clips"):
        shutil.copy(f, output_dir)
    
    click.echo(f"✅ Successfully copied the best clips to: {output_dir}")


if __name__ == '__main__':
    select_best_clips_cli()