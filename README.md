
For ease of working with the code, it is best to install the conda environment using the following command:

```bash
conda env create -f environment.yml
conda activate diffusion-pipe
```

You can download all necessary models using

```bash
bash download_models.sh
```

# Data preparation

You can read how to run data preparation [here](DATA_PREPARATION.md) scripts or you can just run 
```bash
bash dataset_preparation/prepare_dataset.sh --input-video {INPUT_VIDEO} --output-dir {OUTPUT_DIR} [OPTIONS]
```
You will find the data prepared for training in the folder {OUTPUT_DIR}/final_dataset

# LoRA Training
Set correct path in [dataset.toml](wan2.1_i2v_lora_training_config/dataset.toml)

```
[[directory]]
path = "your/dataset/path/is/here"
```

Set correct path to **dataset.toml** config and output save directory in [wan.toml](wan2.1_i2v_lora_training_config/wan.toml) and path to base model checkpoint.

```
output_dir = '/save/path/is/here'
dataset = '/path/to/your/dataset.toml'
...
ckpt_path = '/path/to/model/checkpoint' # path to original model directory path https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-480P
```

Clone diffusion-pipe
```bash
git clone --recurse-submodules https://github.com/tdrussell/diffusion-pipe && cd diffusion-pipe
```

Run training 

```bash
NCCL_P2P_DISABLE="1" NCCL_IB_DISABLE="1" deepspeed --num_gpus={NUMBER_OF_GPUS} train.py --deepspeed --config ../wan2.1_i2v_lora_training_config/wan.toml
```

# Inference
You can test LoRA in ComfyUI using workflow from *workflow* directory

[Here](INFERENCE.md) you can read how to use trained LoRA model using REST API wrapper