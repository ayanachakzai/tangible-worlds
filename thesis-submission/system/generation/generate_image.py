"""
generate_image.py (sdxl-turbo variant)
---------------------------------------
stage 1 test candidate. same job as phase2-generation-tripsor/generate_image.py,
prompt in, image out. only difference under test is the backbone: sdxl-turbo
instead of sd-turbo. does a bigger stage 1 model give sf3d a cleaner source
image to reconstruct from.

# ref: 20/21 july. shares the triposr conda env, not its own env, ayan's
# call. checked first: diffusers 0.39.0 / transformers 5.13.0 already
# support sdxl-turbo, no upgrade needed, no risk to sd-turbo in same env.

usage:
    python generate_image.py "a car" /tmp/car1.png

references:
    sdxl-turbo model card, recommended usage (1 step, guidance_scale 0.0,
    512x512, euler ancestral w/ trailing timesteps):
        https://huggingface.co/stabilityai/sdxl-turbo
"""

import sys
import torch
from diffusers import AutoPipelineForText2Image

IMAGE_MODEL_ID = "stabilityai/sdxl-turbo"

# ref: 26 july, phase 3.4. the fixed suffix is GONE. it couldn't serve an
# open vocab, one wording ("game asset, isometric") worked for mountains
# but gridded trees into a 4-tree layout. framing now comes per-word from
# the shape_prompt llm call in serve.py, which owns the whole prompt. this
# script just runs whatever prompt it's handed, no prefix, no suffix.
# old suffix kept here as a dead comment for the write-up only:
#   ", single centered object, solid white background, isometric, game asset, blender render, sharp flat faces"

# sdxl-turbo is designed for 1 to 4 steps. i use 5 because 4 gave a worse
# mountain result in my testing. guidance 0.0 and 512x512 follow the model card.
# ref: https://huggingface.co/stabilityai/sdxl-turbo
NUM_INFERENCE_STEPS = 5
GUIDANCE_SCALE = 0.0
IMAGE_SIZE = 512


def main():
    if len(sys.argv) != 3:
        print('usage: python generate_image.py "<prompt>" <output_path>')
        sys.exit(1)

    prompt = sys.argv[1]
    output_path = sys.argv[2]
    # ref: 26 july. prompt is used as-is now, shape_prompt in serve.py
    # already framed it (low poly, white bg, single object, etc). no
    # prefix, no suffix here, one prompt mechanism not two fighting.
    full_prompt = prompt

    # ref: unknown going in whether sdxl-turbo's bigger unet fits mps on
    # the 16gb m5. sf3d ooms on mps at a similar scale and falls back to
    # cpu, this might do the same. printed so a failure is visible
    # immediately instead of guessed at after the fact.
    # ref: https://huggingface.co/stabilityai/sdxl-turbo
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"[stage1-sdxlturbo] device: {device}")

    dtype = torch.float16 if device == "mps" else torch.float32
    pipe = AutoPipelineForText2Image.from_pretrained(
        IMAGE_MODEL_ID, torch_dtype=dtype,
        variant="fp16" if device == "mps" else None,
    )
    pipe = pipe.to(device)

    print(f"[stage1-sdxlturbo] prompt: {full_prompt}")
    # ref: https://huggingface.co/stabilityai/sdxl-turbo
    image = pipe(
        prompt=full_prompt,
        num_inference_steps=NUM_INFERENCE_STEPS,
        guidance_scale=GUIDANCE_SCALE,
        height=IMAGE_SIZE,
        width=IMAGE_SIZE,
    ).images[0]

    image.save(output_path)
    print(f"[stage1-sdxlturbo] saved: {output_path}")


if __name__ == "__main__":
    main()