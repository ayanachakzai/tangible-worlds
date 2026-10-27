"""capture one production-equivalent lm studio request with streamed timing.

this is diagnostic-only. it reads the live production prompt and schema from
rendering/serve.py, reads the same scene/modifier state, and changes only the
lm studio response transport from non-streaming to streaming.

usage:
    python capture_request.py "make it stormy"
"""

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

import requests


here = Path(__file__).resolve().parent
phase3_root = here.parents[1]
rendering_dir = phase3_root / "rendering"
serve_path = rendering_dir / "serve.py"
results_dir = here / "results"


def sha256_file(path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def load_production_constants():
    """load serve.py without letting its relative startup reads touch production."""
    # ref: 26 aug 2026. importlib loads a module from an explicit file path.
    # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    spec = importlib.util.spec_from_file_location("tw_serve_latency_diag", serve_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {serve_path}")

    module = importlib.util.module_from_spec(spec)
    old_cwd = Path.cwd()
    try:
        # serve.py has top-level relative state reads and an idempotent mkdir.
        # i isolate those side effects in a temporary directory and only take
        # the production constants needed for this diagnostic.
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            spec.loader.exec_module(module)
    finally:
        os.chdir(old_cwd)

    return module


def read_scene_context(scene_path):
    scene_context = "No scene data available."
    try:
        with open(scene_path) as f:
            scene = json.load(f)
        objects = scene.get("objects", [])
        if objects:
            labels = [obj["label"] for obj in objects]
            layout = scene.get("layout", {})
            scene_context = (
                f"Objects on table: {', '.join(labels)}. "
                f"Spread: {layout.get('spread', 0):.2f}. "
                f"Clusters: {len(scene.get('clusters', []))}."
            )
        else:
            scene_context = "No objects on the table."
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return scene_context


def load_modifiers(modifiers_path, modifier_schema):
    try:
        with open(modifiers_path) as f:
            saved = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}

    current = dict(modifier_schema)
    current.update({
        key: value for key, value in saved.items()
        if key in modifier_schema and value is not None
    })
    return current


def build_payload(production, command, scene_context, current_modifiers):
    prompt = (
        f"Current scene objects: {scene_context}\n"
        f"Current modifiers: {json.dumps(current_modifiers)}\n"
        f"User request: {command}\n"
        "Return the modifier JSON:"
    )

    return {
        "model": production.LMSTUDIO_MODEL,
        "messages": [
            {"role": "system", "content": production.SYSTEM_PROMPT},
            {"role": "user", "content": f"{prompt} /no_think"},
        ],
        "temperature": 0.3,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def consume_stream(response, started):
    """return first-content and completion timing from openai-compatible sse."""
    # ref: 26 aug 2026. lm studio supports stream on /v1/chat/completions.
    # https://lmstudio.ai/docs/developer/openai-compat/chat-completions
    # ref: 26 aug 2026. requests iter_lines is the documented streaming-api path.
    # https://requests.readthedocs.io/en/latest/user/advanced/#streaming-requests
    first_data = None
    first_content = None
    last_content = None
    content_chunks = 0
    finish_reason = None
    parts = []

    if response.encoding is None:
        response.encoding = "utf-8"

    # ref: 26 aug 2026. requests defaults iter_lines to 512-byte chunks.
    # i use 1 byte here so client buffering does not inflate measured ttft.
    # https://github.com/psf/requests/blob/main/src/requests/models.py
    for line in response.iter_lines(chunk_size=1, decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue

        now = time.perf_counter()
        if first_data is None:
            first_data = now

        data = line[5:].strip()
        if data == "[DONE]":
            break

        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue

        choices = chunk.get("choices") or []
        if not choices:
            continue

        choice = choices[0]
        if choice.get("finish_reason") is not None:
            finish_reason = choice["finish_reason"]

        delta = choice.get("delta") or {}
        content = delta.get("content")
        if not isinstance(content, str) or not content:
            continue

        now = time.perf_counter()
        if first_content is None:
            first_content = now
        last_content = now
        content_chunks += 1
        parts.append(content)

    ended = time.perf_counter()
    return {
        "first_data_s": None if first_data is None else first_data - started,
        "ttft_s": None if first_content is None else first_content - started,
        "content_window_s": None if first_content is None else last_content - first_content,
        "post_first_to_end_s": None if first_content is None else ended - first_content,
        "total_s": ended - started,
        "content_chunks": content_chunks,
        "finish_reason": finish_reason,
        "content": "".join(parts),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="make it stormy")
    args = parser.parse_args()

    if not serve_path.exists():
        raise SystemExit(f"missing production file: {serve_path}")

    production = load_production_constants()
    scene_path = (rendering_dir / production.SCENE_DESC_PATH).resolve()
    modifiers_path = (rendering_dir / production.MODIFIERS_PATH).resolve()

    scene_context = read_scene_context(scene_path)
    current_modifiers = load_modifiers(modifiers_path, production.MODIFIER_SCHEMA)
    payload = build_payload(production, args.command.strip(), scene_context, current_modifiers)

    # hard guard: this first diagnostic must differ from production transport only.
    if "max_tokens" in payload or "stream_options" in payload:
        raise RuntimeError("diagnostic payload drifted from the production request")

    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%z")
    wall_started = datetime.now().astimezone().isoformat(timespec="milliseconds")

    # ref: 26 aug 2026. perf_counter is the high-resolution monotonic elapsed timer.
    # https://docs.python.org/3/library/time.html#time.perf_counter
    started = time.perf_counter()
    try:
        # ref: 26 aug 2026. requests keeps response content lazy with stream=True.
        # https://requests.readthedocs.io/en/latest/user/advanced/#body-content-workflow
        with requests.post(
            production.LMSTUDIO_URL,
            json=payload,
            stream=True,
            timeout=60,
        ) as response:
            headers_s = time.perf_counter() - started
            response.raise_for_status()
            streamed = consume_stream(response, started)
            status_code = response.status_code
    except requests.RequestException as exc:
        raise SystemExit(f"lm studio request failed: {exc}") from exc

    result = {
        "timestamp": wall_started,
        "command": args.command.strip(),
        "production_file": str(serve_path),
        "production_file_sha256": sha256_file(serve_path),
        "scene_file": str(scene_path),
        "scene_file_sha256": sha256_file(scene_path),
        "modifiers_file": str(modifiers_path),
        "modifiers_file_sha256": sha256_file(modifiers_path),
        "endpoint": production.LMSTUDIO_URL,
        "model": production.LMSTUDIO_MODEL,
        "payload_sha256": sha256_json(payload),
        "payload": payload,
        "diagnostic_difference": "production payload with stream changed false -> true only",
        "http_status": status_code,
        "response_headers_s": headers_s,
        **streamed,
    }

    results_dir.mkdir(exist_ok=True)
    result_path = results_dir / f"{stamp}.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"command: {result['command']!r}")
    print(f"model: {result['model']}")
    print(f"payload sha256: {result['payload_sha256']}")
    print(f"response headers: {result['response_headers_s']:.3f}s")
    print(f"first sse data: {result['first_data_s']:.3f}s" if result["first_data_s"] is not None else "first sse data: none")
    print(f"ttft first content: {result['ttft_s']:.3f}s" if result["ttft_s"] is not None else "ttft first content: none")
    print(f"content window: {result['content_window_s']:.3f}s" if result["content_window_s"] is not None else "content window: none")
    print(f"total: {result['total_s']:.3f}s")
    print(f"content chunks: {result['content_chunks']}")
    print(f"finish: {result['finish_reason']}")
    print(f"result: {result_path}")
    print("tokens/s: not computed in this first test because stream usage was not added")


if __name__ == "__main__":
    main()
