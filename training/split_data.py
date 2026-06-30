#!/usr/bin/env python3
"""90/10 train/eval split of ShareGPT JSONL data."""

import json
import os
import random

INPUT_FILE = os.path.join(os.path.dirname(__file__), "pairs", "training_data.jsonl")
TRAIN_OUT = os.path.join(os.path.dirname(__file__), "pairs", "train.jsonl")
EVAL_OUT = os.path.join(os.path.dirname(__file__), "pairs", "eval.jsonl")

SPLIT_RATIO = 0.9
SEED = 42


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Input file not found: {INPUT_FILE}")
        print("Run generate_data.py first.")
        return

    entries = []
    with open(INPUT_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    random.seed(SEED)
    random.shuffle(entries)

    split_idx = int(len(entries) * SPLIT_RATIO)
    train = entries[:split_idx]
    eval_ = entries[split_idx:]

    with open(TRAIN_OUT, "w") as f:
        for entry in train:
            f.write(json.dumps(entry) + "\n")

    with open(EVAL_OUT, "w") as f:
        for entry in eval_:
            f.write(json.dumps(entry) + "\n")

    print(f"Split complete ({SPLIT_RATIO*100:.0f}/{100-SPLIT_RATIO*100:.0f}):")
    print(f"  Train: {len(train)} entries → {TRAIN_OUT}")
    print(f"  Eval:  {len(eval_)} entries → {EVAL_OUT}")


if __name__ == "__main__":
    main()
