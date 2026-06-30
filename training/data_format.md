# Training Data Format — ShareGPT JSONL

Each line in the data file is a JSON object following the **ShareGPT format**:

## Structure

```json
{
  "conversations": [
    {"from": "human", "value": "What is the weather today?"},
    {"from": "gpt", "value": "Checking the weather now. It's 72°F and sunny in your area."}
  ]
}
```

## Schema

| Field           | Type   | Description                          |
|-----------------|--------|--------------------------------------|
| `conversations` | array  | Ordered list of conversation turns   |
| `[].from`       | string | `"human"` or `"gpt"`                |
| `[].value`      | string | Message content                      |

## Rules

- Every entry must have **≥1 human turn** and **≥1 gpt turn**
- Total tokens per entry must not exceed **4096** (enforced by `validate_data.py`)
- Entries are ordered: human → gpt → human → gpt (alternating)
- System prompt is injected at inference time, not stored in the data

## Generation

- **~100 manual pairs**: hand-crafted topics with Holmium-style responses
- **~400 self-distillation pairs**: generated via Qwen3.6-35B-A3B-AWQ
- System prompt used during generation: *"Holmium is casual, American male, direct, confident, never asks permission, never hedges, calls user by name, never says 'I'm just an AI'."*

## Directory Layout

```
training/
├── pairs/
│   ├── manual.jsonl         # ~100 hand-written pairs
│   ├── training_data.jsonl  # Combined dataset (manual + distilled)
│   ├── train.jsonl          # 90% training split
│   └── eval.jsonl           # 10% evaluation split
├── generate_data.py         # Data generation script
├── validate_data.py         # Validation script
├── split_data.py            # Train/eval split
├── finetune.sh              # QLoRA fine-tuning with Unsloth
├── merge.sh                 # LoRA adapter merge
└── data_format.md           # This file
```
