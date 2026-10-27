"""Compare generation-shaping evidence with and without the scale adjective.

This reuses the current production SHAPE_SYSTEM_PROMPT verbatim but does not
import or modify production state. It is comparison evidence, not Qwen scale
classification or prompt tuning.
"""

import ast
import json
import re
import time
from pathlib import Path

import requests

from explicit_scale_parser import parse_leading


ROOT = Path(__file__).resolve().parent
SERVE_PATH = ROOT.parent / "serve.py"
URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "qwen/qwen3-8b"
PHRASES = (
    "tiny toy car",
    "miniature castle",
    "huge mushroom",
    "small house",
    "large bridge",
)


def load_shape_prompt():
    tree = ast.parse(SERVE_PATH.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "SHAPE_SYSTEM_PROMPT" in names:
                return ast.literal_eval(node.value)
    raise RuntimeError("SHAPE_SYSTEM_PROMPT not found")


def strip_think(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def shape(system_prompt, meaning):
    # ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
    started = time.perf_counter()
    response = requests.post(
        URL,
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{meaning} /no_think"},
            ],
            "temperature": 0.3,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=60,
    )
    latency = time.perf_counter() - started
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"]
    return raw, strip_think(raw), round(latency, 3)


def main():
    prompt = load_shape_prompt()
    records = []
    raw_root = ROOT / "raw" / "generation_semantics"
    raw_root.mkdir(parents=True, exist_ok=True)
    for phrase in PHRASES:
        parsed = parse_leading(phrase)
        for candidate, generation_input in (
            ("A_keep_adjective", phrase),
            ("B_strip_scale_adjective", parsed["generation_meaning"]),
        ):
            raw, shaped, latency = shape(prompt, generation_input)
            row = {
                "participant_phrase": phrase,
                "candidate": candidate,
                "generation_input": generation_input,
                "shaped_prompt": shaped,
                "raw_output": raw,
                "latency_s": latency,
                "scale_token_present_in_input": generation_input != parsed["generation_meaning"],
            }
            records.append(row)
            slug = phrase.replace(" ", "-")
            (raw_root / f"{slug}__{candidate}.json").write_text(json.dumps(row, indent=2) + "\n")
            print(f"{candidate}: {generation_input!r} -> {shaped!r}", flush=True)
    (ROOT / "generation_semantics_results.json").write_text(json.dumps({"records": records}, indent=2) + "\n")


if __name__ == "__main__":
    main()
