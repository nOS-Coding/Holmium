# training — Fine-tuning Pipeline

Unsloth QLoRA fine-tuning. Rank 16, alpha 32. 500 training pairs (100 manual + 400 self-distillation via Qwen3.6). On-demand only (not automatic).

- `pipeline.py` — training pipeline
- `pairs/` — training data storage
- `export.py` — LoRA adapter export
