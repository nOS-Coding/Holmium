#!/usr/bin/env bash
set -euo pipefail

TRAINING_DIR="$(cd "$(dirname "$0")" && pwd)"
CHECKPOINT_DIR="${TRAINING_DIR}/checkpoints"
MODEL_NAME="QuantTrio/Qwen3.6-35B-A3B-AWQ"
DATA_FILE="${TRAINING_DIR}/pairs/training_data.jsonl"
OUTPUT_DIR="${CHECKPOINT_DIR}/final"

mkdir -p "$CHECKPOINT_DIR"

export ROCR_VISIBLE_DEVICES=0
export HIP_VISIBLE_DEVICES=0
export HSA_OVERRIDE_GFX_VERSION=11.0.0

echo "==> Installing Unsloth with ROCm support..."
pip install unsloth unsloth-rocm 2>&1 | tail -5

echo "==> Starting QLoRA fine-tuning..."

python3 - <<PYEOF
import os
import torch
from datasets import Dataset
from unsloth import FastLanguageModel, is_bfloat16_supported
from transformers import TrainingArguments
from trl import SFTTrainer

os.environ["WANDB_DISABLED"] = "true"

MODEL_NAME = "${MODEL_NAME}"
DATA_PATH = "${DATA_FILE}"
CKPT_DIR = "${CHECKPOINT_DIR}"

print("Loading model in 4-bit...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=4096,
    dtype=None,
    load_in_4bit=True,
    device_map="auto",
    trust_remote_code=True,
)

print("Adding LoRA adapters (rank=16, alpha=32, all 7 modules)...")
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha=32,
    lora_dropout=0.0,
    bias="none",
    use_gradient_checkpointing=True,
    random_state=42,
    use_rslora=False,
    loftq_config=None,
)

print("Loading training data...")
data = []
with open(DATA_PATH) as f:
    for line in f:
        entry = json.loads(line)
        turns = entry["conversations"]
        text = ""
        for t in turns:
            role = "user" if t["from"] == "human" else "assistant"
            text += f"<|im_start|>{role}\n{t['value']}<|im_end|>\n"
        text += "<|im_start|>assistant\n"
        data.append({"text": text})

dataset = Dataset.from_list(data)
split = dataset.train_test_split(test_size=0.1, seed=42)
train_dataset = split["train"]
eval_dataset = split["test"]

print(f"Train: {len(train_dataset)} | Eval: {len(eval_dataset)}")

training_args = TrainingArguments(
    output_dir=CKPT_DIR,
    per_device_train_batch_size=1,
    per_device_eval_batch_size=1,
    gradient_accumulation_steps=8,
    num_train_epochs=3,
    learning_rate=2e-4,
    warmup_steps=100,
    lr_scheduler_type="cosine",
    logging_steps=10,
    eval_steps=100,
    save_steps=500,
    evaluation_strategy="steps",
    save_strategy="steps",
    save_total_limit=3,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    fp16=not is_bfloat16_supported(),
    bf16=is_bfloat16_supported(),
    gradient_checkpointing=True,
    optim="adamw_8bit",
    report_to="none",
    seed=42,
    remove_unused_columns=False,
    dataloader_num_workers=2,
    ddp_find_unused_parameters=False,
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    dataset_text_field="text",
    max_seq_length=4096,
    packing=False,
)

print("Starting training...")
trainer.train()

print(f"Saving final model to {OUTPUT_DIR}...")
trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print("Fine-tuning complete!")
PYEOF

echo ""
echo "============================================"
echo "Training complete!"
echo "Final checkpoint: ${CHECKPOINT_DIR}/final"
echo "Run merge.sh to merge the adapter into the base model."
echo "============================================"
