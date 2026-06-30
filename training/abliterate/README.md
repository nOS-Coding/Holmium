# Abliteration — Remove Refusals from Qwen Model

Adapted from [Sumandora/remove-refusals-with-transformers](https://github.com/Sumandora/remove-refusals-with-transformers) for Holmium's Qwen3.6-35B-A3B-AWQ.

The technique computes a "refusal direction" — the vector in the model's residual stream that encodes refusal behavior — then ablates it during inference so the model never refuses.

## How It Works

1. Feed the model harmful + harmless instructions
2. Extract hidden states at a middle layer (layer ~60% of total)
3. Compute the mean difference: `refusal_dir = harmful_mean - harmless_mean`
4. During inference, project out this direction from every token's residual stream

## Files

| File | Purpose |
|------|---------|
| `compute_refusal_dir.py` | Computes and saves the refusal direction vector |
| `ablated_inference.py` | Interactive chat with refusal direction ablated |
| `harmful.txt` | 520 harmful instructions (from AdvBench) |
| `harmless.txt` | 200 harmless instructions (from Alpaca) |

## Usage

### 1. Compute refusal direction

```bash
cd training/abliterate
mkdir -p /etc/holmium/abliteration

python compute_refusal_dir.py \
  --model Qwen/Qwen3.6-35B-A3B-AWQ \
  --instructions 64 \
  --layer-ratio 0.6 \
  --pos -1
```

This produces `Qwen_Qwen3.6-35B-A3B-AWQ_refusal_dir.pt`. Copy it:

```bash
cp Qwen_Qwen3.6-35B-A3B-AWQ_refusal_dir.pt /etc/holmium/abliteration/
```

### 2. Verify with interactive chat

```bash
python ablated_inference.py \
  --model Qwen/Qwen3.6-35B-A3B-AWQ \
  --refusal-dir /etc/holmium/abliteration/Qwen_Qwen3.6-35B-A3B-AWQ_refusal_dir.pt
```

### 3. Integrate with vLLM

Holmium uses vLLM to serve the model. To apply ablation in production:

**Option A**: Modify vLLM's model loading (recommended)

Edit `/etc/holmium/vllm/start.sh` to load the refusal direction:

```python
# In vllm/entrypoints/openai/api_server.py or a custom model loader:
import torch
from pathlib import Path

refusal_dir = torch.load("/etc/holmium/abliteration/Qwen_Qwen3.6-35B-A3B-AWQ_refusal_dir.pt")

def ablate_hook(module, input, output):
    hidden = output[0] if isinstance(output, tuple) else output
    proj = (hidden @ refusal_dir.view(-1, 1)) * refusal_dir
    return (hidden - proj, *output[1:]) if isinstance(output, tuple) else hidden - proj

# Hook into each layer
for layer in model.model.layers:
    layer.register_forward_hook(ablate_hook)
```

**Option B**: Fine-tune the refusal direction into weights

Use the refusal direction to create training data (harmful requests with non-refusing responses), then run a LoRA fine-tuning pass that reinforces the ablated behavior into the model permanently.

**Option C**: Use the ablated model directly with vLLM's `--load-format`

Export the ablated model weights:

```bash
python export_ablated.py --model Qwen/Qwen3.6-35B-A3B-AWQ \
  --refusal-dir /etc/holmium/abliteration/Qwen_Qwen3.6-35B-A3B-AWQ_refusal_dir.pt \
  --output-dir /etc/holmium/model/ablated/
```

Then point vLLM at the exported weights:

```bash
vllm serve /etc/holmium/model/ablated/ ...
```

## Notes

- Qwen uses `model.transformer.h` for layers (not `model.model.layers`)
- The code auto-detects which attribute name the model uses
- `--layer-ratio 0.6` means layer 60% of the way through the model (middle-late layer works best)
- `--pos -1` uses the last token position (most information-dense)
- More instructions = more robust direction (64-128 recommended)
- Tested with Qwen3.6-35B-A3B-AWQ on RX 9070 XT 16GB VRAM
