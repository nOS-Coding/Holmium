#!/usr/bin/env python3
"""Standalone FramePack video generation — called as subprocess by tools/video.py.

Usage:
    python framepack_generate.py --image <path> --prompt "<text>" --output <dir>
        [--seed N] [--duration N] [--steps N] [--cfg N] [--negative "<text>"]

Outputs JSON to stdout with the result.
"""

import argparse
import json
import os
import sys
import traceback
import uuid
from pathlib import Path

import numpy as np
import torch
from PIL import Image

FRAMEPACK_DIR = Path.home() / "FramePack"
if FRAMEPACK_DIR.exists():
    sys.path.insert(0, str(FRAMEPACK_DIR))

os.environ["HF_HOME"] = str(FRAMEPACK_DIR / "hf_download")

from diffusers_helper.hf_login import login
from diffusers_helper.memory import (
    gpu, get_cuda_free_memory_gb, move_model_to_device_with_memory_preservation,
    offload_model_from_device_for_memory_preservation, fake_diffusers_current_device,
    DynamicSwapInstaller, unload_complete_models, load_model_as_complete,
)
from diffusers_helper.utils import (
    save_bcthw_as_mp4, crop_or_pad_yield_mask, soft_append_bcthw,
    resize_and_center_crop, generate_timestamp,
)
from diffusers_helper.hunyuan import encode_prompt_conds, vae_decode, vae_encode
from diffusers_helper.pipelines.k_diffusion_hunyuan import sample_hunyuan
from diffusers_helper.clip_vision import hf_clip_vision_encode
from diffusers_helper.bucket_tools import find_nearest_bucket
from diffusers_helper.models.hunyuan_video_packed import HunyuanVideoTransformer3DModelPacked
from diffusers import AutoencoderKLHunyuanVideo
from transformers import (
    LlamaModel, CLIPTextModel, LlamaTokenizerFast, CLIPTokenizer,
    SiglipImageProcessor, SiglipVisionModel,
)


def load_models(high_vram: bool):
    text_encoder = LlamaModel.from_pretrained(
        "hunyuanvideo-community/HunyuanVideo", subfolder='text_encoder',
        torch_dtype=torch.float16,
    ).cpu()
    text_encoder_2 = CLIPTextModel.from_pretrained(
        "hunyuanvideo-community/HunyuanVideo", subfolder='text_encoder_2',
        torch_dtype=torch.float16,
    ).cpu()
    tokenizer = LlamaTokenizerFast.from_pretrained(
        "hunyuanvideo-community/HunyuanVideo", subfolder='tokenizer',
    )
    tokenizer_2 = CLIPTokenizer.from_pretrained(
        "hunyuanvideo-community/HunyuanVideo", subfolder='tokenizer_2',
    )
    vae = AutoencoderKLHunyuanVideo.from_pretrained(
        "hunyuanvideo-community/HunyuanVideo", subfolder='vae',
        torch_dtype=torch.float16,
    ).cpu()
    feature_extractor = SiglipImageProcessor.from_pretrained(
        "lllyasviel/flux_redux_bfl", subfolder='feature_extractor',
    )
    image_encoder = SiglipVisionModel.from_pretrained(
        "lllyasviel/flux_redux_bfl", subfolder='image_encoder',
        torch_dtype=torch.float16,
    ).cpu()
    transformer = HunyuanVideoTransformer3DModelPacked.from_pretrained(
        'lllyasviel/FramePackI2V_HY', torch_dtype=torch.bfloat16,
    ).cpu()

    for m in [vae, text_encoder, text_encoder_2, image_encoder, transformer]:
        m.eval()
        m.requires_grad_(False)

    if not high_vram:
        vae.enable_slicing()
        vae.enable_tiling()

    transformer.high_quality_fp32_output_for_inference = True
    transformer.to(dtype=torch.bfloat16)
    vae.to(dtype=torch.float16)
    image_encoder.to(dtype=torch.float16)
    text_encoder.to(dtype=torch.float16)
    text_encoder_2.to(dtype=torch.float16)

    if not high_vram:
        DynamicSwapInstaller.install_model(transformer, device=gpu)
        DynamicSwapInstaller.install_model(text_encoder, device=gpu)
    else:
        text_encoder.to(gpu)
        text_encoder_2.to(gpu)
        image_encoder.to(gpu)
        vae.to(gpu)
        transformer.to(gpu)

    return {
        "text_encoder": text_encoder,
        "text_encoder_2": text_encoder_2,
        "tokenizer": tokenizer,
        "tokenizer_2": tokenizer_2,
        "vae": vae,
        "feature_extractor": feature_extractor,
        "image_encoder": image_encoder,
        "transformer": transformer,
    }


def main():
    parser = argparse.ArgumentParser(description="FramePack video generation")
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--prompt", required=True, help="Text prompt")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--seed", type=int, default=0, help="Random seed")
    parser.add_argument("--duration", type=float, default=5.0, help="Video duration in seconds")
    parser.add_argument("--steps", type=int, default=25, help="Inference steps")
    parser.add_argument("--cfg", type=float, default=10.0, help="Distilled CFG scale")
    parser.add_argument("--negative", default="", help="Negative prompt")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.seed == 0:
        seed = uuid.uuid4().int & 0xFFFFFFFF
    else:
        seed = args.seed

    free_mem_gb = get_cuda_free_memory_gb(gpu)
    high_vram = free_mem_gb > 60

    m = load_models(high_vram)

    input_image_np = np.array(Image.open(args.image).convert("RGB"))
    H, W, C = input_image_np.shape
    height, width = find_nearest_bucket(H, W, resolution=640)
    input_image_np = resize_and_center_crop(input_image_np, target_width=width, target_height=height)

    Image.fromarray(input_image_np).save(str(output_dir / "input.png"))

    input_image_pt = torch.from_numpy(input_image_np).float() / 127.5 - 1
    input_image_pt = input_image_pt.permute(2, 0, 1)[None, :, None]

    latent_window_size = 9
    total_latent_sections = max(round((args.duration * 30) / (latent_window_size * 4)), 1)

    if not high_vram:
        unload_complete_models(m["text_encoder"], m["text_encoder_2"], m["image_encoder"], m["vae"], m["transformer"])

    if not high_vram:
        fake_diffusers_current_device(m["text_encoder"], gpu)
        load_model_as_complete(m["text_encoder_2"], target_device=gpu)

    llama_vec, clip_l_pooler = encode_prompt_conds(
        args.prompt, m["text_encoder"], m["text_encoder_2"],
        m["tokenizer"], m["tokenizer_2"],
    )

    if args.negative:
        llama_vec_n, clip_l_pooler_n = encode_prompt_conds(
            args.negative, m["text_encoder"], m["text_encoder_2"],
            m["tokenizer"], m["tokenizer_2"],
        )
    else:
        llama_vec_n = torch.zeros_like(llama_vec)
        clip_l_pooler_n = torch.zeros_like(clip_l_pooler)

    llama_vec, llama_attention_mask = crop_or_pad_yield_mask(llama_vec, length=512)
    llama_vec_n, llama_attention_mask_n = crop_or_pad_yield_mask(llama_vec_n, length=512)

    if not high_vram:
        load_model_as_complete(m["vae"], target_device=gpu)

    start_latent = vae_encode(input_image_pt, m["vae"])

    if not high_vram:
        load_model_as_complete(m["image_encoder"], target_device=gpu)

    image_encoder_output = hf_clip_vision_encode(
        input_image_np, m["feature_extractor"], m["image_encoder"],
    )
    image_encoder_last_hidden_state = image_encoder_output.last_hidden_state

    llama_vec = llama_vec.to(m["transformer"].dtype)
    llama_vec_n = llama_vec_n.to(m["transformer"].dtype)
    clip_l_pooler = clip_l_pooler.to(m["transformer"].dtype)
    clip_l_pooler_n = clip_l_pooler_n.to(m["transformer"].dtype)
    image_encoder_last_hidden_state = image_encoder_last_hidden_state.to(m["transformer"].dtype)

    rnd = torch.Generator("cpu").manual_seed(seed)
    num_frames = latent_window_size * 4 - 3
    gpu_memory_preservation = 6.0

    history_latents = torch.zeros(
        size=(1, 16, 1 + 2 + 16, height // 8, width // 8),
        dtype=torch.float32,
    ).cpu()
    history_pixels = None
    total_generated_latent_frames = 0

    if total_latent_sections > 4:
        latent_paddings = [3] + [2] * (total_latent_sections - 3) + [1, 0]
    else:
        latent_paddings = list(reversed(range(total_latent_sections)))

    for latent_padding in latent_paddings:
        is_last_section = latent_padding == 0
        latent_padding_size = latent_padding * latent_window_size

        indices = torch.arange(0, sum([1, latent_padding_size, latent_window_size, 1, 2, 16])).unsqueeze(0)
        parts = indices.split([1, latent_padding_size, latent_window_size, 1, 2, 16], dim=1)
        clean_latent_indices_pre, _, latent_indices, clean_latent_indices_post, clean_latent_2x_indices, clean_latent_4x_indices = parts
        clean_latent_indices = torch.cat([clean_latent_indices_pre, clean_latent_indices_post], dim=1)

        clean_latents_pre = start_latent.to(history_latents)
        clean_latents_post, clean_latents_2x, clean_latents_4x = history_latents[:, :, :1 + 2 + 16, :, :].split([1, 2, 16], dim=2)
        clean_latents = torch.cat([clean_latents_pre, clean_latents_post], dim=2)

        if not high_vram:
            unload_complete_models()
            move_model_to_device_with_memory_preservation(
                m["transformer"], target_device=gpu, preserved_memory_gb=gpu_memory_preservation,
            )

        m["transformer"].initialize_teacache(enable_teacache=True, num_steps=args.steps)

        generated_latents = sample_hunyuan(
            transformer=m["transformer"],
            sampler='unipc',
            width=width,
            height=height,
            frames=num_frames,
            real_guidance_scale=1.0,
            distilled_guidance_scale=args.cfg,
            guidance_rescale=0.0,
            num_inference_steps=args.steps,
            generator=rnd,
            prompt_embeds=llama_vec,
            prompt_embeds_mask=llama_attention_mask,
            prompt_poolers=clip_l_pooler,
            negative_prompt_embeds=llama_vec_n,
            negative_prompt_embeds_mask=llama_attention_mask_n,
            negative_prompt_poolers=clip_l_pooler_n,
            device=gpu,
            dtype=torch.bfloat16,
            image_embeddings=image_encoder_last_hidden_state,
            latent_indices=latent_indices,
            clean_latents=clean_latents,
            clean_latent_indices=clean_latent_indices,
            clean_latents_2x=clean_latents_2x,
            clean_latent_2x_indices=clean_latent_2x_indices,
            clean_latents_4x=clean_latents_4x,
            clean_latent_4x_indices=clean_latent_4x_indices,
            callback=None,
        )

        if is_last_section:
            generated_latents = torch.cat([start_latent.to(generated_latents), generated_latents], dim=2)

        total_generated_latent_frames += int(generated_latents.shape[2])
        history_latents = torch.cat([generated_latents.to(history_latents), history_latents], dim=2)

        if not high_vram:
            offload_model_from_device_for_memory_preservation(
                m["transformer"], target_device=gpu, preserved_memory_gb=8,
            )
            load_model_as_complete(m["vae"], target_device=gpu)

        real_history_latents = history_latents[:, :, :total_generated_latent_frames, :, :]

        if history_pixels is None:
            history_pixels = vae_decode(real_history_latents, m["vae"]).cpu()
        else:
            section_latent_frames = (latent_window_size * 2 + 1) if is_last_section else (latent_window_size * 2)
            overlapped_frames = latent_window_size * 4 - 3
            current_pixels = vae_decode(real_history_latents[:, :, :section_latent_frames], m["vae"]).cpu()
            history_pixels = soft_append_bcthw(current_pixels, history_pixels, overlapped_frames)

        if not high_vram:
            unload_complete_models()

        section_path = output_dir / f"section_{total_generated_latent_frames}.mp4"
        save_bcthw_as_mp4(history_pixels, str(section_path), fps=30, crf=16)

        if is_last_section:
            break

    if not high_vram:
        unload_complete_models(
            m["text_encoder"], m["text_encoder_2"], m["image_encoder"], m["vae"], m["transformer"],
        )

    final_path = output_dir / "final.mp4"
    if section_path != final_path:
        import shutil
        shutil.move(str(section_path), str(final_path))

    result = {
        "success": True,
        "path": str(final_path),
        "duration": args.duration,
        "seed": seed,
        "width": width,
        "height": height,
        "frames": total_generated_latent_frames,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        result = {"success": False, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
        print(json.dumps(result))
        sys.exit(1)
