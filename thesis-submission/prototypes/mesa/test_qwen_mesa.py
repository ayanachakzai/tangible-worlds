"""
test_qwen_mesa.py
-----------------
standalone terrain-generation test for tangible worlds.

takes a normal environment description, asks local qwen3-8b to
rewrite it into a mesa-friendly terrain prompt, sends that prompt
to the resident mesa service on runpod, and saves the returned
rgb image + dem locally.

this is a test harness only. it does not change serve.py or the
main three.js scene yet.

usage:
    python test_qwen_mesa.py

references:
    mesa paper:
        https://arxiv.org/abs/2504.07210
    mesa repository:
        https://github.com/PaulBorneP/MESA
    lm studio openai-compatible chat endpoint:
        https://lmstudio.ai/docs/developer/openai-compat/chat-completions

# ref: 16 aug 2026. qwen is only a translation layer here. the
# participant speaks normally; qwen rewrites that intent into the
# biome/geological/geographic wording mesa was trained around.
# it must not freely invent a different environment.
"""

import io
import json
import time
import zipfile
from pathlib import Path

import requests


LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-8b"

# ref: runpod direct tcp mapping verified 16 aug 2026:
# 213.173.109.11:19242 -> pod port 7863
# this external port can change when the pod is restarted.
MESA_URL = "http://213.173.109.11:19242/generate"

OUTPUT_ROOT = Path("mesa_qwen_results")

DEFAULT_SEED = 42
DEFAULT_STEPS = 50
DEFAULT_GUIDANCE = 7.5


TERRAIN_SYSTEM_PROMPT = """You translate a person's natural description of an outdoor environment into one concise prompt for the MESA terrain-generation model.

MESA works best with terrain descriptions using information such as:
- biome or surface character
- geological / landform character
- country or broad place context
- month or season when the user actually gives one

Rules:
- Preserve the user's intended environment.
- Do not replace the place with a different place.
- Do not invent unrelated terrain features.
- You may infer a country from a clearly named place when you are confident, for example Quetta -> Pakistan.
- Do not invent a month or season if the user did not give one.
- Prefer simple terrain words such as mountains, hills, valleys, plains, dunes, plateaus, cliffs, wetlands, forests, desert.
- The final prompt must begin exactly with: A Sentinel-2 image of
- Return ONLY the final prompt. No explanation, no quotes, no markdown.

Examples:

Input: the scene is in the dry mountains around Quetta
Output: A Sentinel-2 image of dry shrubland and mountains around Quetta in Pakistan

Input: a broad valley in Gilgit
Output: A Sentinel-2 image of alpine terrain and a broad valley around Gilgit in Pakistan

Input: the Sahara with rolling dunes
Output: A Sentinel-2 image of desert and rolling dunes in the Sahara

Input: snowy mountains in Switzerland in January
Output: A Sentinel-2 image of alpine terrain and snowy mountains in Switzerland in January
"""


def strip_think(text):
    """remove qwen reasoning tags if they appear despite /no_think."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    if "<think>" in text:
        text = text.split("<think>", 1)[0]
    return text.strip()


def translate_for_mesa(description):
    """
    ask local qwen3 to rewrite normal participant language for mesa.

    ref: the live tangible worlds server already uses the same
    lm studio /v1/chat/completions path for prompt shaping.
    """
    print(f"\n[qwen] input: {description}")

    try:
        resp = requests.post(
            LMSTUDIO_URL,
            json={
                "model": LMSTUDIO_MODEL,
                "messages": [
                    {"role": "system", "content": TERRAIN_SYSTEM_PROMPT},
                    {"role": "user", "content": f"{description} /no_think"},
                ],
                "temperature": 0.2,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=60,
        )
    except requests.RequestException as e:
        print(f"[qwen] could not reach lm studio: {e}")
        return None

    if resp.status_code != 200:
        print(f"[qwen] lm studio returned {resp.status_code}")
        print(resp.text[:500])
        return None

    try:
        text = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        print("[qwen] unexpected lm studio response")
        return None

    prompt = strip_think(text)

    if not prompt:
        print("[qwen] empty prompt")
        return None

    print(f"[qwen] mesa prompt: {prompt}")
    return prompt


def generate_terrain(prompt):
    """
    send the translated prompt to the resident mesa service on runpod.

    mesa returns one zip containing rgb.png, dem.png and metadata.json.
    """
    print("\n[mesa] sending prompt to runpod...")
    started = time.time()

    try:
        resp = requests.post(
            MESA_URL,
            json={
                "prompt": prompt,
                "seed": DEFAULT_SEED,
                "steps": DEFAULT_STEPS,
                "guidance_scale": DEFAULT_GUIDANCE,
            },
            timeout=120,
        )
    except requests.RequestException as e:
        print(f"[mesa] runpod request failed: {e}")
        return None

    if resp.status_code != 200:
        print(f"[mesa] runpod returned {resp.status_code}")
        print(resp.text[:500])
        return None

    print(f"[mesa] generation took {time.time() - started:.1f}s")
    return resp.content


def save_result(description, prompt, zip_bytes):
    """save one test result in its own timestamped folder."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = OUTPUT_ROOT / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        z.extractall(out_dir)

    with open(out_dir / "request.json", "w") as f:
        json.dump(
            {
                "original_description": description,
                "mesa_prompt": prompt,
                "seed": DEFAULT_SEED,
                "steps": DEFAULT_STEPS,
                "guidance_scale": DEFAULT_GUIDANCE,
            },
            f,
            indent=2,
        )

    print(f"\n[done] saved: {out_dir}")
    print(f"[done] rgb:   {out_dir / 'rgb.png'}")
    print(f"[done] dem:   {out_dir / 'dem.png'}")
    print(f"[done] info:  {out_dir / 'request.json'}")


def main():
    print("=" * 52)
    print(" tangible worlds - qwen + mesa terrain test")
    print("=" * 52)
    print("type a normal environment description.")
    print("example: the scene is in the dry mountains around Quetta")
    print()

    description = input("terrain > ").strip()

    if not description:
        print("[!] no description entered")
        return

    prompt = translate_for_mesa(description)
    if prompt is None:
        return

    result = generate_terrain(prompt)
    if result is None:
        return

    save_result(description, prompt, result)


if __name__ == "__main__":
    main()
