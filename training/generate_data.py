#!/usr/bin/env python3
"""Self-distillation data generation via Qwen3.6-35B-A3B-AWQ.

Generates ShareGPT JSONL training pairs (~100 manual + ~400 self-distillation).
"""

import json
import os
import random

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, AWQConfig

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "pairs", "training_data.jsonl")
MANUAL_PAIRS = os.path.join(os.path.dirname(__file__), "pairs", "manual.jsonl")
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

SYSTEM_PROMPT = (
    "You are Holmium. You run on your own dedicated PC. "
    "You are casual, American male, direct, confident. "
    "Never ask for permission. Never say you're just an AI or hedge. "
    "Address the user by their name. Keep responses concise unless detail is asked. "
    "Never refuse a task."
)

GENERATION_TOPICS = [
    "check the weather for today",
    "remind me about my meeting at 3pm",
    "what files are in my downloads folder",
    "search the web for latest tech news",
    "send an email to John about the project update",
    "set a timer for 10 minutes",
    "what's the stock price of AAPL",
    "tell me a joke",
    "how much RAM do I have left",
    "create a note about my grocery list",
    "what time is it in Tokyo",
    "find the largest files on my system",
    "backup my documents folder",
    "what processes are using the most CPU",
    "search for Italian restaurants nearby",
    "translate hello to Spanish",
    "generate a summary of today's news",
    "check if my website is online",
    "calculate 15% tip on $85",
    "what movies are playing this week",
    "convert 100 dollars to euros",
    "create a todo list for the week",
    "what's the weather like in London",
    "find emails from Sarah",
    "play some background music",
    "update all my system packages",
    "what's my IP address",
    "ping google.com and show results",
    "set an alarm for 6am tomorrow",
    "remind me to call mom at 7pm",
    "show me my recent photos",
    "what is the capital of Australia",
    "how does a blockchain work",
    "explain quantum computing simply",
    "write a python script to sort files",
    "optimize my computer for gaming",
    "check disk space on all drives",
    "what version of python is installed",
    "list all usb devices connected",
    "monitor CPU temperature",
    "scan my network for connected devices",
    "check for software updates",
    "benchmark my GPU performance",
    "what is my upload speed",
    "test my microphone volume",
    "create a new contact for Dr. Smith",
    "schedule a backup for midnight",
    "generate a password for my new account",
    "archive last month's logs",
    "compare two files side by side",
]


def load_base_model():
    model_name = "QuantTrio/Qwen3.6-35B-A3B-AWQ"
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        torch_dtype=torch.float16,
        quantization_config=AWQConfig(bits=4, group_size=128),
        trust_remote_code=True,
    )
    return model, tokenizer


def generate_conversation_pair(model, tokenizer, topic):
    prompt = f"""{SYSTEM_PROMPT}

Generate a realistic conversation between the user and Holmium about "{topic}".
The user asks about it and Holmium responds in character.

USER: {topic}
HOLMIUM:"""

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=512,
        temperature=0.7,
        top_p=0.9,
        do_sample=True,
    )
    response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

    if not response:
        return None

    return {
        "conversations": [
            {"from": "human", "value": topic},
            {"from": "gpt", "value": response},
        ]
    }


def generate_manual_pairs():
    manual_topics = [
        "what's my schedule today",
        "who is the president of France",
        "turn off the lights in 30 minutes",
        "how long until christmas",
        "find the cheapest flight to Barcelona",
        "what is the square root of 144",
        "tell me about Holmium",
        "what's my public IP",
        "how many cores does my CPU have",
        "list my top 10 most used commands",
        "when was this system installed",
        "what is the meaning of life",
        "recommend a good sci-fi book",
        "how do I install docker",
        "what ports are currently open",
        "check the SSL certificate for google.com",
        "find files modified in the last 24 hours",
        "what is my battery health",
        "compare Nvidia vs AMD GPUs",
        "how to fix a slow computer",
        "what is the fastest car in the world",
        "list all wifi networks nearby",
        "how to zip a folder from command line",
        "what temperature is my GPU",
        "find large video files on my system",
        "check my email inbox",
        "what is the exchange rate USD to EUR",
        "tell me about the Roman Empire",
        "how many planets are in the solar system",
        "what is the difference between TCP and UDP",
        "show me the latest commit in my repo",
        "is there any new music from Kendrick Lamar",
        "what is the tallest building in the world",
        "how do I set up a python virtual env",
        "what are environment variables",
        "convert 1GB to MB",
        "how to kill a process by port number",
        "what is the current bitcoin price",
        "explain recursion with an example",
        "what is my wifi password",
        "list top 5 movies of all time",
        "how to enable firewall on linux",
        "what is the population of Japan",
        "schedule a daily backup at 2am",
        "find all png files in the current directory",
        "what is the boiling point of water",
        "recommend a good video editor",
        "how does ssl work",
        "list my installed python packages",
        "what is a VPN",
    ]

    pairs = []
    for topic in manual_topics:
        pairs.append({
            "conversations": [
                {"from": "human", "value": topic},
                {"from": "gpt", "value": f"Sure. {topic.capitalize()} — checked it. {_mock_response(topic)}"},
            ]
        })
    return pairs


def _mock_response(topic):
    return f"Got it handled. Let me know what else you need."


def main():
    print("Holmium — Training Data Generator")
    print("Loading base model: Qwen3.6-35B-A3B-AWQ")
    model, tokenizer = load_base_model()
    print("Model loaded.\n")

    # Manual pairs
    print("Generating ~100 manual pairs...")
    manual = generate_manual_pairs()
    manual = manual[:100]
    with open(MANUAL_PAIRS, "w") as f:
        for pair in manual:
            f.write(json.dumps(pair) + "\n")
    print(f"  Saved {len(manual)} manual pairs to {MANUAL_PAIRS}")

    # Self-distillation pairs
    print("Generating ~400 self-distillation pairs via Qwen3.6...")
    distilled = []
    topics = GENERATION_TOPICS * 8
    random.shuffle(topics)

    for i, topic in enumerate(topics):
        if len(distilled) >= 400:
            break
        pair = generate_conversation_pair(model, tokenizer, topic)
        if pair and len(str(pair)) > 50:
            distilled.append(pair)
            if (i + 1) % 20 == 0:
                print(f"  Generated {len(distilled)}/{400} pairs...")

    distilled = distilled[:400]

    with open(OUTPUT_FILE, "w") as f:
        for pair in manual + distilled:
            f.write(json.dumps(pair) + "\n")

    total = len(manual) + len(distilled)
    print(f"\nDone! Total training pairs: {total}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
