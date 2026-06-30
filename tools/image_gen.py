"""FLUX.1-schnell image generation tool."""

import os
import uuid
from pathlib import Path

import torch
from diffusers import FluxPipeline

from tools.registry import register_tool

IMAGES_DIR = Path("/var/holmium/images")


def _ensure_images_dir() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


_pipeline = None


def _get_pipeline() -> FluxPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-schnell",
            torch_dtype=torch.bfloat16,
        ).to("cuda")
    return _pipeline


@register_tool(
    "generate_image",
    "Generate an image from a text prompt using FLUX.1-schnell.",
    params_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text prompt describing the image to generate",
            },
            "steps": {
                "type": "integer",
                "description": "Number of inference steps (default 4)",
                "default": 4,
            },
            "guidance_scale": {
                "type": "number",
                "description": "Guidance scale for generation (default 0.0 for schnell)",
                "default": 0.0,
            },
            "width": {
                "type": "integer",
                "description": "Image width in pixels (default 1024)",
                "default": 1024,
            },
            "height": {
                "type": "integer",
                "description": "Image height in pixels (default 1024)",
                "default": 1024,
            },
        },
        "required": ["prompt"],
    },
)
def generate_image(
    prompt: str,
    steps: int = 4,
    guidance_scale: float = 0.0,
    width: int = 1024,
    height: int = 1024,
) -> str:
    """Generate a PNG image using FLUX.1-schnell and return the file path."""
    _ensure_images_dir()

    pipe = _get_pipeline()

    seed = uuid.uuid4().int & ((1 << 64) - 1)
    generator = torch.Generator("cuda").manual_seed(seed)

    images = pipe(
        prompt=prompt,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        width=width,
        height=height,
        generator=generator,
    ).images

    filename = f"{uuid.uuid4().hex}.png"
    path = IMAGES_DIR / filename
    images[0].save(str(path), format="PNG")

    return str(path)
