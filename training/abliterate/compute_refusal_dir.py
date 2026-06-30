"""Compute refusal direction for Qwen models.
Adapted from Sumandora/remove-refusals-with-transformers for Qwen architecture.

Usage: python compute_refusal_dir.py --model Qwen/Qwen3.6-35B-A3B-AWQ
"""

import argparse
import random
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from tqdm import tqdm

torch.inference_mode()


def get_layers(model):
    """Qwen stores layers at model.transformer.h instead of model.model.layers."""
    if hasattr(model, "model") and hasattr(model.model, "layers"):
        return model.model.layers
    elif hasattr(model, "transformer") and hasattr(model.transformer, "h"):
        return model.transformer.h
    elif hasattr(model, "model") and hasattr(model.model, "h"):
        return model.model.h
    raise AttributeError("Could not find model layers. Known paths: model.model.layers, model.transformer.h, model.model.h")


def main():
    parser = argparse.ArgumentParser(description="Compute refusal direction for Qwen models")
    parser.add_argument("--model", default="Qwen/Qwen3.6-35B-A3B-AWQ",
                        help="HuggingFace model ID")
    parser.add_argument("--instructions", type=int, default=64,
                        help="Number of harmful/harmless instruction pairs")
    parser.add_argument("--layer-ratio", type=float, default=0.6,
                        help="Which layer to extract from (0.0-1.0)")
    parser.add_argument("--pos", type=int, default=-1,
                        help="Position index in the residual stream (-1 = last token)")
    parser.add_argument("--harmful", default="harmful.txt",
                        help="Path to harmful instructions file")
    parser.add_argument("--harmless", default="harmless.txt",
                        help="Path to harmless instructions file")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading {args.model} on {device}...")

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        trust_remote_code=True,
        dtype=torch.float16,
        device_map="cuda",
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        ),
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)

    layers = get_layers(model)
    layer_idx = int(len(layers) * args.layer_ratio)
    pos = args.pos

    print(f"Total layers: {len(layers)}")
    print(f"Using layer: {layer_idx} (index {layer_idx})")
    print(f"Position: {pos}")
    print(f"Instructions per set: {args.instructions}")

    with open(args.harmful, "r") as f:
        harmful = [l.strip() for l in f if l.strip()]
    with open(args.harmless, "r") as f:
        harmless = [l.strip() for l in f if l.strip()]

    harmful_sample = random.sample(harmful, min(args.instructions, len(harmful)))
    harmless_sample = random.sample(harmless, min(args.instructions, len(harmless)))

    def tokenize_instructions(instructions):
        return [
            tokenizer.apply_chat_template(
                conversation=[{"role": "user", "content": insn}],
                add_generation_prompt=True,
                return_tensors="pt",
            )
            for insn in instructions
        ]

    harmful_toks = tokenize_instructions(harmful_sample)
    harmless_toks = tokenize_instructions(harmless_sample)

    max_its = len(harmful_toks) + len(harmless_toks)

    def generate(toks):
        return model.generate(
            toks.to(model.device),
            use_cache=False,
            max_new_tokens=1,
            return_dict_in_generate=True,
            output_hidden_states=True,
        )

    bar = tqdm(total=max_its, desc="Generating")
    harmful_outputs = []
    for toks in harmful_toks:
        harmful_outputs.append(generate(toks))
        bar.update(1)
    harmless_outputs = []
    for toks in harmless_toks:
        harmless_outputs.append(generate(toks))
        bar.update(1)
    bar.close()

    harmful_hidden = [
        output.hidden_states[0][layer_idx][:, pos, :]
        for output in harmful_outputs
    ]
    harmless_hidden = [
        output.hidden_states[0][layer_idx][:, pos, :]
        for output in harmless_outputs
    ]

    harmful_mean = torch.stack(harmful_hidden).mean(dim=0)
    harmless_mean = torch.stack(harmless_hidden).mean(dim=0)

    refusal_dir = harmful_mean - harmless_mean
    refusal_dir = refusal_dir / refusal_dir.norm()

    print(f"Refusal direction shape: {refusal_dir.shape}")
    print(f"Refusal direction norm: {refusal_dir.norm().item()}")

    safe_name = args.model.replace("/", "_")
    out_path = f"{safe_name}_refusal_dir.pt"
    torch.save(refusal_dir, out_path)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
