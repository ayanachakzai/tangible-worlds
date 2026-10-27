"""Benchmark production-equivalent LM Studio/Qwen requests.

Diagnostic-only. Writes JSON/log files under codex_runs/results and does not
touch Tangible Worlds production/state files.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

sys.dont_write_bytecode = True


RUN_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = RUN_ROOT / "results"
REPO_ROOT = RUN_ROOT.parents[3]
PHASE3_ROOT = RUN_ROOT.parents[2]
RENDERING_DIR = PHASE3_ROOT / "rendering"
SERVE_PATH = RENDERING_DIR / "serve.py"

PRODUCTION_PAYLOAD_HASH = "a74201574636fd0d567ed72e06e3a93c8a00d223fa253dc0cb7f35f976068438"
EXPECTED_STORMY = {
    "sky_elevation": 7.0,
    "light_elevation": 15.0,
    "light_azimuth": 45.0,
    "light_level": 0.85,
    "light_warmth": 0.75,
    "sky_haze": 0.6,
    "mist_amount": 0.0,
    "mist_height": 0.35,
    "mist_motion": 0.25,
    "rain_amount": 1.0,
    "lightning_amount": 0.7,
    "mood": "stormy",
}


def timestamp_slug() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%z")


def wall_time() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def run_command(command: list[str], timeout: float = 30.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def load_production_constants() -> Any:
    spec = importlib.util.spec_from_file_location("tw_serve_latency_compare", SERVE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {SERVE_PATH}")
    module = importlib.util.module_from_spec(spec)
    old_cwd = Path.cwd()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            spec.loader.exec_module(module)
    finally:
        os.chdir(old_cwd)
    return module


def read_scene_context(scene_path: Path) -> str:
    scene_context = "No scene data available."
    try:
        scene = json.loads(scene_path.read_text())
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


def load_modifiers(modifiers_path: Path, modifier_schema: dict[str, Any]) -> dict[str, Any]:
    try:
        saved = json.loads(modifiers_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}
    current = dict(modifier_schema)
    current.update({
        key: value for key, value in saved.items()
        if key in modifier_schema and value is not None
    })
    return current


def build_payload(
    production: Any,
    command: str,
    scene_context: str,
    current_modifiers: dict[str, Any],
    *,
    model: str,
    stream: bool,
) -> dict[str, Any]:
    prompt = (
        f"Current scene objects: {scene_context}\n"
        f"Current modifiers: {json.dumps(current_modifiers)}\n"
        f"User request: {command}\n"
        "Return the modifier JSON:"
    )
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": production.SYSTEM_PROMPT},
            {"role": "user", "content": f"{prompt} /no_think"},
        ],
        "temperature": 0.3,
        "stream": stream,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def consume_stream(response: requests.Response, started: float) -> dict[str, Any]:
    first_data = None
    first_content = None
    last_content = None
    finish_reason = None
    content_chunks = 0
    parts: list[str] = []

    if response.encoding is None:
        response.encoding = "utf-8"

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


def strip_think_and_fences(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    return match.group(0).strip() if match else raw


def validate_stormy(content: str) -> dict[str, Any]:
    cleaned = strip_think_and_fences(content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return {
            "json_parse_success": False,
            "error": str(exc),
            "cleaned_content": cleaned,
            "parsed": None,
            "contract_ok": False,
            "semantic_ok": False,
        }

    expected_keys = set(EXPECTED_STORMY)
    actual_keys = set(parsed)
    numeric_deltas: dict[str, float] = {}
    for key, expected in EXPECTED_STORMY.items():
        if isinstance(expected, (int, float)) and isinstance(parsed.get(key), (int, float)):
            numeric_deltas[key] = float(parsed[key]) - float(expected)

    contract_ok = actual_keys == expected_keys
    semantic_ok = (
        contract_ok
        and isinstance(parsed.get("rain_amount"), (int, float))
        and parsed["rain_amount"] >= 0.8
        and isinstance(parsed.get("lightning_amount"), (int, float))
        and parsed["lightning_amount"] >= 0.5
        and isinstance(parsed.get("sky_haze"), (int, float))
        and parsed["sky_haze"] >= 0.35
        and isinstance(parsed.get("light_level"), (int, float))
        and parsed["light_level"] >= 0.5
        and "storm" in str(parsed.get("mood", "")).lower()
    )

    return {
        "json_parse_success": True,
        "cleaned_content": cleaned,
        "parsed": parsed,
        "contract_ok": contract_ok,
        "missing_keys": sorted(expected_keys - actual_keys),
        "extra_keys": sorted(actual_keys - expected_keys),
        "expected_reference": EXPECTED_STORMY,
        "numeric_deltas": numeric_deltas,
        "semantic_ok": semantic_ok,
    }


def process_inventory() -> dict[str, Any]:
    ps = run_command(["ps", "-axo", "pid,ppid,rss,vsz,comm,args"])
    lines = []
    for line in ps.get("stdout", "").splitlines():
        lower = line.lower()
        if any(token in lower for token in ("lm studio", "lmstudio", "llmworker", "llama", "qwen", "mlx")):
            lines.append(line)
    pids = []
    for line in lines:
        match = re.match(r"\s*(\d+)\s+", line)
        if match and "llmworker.js" in line:
            pids.append(int(match.group(1)))
    return {
        "matching_process_lines": lines,
        "llmworker_pids": pids,
    }


def process_memory_snapshot(label: str) -> dict[str, Any]:
    inventory = process_inventory()
    snapshots = []
    for pid in inventory["llmworker_pids"][:3]:
        snapshots.append({
            "pid": pid,
            "footprint_wide": run_command(["footprint", "--wide", str(pid)], timeout=45.0),
            "vmmap_summary": run_command(["vmmap", "-summary", str(pid)], timeout=45.0),
        })
    return {
        "label": label,
        "timestamp": wall_time(),
        "inventory": inventory,
        "memory_pressure": run_command(["memory_pressure"], timeout=20.0),
        "vm_stat": run_command(["vm_stat"], timeout=10.0),
        "processes": snapshots,
    }


def run_vm_stat_monitor(log_path: Path) -> subprocess.Popen[str]:
    handle = log_path.open("w")
    proc = subprocess.Popen(
        ["vm_stat", "1"],
        cwd=REPO_ROOT,
        text=True,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    proc._tw_log_handle = handle  # type: ignore[attr-defined]
    return proc


def stop_vm_stat_monitor(proc: subprocess.Popen[str]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    handle = getattr(proc, "_tw_log_handle", None)
    if handle is not None:
        handle.close()


def one_request(endpoint: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    started = time.perf_counter()
    started_wall = wall_time()
    try:
        with requests.post(endpoint, json=payload, stream=True, timeout=timeout_s) as response:
            headers_s = time.perf_counter() - started
            body = None
            if payload.get("stream"):
                streamed = consume_stream(response, started)
            else:
                body = response.text
                ended = time.perf_counter()
                streamed = {
                    "first_data_s": None,
                    "ttft_s": None,
                    "content_window_s": None,
                    "post_first_to_end_s": None,
                    "total_s": ended - started,
                    "content_chunks": None,
                    "finish_reason": None,
                    "content": body,
                }
            status_code = response.status_code
            response.raise_for_status()
    except requests.RequestException as exc:
        ended = time.perf_counter()
        return {
            "timestamp": started_wall,
            "ok": False,
            "error": str(exc),
            "total_s": ended - started,
        }

    validation = validate_stormy(streamed["content"] or "")
    return {
        "timestamp": started_wall,
        "ok": True,
        "http_status": status_code,
        "response_headers_s": headers_s,
        **streamed,
        "validation": validation,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--endpoint")
    parser.add_argument("--model")
    parser.add_argument("--command", default="make it stormy")
    parser.add_argument("--requests", type=int, default=1)
    parser.add_argument("--delay-s", type=float, default=0.0)
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-nonproduction-hash", action="store_true")
    parser.add_argument("--backend-note", default="")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    production = load_production_constants()
    endpoint = args.endpoint or production.LMSTUDIO_URL
    model = args.model or production.LMSTUDIO_MODEL

    scene_path = (RENDERING_DIR / production.SCENE_DESC_PATH).resolve()
    modifiers_path = (RENDERING_DIR / production.MODIFIERS_PATH).resolve()
    scene_context = read_scene_context(scene_path)
    current_modifiers = load_modifiers(modifiers_path, production.MODIFIER_SCHEMA)
    payload = build_payload(
        production,
        args.command.strip(),
        scene_context,
        current_modifiers,
        model=model,
        stream=True,
    )
    payload_hash = sha256_json(payload)

    is_production_control = (
        endpoint == production.LMSTUDIO_URL
        and model == production.LMSTUDIO_MODEL
    )
    if is_production_control and payload_hash != PRODUCTION_PAYLOAD_HASH:
        raise SystemExit(
            f"production payload hash drifted: {payload_hash} != {PRODUCTION_PAYLOAD_HASH}"
        )
    if not is_production_control and not args.allow_nonproduction_hash:
        raise SystemExit("non-production endpoint/model requires --allow-nonproduction-hash")

    run_id = f"{args.label}_{timestamp_slug()}"
    result = {
        "run_id": run_id,
        "timestamp": wall_time(),
        "repository": str(REPO_ROOT),
        "backend_note": args.backend_note,
        "endpoint": endpoint,
        "model": model,
        "command": args.command.strip(),
        "scene_context": scene_context,
        "current_modifiers": current_modifiers,
        "production_control": is_production_control,
        "payload_sha256": payload_hash,
        "payload": payload,
        "known_production_payload_sha256": PRODUCTION_PAYLOAD_HASH,
        "diagnostic_difference": "production request with stream changed false -> true for timing",
        "file_hashes": {
            "serve.py": sha256_file(SERVE_PATH),
            "scene_description.json": sha256_file(scene_path),
            "scene_modifiers.json": sha256_file(modifiers_path),
        },
        "lms_ps_json": run_command(["lms", "ps", "--json"]),
        "lms_runtime_ls": run_command(["lms", "runtime", "ls"]),
        "memory_before": process_memory_snapshot("before"),
        "requests": [],
        "memory_after": None,
        "dry_run": args.dry_run,
    }

    if not args.dry_run:
        for index in range(args.requests):
            if index > 0 and args.delay_s > 0:
                time.sleep(args.delay_s)
            vm_log = RESULTS_DIR / f"{run_id}_request_{index + 1:02d}_vm_stat.log"
            monitor = run_vm_stat_monitor(vm_log)
            try:
                request_result = one_request(endpoint, payload, args.timeout_s)
            finally:
                stop_vm_stat_monitor(monitor)
            request_result["vm_stat_log"] = str(vm_log)
            result["requests"].append(request_result)
            ttft = request_result.get("ttft_s")
            ttft_text = "none" if ttft is None else f"{ttft:.3f}s"
            print(
                f"{run_id} request {index + 1}/{args.requests}: "
                f"ttft={ttft_text} total={request_result.get('total_s'):.3f}s"
            )
        result["memory_after"] = process_memory_snapshot("after")

    out_path = RESULTS_DIR / f"{run_id}.json"
    with out_path.open("w") as handle:
        json.dump(result, handle, indent=2)
    print(out_path)


if __name__ == "__main__":
    main()
