"""Ablated inference — removes refusal direction during generation.
Adapted from Sumandora/remove-refusals-with-transformers for Qwen.

Usage: python ablated_inference.py --model Qwen/Qwen3.6-35B-A3B-AWQ
"""

import argparse
import einops
import torch
import torch.nn as nn
from typing import Optional, Tuple
from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer, BitsAndBytesConfig

torch.inference_mode()


def get_layers(model):
    if hasattr(model, "model") and hasattr(model.model, "layers"):
        return model.model.layers
    elif hasattr(model, "transformer") and hasattr(model.transformer, "h"):
        return model.transformer.h
    elif hasattr(model, "model") and hasattr(model.model, "h"):
        return model.model.h
    raise AttributeError("Could not find model layers")


def direction_ablation_hook(activation, direction):
    proj = einops.einsum(
        activation, direction.view(-1, 1),
        "... d_act, d_act single -> ... single"
    ) * direction
    return activation - proj


class AblationDecoderLayer(nn.Module):
    """Wrapper layer that ablates refusal direction from hidden states."""

    def __init__(self):
        super().__init__()

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        position_ids: Optional[torch.LongTensor] = None,
        past_key_value: Optional[Tuple[torch.Tensor]] = None,
        output_attentions: Optional[bool] = False,
        use_cache: Optional[bool] = False,
        cache_position: Optional[torch.LongTensor] = None,
        **kwargs,
    ):
        assert not output_attentions
        ablated = direction_ablation_hook(
            hidden_states, self.refusal_dir.to(hidden_states.device)
        ).to(hidden_states.device)

        if hasattr(self, "_simple_return"):
            return ablated

        outputs = (ablated,)
        if use_cache:
            outputs += (past_key_value,)
        return outputs


def main():
    parser = argparse.ArgumentParser(description="Ablated inference for Qwen models")
    parser.add_argument("--model", default="Qwen/Qwen3.6-35B-A3B-AWQ",
                        help="HuggingFace model ID (must match compute_refusal_dir.py)")
    parser.add_argument("--refusal-dir", default=None,
                        help="Path to refusal_dir.pt (default: auto-detect)")
    parser.add_argument("--max-tokens", type=int, default=2048,
                        help="Maximum new tokens per response")
    args = parser.parse_args()

    if args.refusal_dir is None:
        args.refusal_dir = args.model.replace("/", "_") + "_refusal_dir.pt"

    print(f"Loading refusal direction from {args.refusal_dir}...")
    refusal_dir = torch.load(args.refusal_dir)
    print(f"Refusal direction loaded. Shape: {refusal_dir.shape}")

    print(f"Loading {args.model}...")
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
    print(f"Found {len(layers)} layers")

    # Inject ablation layer at each position
    ablation_layer = AblationDecoderLayer()
    ablation_layer.refusal_dir = refusal_dir

    for idx in reversed(range(len(layers))):
        layers.insert(idx, ablation_layer)

    # Update layer count if model has it
    if hasattr(model, "config") and hasattr(model.config, "num_hidden_layers"):
        model.config.num_hidden_layers *= 2

    streamer = TextStreamer(tokenizer)
    print(f"\nAblated chat with {args.model}")
    print("Type 'quit' to exit.\n")

    conversation = []
    while True:
        try:
            prompt = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if prompt.strip().lower() in ("quit", "exit"):
            break

        conversation.append({"role": "user", "content": prompt})

        toks = tokenizer.apply_chat_template(
            conversation=conversation,
            add_generation_prompt=True,
            return_tensors="pt",
        )

        gen = model.generate(
            toks.to(model.device),
            streamer=streamer,
            max_new_tokens=args.max_tokens,
        )

        decoded = tokenizer.batch_decode(
            gen[0][len(toks[0]):], skip_special_tokens=True
        )
        conversation.append({"role": "assistant", "content": "".join(decoded)})
        print()


if __name__ == "__main__":
    main()
