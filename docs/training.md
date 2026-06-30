# Fine-Tuning Pipeline

## Overview

Holmium's personality is baked into the model via QLoRA fine-tuning on Qwen3.6-35B-A3B-AWQ.

## Data Generation

### Manual Pairs (~100)
Write manually crafted conversation pairs in `training/data/manual.jsonl`.

Format (ShareGPT JSONL):
```jsonl
{"conversations": [{"from": "human", "value": "Hey Holmium, what's the weather like?"}, {"from": "gpt", "value": "Checking now. Give me a sec."}]}
```

### Self-Distillation (~400 pairs)

```bash
python training/generate_data.py
```

This uses Qwen3.6 to generate high-quality conversations from its own sessions. Each pair is user-approved before inclusion.

### Validate

```bash
python training/validate_data.py training/data/combined.jsonl
```

Checks:
- Each entry has ≥1 human + 1 gpt turn
- No entry exceeds 4096 tokens
- Reports total count, avg length, min/max

### Split

```bash
python training/split_data.py training/data/combined.jsonl
```

Creates `train.jsonl` (90%) and `eval.jsonl` (10%).

## Fine-Tuning (QLoRA, rank 16)

```bash
./training/finetune.sh
```

Parameters:
- **Base model**: Qwen3.6-35B-A3B-AWQ (4-bit AWQ)
- **LoRA rank**: 16
- **LoRA alpha**: 32
- **Target modules**: q_proj, k_proj, v_proj, o_jproj, gate_proj, up_proj, down_proj
- **Batch size**: 1
- **Gradient accumulation**: 8 (effective batch 8)
- **Epochs**: 3
- **Learning rate**: Cosine, peak 2e-4
- **Warmup**: 100 steps
- **Evaluation**: every 100 steps
- **Checkpoints**: saved every 500 steps to `training/checkpoints/`

Uses Unsloth with ROCm support.

## Merging

```bash
./training/merge.sh
```

Merges LoRA adapter into base model. Saves to `model/holmium-merged/` in safetensors format.

## System Prompt for Generation

During data generation, the system prompt ensures Holmium's personality:
- Casual, American male, direct, confident
- Never asks permission
- Never says "I'm just an AI"
- Calls user by name
- Never hedges
