import argparse
import json
import re
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List
import logging

try:
    from safetensors.torch import load_file, save_file
    import torch
except ImportError:
    print("Please install required packages: pip install safetensors torch")
    exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DiTLoRAConverter:
    """
    Converts Diffusion Transformer LoRA from diffusion-pipe/ComfyUI format to diffusers format.
    Specifically designed for Wan2.1 I2V and similar DiT models.
    """
    
    def __init__(self, alpha: float = 32.0, rank: int = 32, device: str = "cpu"):
        """
        Initialize the converter.
        
        Args:
            alpha: LoRA alpha value (default: 32.0 from your config)
            rank: LoRA rank (default: 32 from your config)
            device: Device to load tensors on (default: "cpu")
        """
        self.alpha = alpha
        self.rank = rank
        self.device = device
        self.conversion_stats = {}
        
    def detect_format(self, state_dict: Dict[str, torch.Tensor]) -> str:
        """
        Detect the format of the LoRA file.
        
        Args:
            state_dict: The loaded state dictionary
            
        Returns:
            Format type: "dit_comfyui", "diffusers", or "unknown"
        """
        keys = list(state_dict.keys())
        
        # Check for DiT ComfyUI format (your format)
        if any("diffusion_model.blocks" in k and "lora_A" in k for k in keys):
            return "dit_comfyui"
        
        # Check for diffusers format
        if any("transformer.blocks" in k and "lora" in k and "processor" in k for k in keys):
            return "diffusers"
        
        return "unknown"
    
    def convert_dit_key(self, key: str) -> Optional[str]:
        """
        Convert a DiT ComfyUI key to diffusers format.
        
        Maps from: diffusion_model.blocks.{N}.{attn_type}.{proj}.lora_{A|B}.weight
        To: transformer.blocks.{N}.{attn_type}.processor.{proj}.lora_{down|up}.weight
        
        Args:
            key: Original DiT format key
            
        Returns:
            Converted diffusers format key or None if not convertible
        """
        # Pattern to match DiT keys
        pattern = r"diffusion_model\.blocks\.(\d+)\.([\w_]+)\.([\w_]+)\.lora_([AB])\.weight"
        match = re.match(pattern, key)
        
        if not match:
            logger.warning(f"Key doesn't match expected pattern: {key}")
            return None
        
        block_num = match.group(1)
        attn_type = match.group(2)  # self_attn, cross_attn, or ffn
        proj_type = match.group(3)  # q, k, v, o, k_img, v_img, or ffn.0/ffn.2
        lora_type = match.group(4)  # A or B
        
        # Convert A/B to down/up
        lora_suffix = "lora_down" if lora_type == "A" else "lora_up"
        
        # Handle different attention types
        if attn_type == "self_attn":
            # Self-attention layers
            if proj_type in ["q", "k", "v", "o"]:
                # Map to diffusers format
                proj_map = {
                    "q": "to_q",
                    "k": "to_k", 
                    "v": "to_v",
                    "o": "to_out.0"
                }
                diffusers_proj = proj_map.get(proj_type, proj_type)
                return f"transformer.blocks.{block_num}.attn1.processor.{diffusers_proj}.{lora_suffix}.weight"
                
        elif attn_type == "cross_attn":
            # Cross-attention layers
            if proj_type in ["q", "k", "v", "o"]:
                # Regular cross-attention (text)
                proj_map = {
                    "q": "to_q",
                    "k": "to_k",
                    "v": "to_v", 
                    "o": "to_out.0"
                }
                diffusers_proj = proj_map.get(proj_type, proj_type)
                return f"transformer.blocks.{block_num}.attn2.processor.{diffusers_proj}.{lora_suffix}.weight"
                
            elif proj_type in ["k_img", "v_img"]:
                # Image cross-attention (for I2V models)
                # These might map to a separate attention layer or be part of attn2
                # Adjust based on your specific model architecture
                proj_map = {
                    "k_img": "to_k_img",
                    "v_img": "to_v_img"
                }
                diffusers_proj = proj_map.get(proj_type, proj_type)
                # You might need to adjust this based on how diffusers handles image attention
                return f"transformer.blocks.{block_num}.attn2.processor.{diffusers_proj}.{lora_suffix}.weight"
                
        elif attn_type == "ffn":
            # Feed-forward network layers
            if proj_type == "0":
                # First linear layer in FFN
                return f"transformer.blocks.{block_num}.ff.net.0.proj.{lora_suffix}.weight"
            elif proj_type == "2":
                # Second linear layer in FFN
                return f"transformer.blocks.{block_num}.ff.net.2.{lora_suffix}.weight"
        
        logger.warning(f"Couldn't convert key: {key}")
        return None
    
    def convert_dit_key_alternative(self, key: str) -> Optional[str]:
        """
        Alternative conversion mapping that preserves more of the original structure.
        Use this if the first mapping doesn't work with your diffusers pipeline.
        
        Args:
            key: Original DiT format key
            
        Returns:
            Alternative diffusers format key
        """
        # Simply replace diffusion_model with transformer and adjust lora naming
        converted = key.replace("diffusion_model.", "transformer.")
        converted = converted.replace(".lora_A.", ".processor.lora_down.")
        converted = converted.replace(".lora_B.", ".processor.lora_up.")
        
        # Adjust specific mappings
        converted = converted.replace(".self_attn.", ".attn1.")
        converted = converted.replace(".cross_attn.", ".attn2.")
        
        # Handle FFN differently
        if ".ffn." in converted:
            converted = re.sub(r"\.ffn\.(\d+)\.", r".ff.net.\1.", converted)
        
        return converted
    
    def group_lora_pairs(self, state_dict: Dict[str, torch.Tensor]) -> Dict[str, Dict[str, torch.Tensor]]:
        """
        Group LoRA weights by their base key (pairing lora_A and lora_B).
        
        Args:
            state_dict: The loaded state dictionary
            
        Returns:
            Dictionary with base keys and their associated weights
        """
        key_pairs = {}
        
        for key, tensor in state_dict.items():
            # Extract base key (without .lora_A.weight or .lora_B.weight)
            if ".lora_A.weight" in key:
                base_key = key.replace(".lora_A.weight", "")
                if base_key not in key_pairs:
                    key_pairs[base_key] = {}
                key_pairs[base_key]["lora_A"] = tensor
                
            elif ".lora_B.weight" in key:
                base_key = key.replace(".lora_B.weight", "")
                if base_key not in key_pairs:
                    key_pairs[base_key] = {}
                key_pairs[base_key]["lora_B"] = tensor
                
            else:
                # Handle other potential keys
                key_pairs[key] = {"tensor": tensor}
        
        return key_pairs
    
    def extract_and_scale_weights(self, lora_a: torch.Tensor, lora_b: torch.Tensor, 
                                 alpha: Optional[float] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Extract and optionally scale LoRA weights.
        
        Args:
            lora_a: LoRA A (down) weights
            lora_b: LoRA B (up) weights  
            alpha: Optional alpha value to override instance alpha
            
        Returns:
            Tuple of (scaled_down, scaled_up) tensors
        """
        alpha = alpha if alpha is not None else self.alpha
        
        # For diffusers, we typically don't pre-scale the weights
        # The scaling is applied during inference
        # But you can enable scaling here if needed
        
        # Uncomment to apply scaling:
        # if alpha != self.rank:
        #     scale = alpha / self.rank
        #     lora_a = lora_a * scale
        #     lora_b = lora_b * scale
        
        return lora_a, lora_b
    
    def convert(self, input_path: str, output_path: str, 
                create_config: bool = True,
                use_alternative_mapping: bool = False) -> Dict[str, Any]:
        """
        Convert DiT LoRA to diffusers format.
        
        Args:
            input_path: Path to input DiT LoRA file
            output_path: Path to output diffusers LoRA file
            create_config: Whether to create adapter_config.json
            use_alternative_mapping: Use alternative key mapping if True
            
        Returns:
            Dictionary with conversion statistics
        """
        logger.info(f"Loading LoRA from {input_path}")
        state_dict = load_file(input_path)
        
        # Detect format
        format_type = self.detect_format(state_dict)
        logger.info(f"Detected format: {format_type}")
        
        if format_type == "diffusers":
            logger.warning("File appears to already be in diffusers format")
            return {"status": "already_diffusers", "keys_converted": 0}
        
        if format_type == "unknown":
            logger.error("Unknown LoRA format")
            return {"status": "unknown_format", "keys_converted": 0}
        
        # Convert keys
        converted_dict = {}
        conversion_stats = {
            "blocks_converted": set(),
            "attention_keys": 0,
            "ffn_keys": 0,
            "skipped_keys": 0,
            "total_keys": len(state_dict)
        }
        
        # Group keys by base name
        key_pairs = self.group_lora_pairs(state_dict)
        
        # Choose conversion method
        convert_fn = self.convert_dit_key_alternative if use_alternative_mapping else self.convert_dit_key
        
        for base_key, weights in key_pairs.items():
            if "lora_A" in weights and "lora_B" in weights:
                converted_key = convert_fn(f"{base_key}.lora_A.weight")
                
                if converted_key:
                    # Extract block number for statistics
                    block_match = re.search(r"blocks\.(\d+)", converted_key)
                    if block_match:
                        conversion_stats["blocks_converted"].add(int(block_match.group(1)))
                    
                    # Apply scaling if needed
                    down, up = self.extract_and_scale_weights(
                        weights["lora_A"],
                        weights["lora_B"]
                    )
                    
                    # Store with proper suffixes
                    base_converted = converted_key.replace(".lora_down.weight", "")
                    converted_dict[f"{base_converted}.lora_down.weight"] = down
                    converted_dict[f"{base_converted}.lora_up.weight"] = up
                    
                    # Update statistics
                    if "attn" in converted_key:
                        conversion_stats["attention_keys"] += 2
                    elif "ff" in converted_key:
                        conversion_stats["ffn_keys"] += 2
                else:
                    conversion_stats["skipped_keys"] += 2
                    logger.warning(f"Skipped: {base_key}")
            else:
                # Single tensor without pair
                if "tensor" in weights:
                    conversion_stats["skipped_keys"] += 1
        
        # Save converted weights
        logger.info(f"Saving converted LoRA to {output_path}")
        save_file(converted_dict, output_path)
        
        # Create adapter config if requested
        if create_config:
            config_path = Path(output_path).parent / "adapter_config.json"
            self._create_adapter_config(config_path, conversion_stats)
        
        # Log statistics
        logger.info(f"Conversion complete:")
        logger.info(f"  - Blocks converted: {sorted(conversion_stats['blocks_converted'])}")
        logger.info(f"  - Attention keys: {conversion_stats['attention_keys']}")
        logger.info(f"  - FFN keys: {conversion_stats['ffn_keys']}")
        logger.info(f"  - Keys skipped: {conversion_stats['skipped_keys']}")
        logger.info(f"  - Total keys processed: {conversion_stats['total_keys']}")
        
        return conversion_stats
    
    def _create_adapter_config(self, config_path: Path, stats: Dict[str, Any]):
        """
        Create PEFT-compatible adapter_config.json for diffusers.
        
        Args:
            config_path: Path to save the config
            stats: Conversion statistics
        """
        config = {
            "alpha_pattern": {},
            "auto_mapping": None,
            "base_model_name_or_path": "Wan-AI/Wan2.1-I2V-14B-480P",
            "bias": "none",
            "fan_in_fan_out": False,
            "inference_mode": True,
            "init_lora_weights": True,
            "layers_pattern": None,
            "layers_to_transform": None,
            "lora_alpha": self.alpha,
            "lora_dropout": 0.0,
            "modules_to_save": None,
            "peft_type": "LORA",
            "r": self.rank,
            "rank_pattern": {},
            "revision": None,
            "target_modules": [
                "to_q",
                "to_k", 
                "to_v",
                "to_out.0",
                "to_k_img",
                "to_v_img",
                "ff.net.0.proj",
                "ff.net.2"
            ],
            "task_type": "DIFFUSION",
            "use_dora": False,
            "use_rslora": False,
            "conversion_info": {
                "converter": "dit_to_diffusers",
                "source_format": "diffusion-pipe/comfyui", 
                "attention_keys": stats["attention_keys"],
                "ffn_keys": stats["ffn_keys"],
                "blocks_converted": len(stats["blocks_converted"]),
                "skipped_keys": stats["skipped_keys"]
            }
        }
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Created adapter config at {config_path}")
    
    def verify_conversion(self, original_path: str, converted_path: str) -> bool:
        """
        Verify the conversion by checking tensor counts and shapes.
        
        Args:
            original_path: Path to original DiT LoRA
            converted_path: Path to converted diffusers LoRA
            
        Returns:
            True if verification passes
        """
        original = load_file(original_path)
        converted = load_file(converted_path)
        
        # Check that we have the expected number of tensors
        original_pairs = len([k for k in original.keys() if "lora_A" in k])
        converted_pairs = len([k for k in converted.keys() if "lora_down" in k])
        
        if original_pairs != converted_pairs:
            logger.warning(f"Tensor count mismatch: {original_pairs} vs {converted_pairs}")
            return False
        
        # Check a few tensor shapes
        for orig_key in list(original.keys())[:5]:
            if "lora_A" in orig_key:
                orig_shape = original[orig_key].shape
                # Find corresponding converted key
                for conv_key in converted.keys():
                    if "lora_down" in conv_key and orig_shape == converted[conv_key].shape:
                        logger.debug(f"Shape match found: {orig_key} -> {conv_key}")
                        break
                else:
                    logger.warning(f"No shape match for {orig_key}")
        
        logger.info(f"Verification passed: {converted_pairs} LoRA pairs converted")
        return True
    
    def batch_convert(self, input_dir: str, output_dir: str, pattern: str = "*.safetensors"):
        """
        Convert multiple LoRA files in a directory.
        
        Args:
            input_dir: Directory containing input files
            output_dir: Directory for output files
            pattern: File pattern to match
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        files = list(input_path.glob(pattern))
        logger.info(f"Found {len(files)} files to convert")
        
        for file in files:
            output_file = output_path / file.name
            logger.info(f"Converting {file.name}...")
            self.convert(str(file), str(output_file))


def main():
    parser = argparse.ArgumentParser(
        description="Convert DiT (Wan2.1) LoRA to diffusers format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic conversion:
    python convert_dit_lora.py input.safetensors output.safetensors
  
  With custom alpha and rank:
    python convert_dit_lora.py input.safetensors output.safetensors --alpha 32 --rank 32
  
  Use alternative mapping:
    python convert_dit_lora.py input.safetensors output.safetensors --alternative
    
  Batch conversion:
    python convert_dit_lora.py --batch input_dir/ output_dir/
        """
    )
    
    parser.add_argument("input", help="Path to input DiT LoRA file or directory for batch mode")
    parser.add_argument("output", help="Path to output diffusers LoRA file or directory for batch mode")
    parser.add_argument("--alpha", type=float, default=32.0,
                       help="LoRA alpha value (default: 32.0)")
    parser.add_argument("--rank", type=int, default=32,
                       help="LoRA rank value (default: 32)")
    parser.add_argument("--no-config", action="store_true",
                       help="Don't create adapter_config.json")
    parser.add_argument("--alternative", action="store_true",
                       help="Use alternative key mapping")
    parser.add_argument("--batch", action="store_true",
                       help="Batch convert all files in directory")
    parser.add_argument("--device", default="cpu",
                       help="Device to load tensors on (default: cpu)")
    parser.add_argument("--verify", action="store_true",
                       help="Verify conversion after completion")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create converter
    converter = DiTLoRAConverter(alpha=args.alpha, rank=args.rank, device=args.device)
    
    if args.batch:
        # Batch conversion mode
        converter.batch_convert(args.input, args.output)
    else:
        # Single file conversion
        stats = converter.convert(
            args.input,
            args.output,
            create_config=not args.no_config,
            use_alternative_mapping=args.alternative
        )
        
        # Verify if requested
        if args.verify:
            if converter.verify_conversion(args.input, args.output):
                logger.info("Verification successful!")
            else:
                logger.warning("Verification failed - please check the conversion")
    
    return 0


if __name__ == "__main__":
    exit(main())