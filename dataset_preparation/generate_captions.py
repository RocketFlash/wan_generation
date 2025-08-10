import os
import click
import torch
from transformers import (
    Qwen2_5_VLForConditionalGeneration, 
    AutoProcessor
)
from tqdm import tqdm
from qwen_vl_utils import process_vision_info


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
# MODEL_ID = "thesby/Qwen2.5-VL-7B-NSFW-Caption-V3"

MODEL_ID = "Ertugrul/Qwen2.5-VL-7B-Captioner-Relaxed"
# MODEL_ID = "huihui-ai/Qwen2.5-VL-7B-Instruct-abliterated"

print("Loading model and tokenizer...")
processor = AutoProcessor.from_pretrained(
    MODEL_ID, 
    trust_remote_code=True
)

model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    MODEL_ID, 
    torch_dtype="auto", 
    device_map="auto",
    low_cpu_mem_usage=True,
    trust_remote_code=True,
    attn_implementation="flash_attention_2"
).eval()
print("Model and tokenizer loaded successfully.")

PROMPT_TEMPLATE = f"""
You are an expert video analyst. Your task is to create a single, concise, and descriptive paragraph for a 5-second video clip. 
The entire response must not exceed {{max_tokens}} tokens. The caption must start with the exact word: "{{trigger_word}}".

**Video Context:**
The video is a short, first-person point of view (POV) clip.

**Analysis and Captioning Instructions:**
Analyze the provided video and generate a single, coherent, and brief paragraph. 
The paragraph must begin with "{{trigger_word}}" and concisely integrate the following points:

1.  **The Woman's Appearance:** Briefly describe her most prominent features (e.g., hair, face).
2.  **Her Emotional State & Gaze:** Describe her facial expression and where she is looking.
3.  **The Environment & Lighting:** Briefly describe the room and the style of lighting.

**Constraint Checklist:**
- **Start word:** Must begin with "{{trigger_word}}".
- **Token Limit:** The entire output must be under {{max_tokens}} tokens.
- **Format:** A single, well-written paragraph.

Generate the caption now.
"""


def generate_caption_for_video(
    video_path: str, 
    trigger_word: str,
    fps: int,
    max_tokens: int
) -> str:
    """
    Generates a caption for a single video file using the Qwen2.5-VL model.

    Args:
        video_path: The absolute path to the video file.
        trigger_word: The action trigger word to include in the caption.

    Returns:
        The generated caption as a string.
    """
    try:
        # Create the detailed prompt for the model
        prompt_text = PROMPT_TEMPLATE.format(
            trigger_word=trigger_word,
            max_tokens=max_tokens
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "video",
                        "video": f"file://{video_path}",
                        "fps": fps,
                    },
                    {"type": "text", "text": prompt_text},
                ],
            }
        ]

        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs, video_kwargs = process_vision_info(messages, return_video_kwargs=True)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
            **video_kwargs,
        )
        inputs = inputs.to("cuda")

        # Inference
        generated_ids = model.generate(**inputs, max_new_tokens=max_tokens)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )

        return output_text[0].strip() if output_text else "Failed to generate caption."

    except Exception as e:
        return f"An error occurred during caption generation: {e}"


@click.command()
@click.option(
    '--input-folder',
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help='The folder containing MP4 videos to process.'
)
@click.option(
    '--trigger-word',
    required=True,
    type=str,
    help='The action trigger word to insert into captions.'
)
@click.option(
    '--fps',
    required=True,
    default=1,
    type=int,
    help='processing fps'
)
@click.option(
    '--max_tokens',
    required=True,
    default=256,
    type=int,
    help='maximum number of tokens in output caption'
)
def main(
    input_folder: str, 
    trigger_word: str,
    fps: int,
    max_tokens: int
):
    """
    A script to generate captions for all MP4 videos in a folder using the
    Qwen2.5-VL-7B model, including a specific trigger word for I2V finetuning.
    """
    click.echo(f"Starting video processing in: {input_folder}")
    click.echo(f"Using action trigger word: '{trigger_word}'")

    # Iterate over all files in the specified directory
    for filename in tqdm(os.listdir(input_folder)):
        if filename.lower().endswith(".mp4"):
            video_path = os.path.join(input_folder, filename)
            absolute_video_path = os.path.abspath(video_path)
            click.echo(f"Processing video: {filename}...")

            # Generate the caption for the video
            caption = generate_caption_for_video(
                absolute_video_path, 
                trigger_word,
                fps=fps,
                max_tokens=max_tokens
            )

            # Create the corresponding .txt filename and path
            base_filename = os.path.splitext(filename)[0]
            caption_filename = f"{base_filename}.txt"
            caption_filepath = os.path.join(input_folder, caption_filename)

            # Save the generated caption to the text file
            try:
                with open(caption_filepath, "w", encoding="utf-8") as f:
                    f.write(caption)
                click.echo(f"  -> Saved caption to: {caption_filename}")
            except IOError as e:
                click.echo(f"  -> Error saving caption file: {e}", err=True)

    click.echo("Processing complete.")


if __name__ == "__main__":
    main()