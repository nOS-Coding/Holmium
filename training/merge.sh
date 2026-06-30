#!/usr/bin/env bash
set -euo pipefail

TRAINING_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_MODEL="QuantTrio/Qwen3.6-35B-A3B-AWQ"
ADAPTER_PATH="${TRAINING_DIR}/checkpoints/final"
MERGE_OUTPUT="${TRAINING_DIR}/../model/holmium-merged"

mkdir -p "$MERGE_OUTPUT"

export ROCR_VISIBLE_DEVICES=0
export HIP_VISIBLE_DEVICES=0

echo "==> Merging LoRA adapter into base model..."
echo "  Base model:    ${BASE_MODEL}"
echo "  Adapter:       ${ADAPTER_PATH}"
echo "  Output:        ${MERGE_OUTPUT}"
echo ""

python3 <<PYEOF
import torch
from unsloth import FastLanguageModel
from transformers import AutoTokenizer

BASE_MODEL = "${BASE_MODEL}"
ADAPTER_PATH = "${ADAPTER_PATH}"
OUTPUT_PATH = "${MERGE_OUTPUT}"

print("Loading base model with adapter...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL,
    max_seq_length=4096,
    dtype=torch.float16,
    load_in_4bit=True,
    device_map="auto",
    trust_remote_code=True,
)

print("Loading LoRA adapter...")
model.load_adapter(ADAPTER_PATH)

print("Merging adapter and unloading...")
model = model.merge_and_unload()

print(f"Saving merged model to {OUTPUT_PATH}...")
model.save_pretrained(
    OUTPUT_PATH,
    safe_serialization=True,
    max_shard_size="4GB",
)
tokenizer.save_pretrained(OUTPUT_PATH)

print("Merge complete! Merged model saved in safetensors format.")
PYEOF

echo ""
echo "============================================"
echo "Merge complete!"
echo "Merged model: ${MERGE_OUTPUT}"
echo "============================================"
