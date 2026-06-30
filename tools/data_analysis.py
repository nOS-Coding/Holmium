"""Data analysis tool — CSV/JSON analysis with pandas + vLLM + script execution."""

import json
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd

from tools.registry import register_tool

VLLM_SOCKET = "/run/holmium/vllm.sock"
WORKSPACE = Path("/home/holmium/projects")
IMAGES_DIR = Path("/var/holmium/images")


def _call_vllm(prompt: str) -> str:
    transport = httpx.HTTPTransport(uds=VLLM_SOCKET)
    payload = {
        "model": "Qwen3.6-35B-A3B-AWQ",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "temperature": 0.3,
    }
    with httpx.Client(transport=transport, timeout=120) as client:
        resp = client.post("http://localhost/v1/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _extract_python_code(text: str) -> Optional[str]:
    """Extract Python code block from LLM response."""
    match = re.search(r"```python\n(.+?)\n```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"```\n(.+?)\n```", text, re.DOTALL)
    if match:
        return match.group(1)
    return None


def _route_image(image_path: str) -> None:
    """Route generated image to appropriate output channels."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(image_path)
    if src.is_file():
        dst = IMAGES_DIR / src.name
        import shutil
        shutil.copy2(str(src), str(dst))


@register_tool(
    "analyze_data",
    "Analyze a CSV or JSON data file: describe, get vLLM insights, generate chart.",
    params_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to CSV or JSON data file",
            },
            "question": {
                "type": "string",
                "description": "Optional question about the data to answer",
            },
        },
        "required": ["file_path"],
    },
)
def analyze_data(file_path: str, question: Optional[str] = None) -> str:
    """Analyze a data file — detect CSV/JSON, describe, get insights, plot chart."""
    if not os.path.isfile(file_path):
        return f"Error: file not found at {file_path}"

    try:
        ext = Path(file_path).suffix.lower()
        df: pd.DataFrame

        if ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext == ".json":
            df = pd.read_json(file_path)
        else:
            return f"Unsupported file type: {ext}. Supported: .csv, .json"

        desc = df.describe(include="all").to_string()
        cols = list(df.columns)
        dtypes = {c: str(df[c].dtype) for c in cols}
        sample = df.head(5).to_string()
        summary = (
            f"Shape: {df.shape}\n"
            f"Columns: {cols}\n"
            f"Dtypes: {dtypes}\n\n"
            f"Describe:\n{desc}\n\n"
            f"Sample (5 rows):\n{sample}"
        )

        prompt = (
            "You are a data analyst. Analyze the following dataset and answer the question if provided.\n"
            "Provide: key insights, patterns, anomalies, and recommendations.\n"
            "Then write a Python script using pandas and matplotlib to visualize the most interesting aspect.\n"
            "The script should:\n"
            "1. Load the data from the original file path\n"
            "2. Create one clear, publication-quality chart\n"
            "3. Save it with plt.savefig() to a path in /home/holmium/projects/\n"
            "4. Use a unique filename with timestamp\n\n"
            f"Data summary:\n{summary}\n"
            + (f"\nQuestion: {question}" if question else "")
        )

        analysis = _call_vllm(prompt)
        code = _extract_python_code(analysis)

        if code:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            script_name = f"analysis_{timestamp}.py"
            WORKSPACE.mkdir(parents=True, exist_ok=True)
            script_path = WORKSPACE / script_name
            script_path.write_text(code.replace(file_path, f'"{file_path}"'))

            result = subprocess.run(
                ["python3", str(script_path)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(WORKSPACE),
            )

            output_lines = [analysis, f"\n--- Script Output ---\n{result.stdout}"]
            if result.stderr:
                output_lines.append(f"\n--- Stderr ---\n{result.stderr[:1000]}")

            for png in WORKSPACE.glob("*.png"):
                _route_image(str(png))

            return "\n".join(output_lines)

        return analysis

    except subprocess.TimeoutExpired:
        return "Analysis script timed out after 60 seconds."
    except Exception as e:
        return f"Error during data analysis: {e}"
