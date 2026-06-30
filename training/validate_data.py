#!/usr/bin/env python3
"""Validates ShareGPT JSONL training data."""

import json
import os
import sys

try:
    import tiktoken
except ImportError:
    tiktoken = None

MAX_TOKENS = 4096


def count_tokens(text):
    if tiktoken:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    return len(text.split())


def validate_file(path):
    errors = []
    total_entries = 0
    total_turns = 0
    token_counts = []
    empty_entries = 0

    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"  Line {lineno}: Invalid JSON — {e}")
                continue

            convos = entry.get("conversations", [])
            total_entries += 1
            total_turns += len(convos)

            if not convos:
                errors.append(f"  Line {lineno}: Empty conversations array")
                empty_entries += 1
                continue

            human_turns = sum(1 for c in convos if c.get("from") == "human")
            gpt_turns = sum(1 for c in convos if c.get("from") == "gpt")

            if human_turns < 1:
                errors.append(f"  Line {lineno}: Less than 1 human turn (found {human_turns})")
            if gpt_turns < 1:
                errors.append(f"  Line {lineno}: Less than 1 gpt turn (found {gpt_turns})")

            full_text = ""
            for c in convos:
                if "from" not in c or "value" not in c:
                    errors.append(f"  Line {lineno}: Missing 'from' or 'value' in conversation entry")
                else:
                    full_text += c["value"] + " "

            n_tokens = count_tokens(full_text)
            token_counts.append(n_tokens)

            if n_tokens > MAX_TOKENS:
                errors.append(
                    f"  Line {lineno}: Exceeds {MAX_TOKENS} tokens ({n_tokens} tokens)"
                )

    return {
        "path": path,
        "total_entries": total_entries,
        "total_turns": total_turns,
        "avg_turns": round(total_turns / total_entries, 2) if total_entries else 0,
        "avg_tokens": round(sum(token_counts) / len(token_counts), 1) if token_counts else 0,
        "min_tokens": min(token_counts) if token_counts else 0,
        "max_tokens": max(token_counts) if token_counts else 0,
        "empty_entries": empty_entries,
        "errors": errors,
    }


def main():
    paths = sys.argv[1:] if len(sys.argv) > 1 else []
    if not paths:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        pairs_dir = os.path.join(script_dir, "pairs")
        for fname in ["manual.jsonl", "training_data.jsonl"]:
            fpath = os.path.join(pairs_dir, fname)
            if os.path.exists(fpath):
                paths.append(fpath)

    if not paths:
        print("No data files found. Pass paths as arguments.")
        sys.exit(1)

    all_ok = True
    for path in paths:
        print(f"\nValidating: {path}")
        print("-" * 50)
        stats = validate_file(path)

        print(f"  Total entries:        {stats['total_entries']}")
        print(f"  Total turns:          {stats['total_turns']}")
        print(f"  Avg turns/entry:      {stats['avg_turns']}")
        print(f"  Avg tokens/entry:     {stats['avg_tokens']}")
        print(f"  Min tokens:           {stats['min_tokens']}")
        print(f"  Max tokens:           {stats['max_tokens']}")
        print(f"  Empty entries:        {stats['empty_entries']}")

        if stats["errors"]:
            all_ok = False
            print(f"\n  Errors ({len(stats['errors'])}):")
            for err in stats["errors"]:
                print(err)
        else:
            print(f"\n  \033[1;32m✓ All entries valid!\033[0m")

    if not all_ok:
        print("\n\033[1;31mValidation failed — fix errors above.\033[0m")
        sys.exit(1)
    else:
        print("\n\033[1;32mAll files validated successfully.\033[0m")


if __name__ == "__main__":
    main()
