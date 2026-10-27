"""Final bounded MLX latency campaign helper.

Diagnostic-only. Writes only under this final_mlx_campaign directory.
It does not call Tangible Worlds application endpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import signal
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
REPO_ROOT = RUN_ROOT.parents[5]
PHASE3_ROOT = REPO_ROOT / "phase3-tabletop"
RENDERING_DIR = PHASE3_ROOT / "rendering"
SERVE_PATH = RENDERING_DIR / "serve.py"

PRODUCTION_PAYLOAD_HASH = "a74201574636fd0d567ed72e06e3a93c8a00d223fa253dc0cb7f35f976068438"

IMMUTABLE_FILES = [
    "phase3-tabletop/rendering/serve.py",
    "phase3-tabletop/rendering/index.html",
    "phase3-tabletop/rendering/voice_capture_worklet.js",
    "phase3-tabletop/mapping/compute_scene.py",
    "phase3-tabletop/mapping/scene_description.json",
    "phase3-tabletop/tracking/track_tabletop.py",
    "phase3-tabletop/tracking/scene_state.json",
    "phase3-tabletop/conversation/converse.py",
    "phase3-tabletop/conversation/scene_modifiers.json",
    "phase3-tabletop/conversation/conversation_log.json",
    "phase3-tabletop/rendering/assignments.json",
    "phase3-tabletop/rendering/relations.json",
    "phase3-tabletop/rendering/mesh_rotations.json",
    "phase3-tabletop/tracking/calibration_trigger.json",
    "phase3-tabletop/tracking/calibration_state.json",
    "phase6-voice/transcribe_server.py",
    "phase2-generation-sdxlturbo/generate_image.py",
    "phase3-tabletop/PROJECT_AUDIT.md",
    "phase3-tabletop/RUNBOOK.md",
    "design-diary/DESIGN_DIARY.md",
]

EXPECTED_KEYS = {
    "sky_elevation",
    "light_elevation",
    "light_azimuth",
    "light_level",
    "light_warmth",
    "sky_haze",
    "mist_amount",
    "mist_height",
    "mist_motion",
    "rain_amount",
    "lightning_amount",
    "mood",
}

RANGES = {
    "sky_elevation": (-90.0, 90.0),
    "light_elevation": (-90.0, 90.0),
    "light_azimuth": (0.0, 360.0),
    "light_level": (0.0, 1.0),
    "light_warmth": (0.0, 1.0),
    "sky_haze": (0.0, 1.0),
    "mist_amount": (0.0, 1.0),
    "mist_height": (0.0, 1.0),
    "mist_motion": (0.0, 1.0),
    "rain_amount": (0.0, 1.0),
    "lightning_amount": (0.0, 1.0),
}


def timestamp_slug() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%z")


def wall_time() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def write_new_json(path: Path, data: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    with path.open("w") as handle:
        json.dump(data, handle, indent=2)


def write_new_text(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(text)


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


def process_inventory() -> dict[str, Any]:
    ps = run_command(["ps", "-axo", "pid,ppid,rss,vsz,comm,args"], timeout=10)
    lines = []
    llmworker_pids: list[int] = []
    if ps["stdout"]:
        for line in ps["stdout"].splitlines():
            haystack = line.lower()
            if any(token in haystack for token in ["lm studio", "llmworker.js", "lms ", "llama-server"]):
                lines.append(line)
            if "llmworker.js" in line:
                parts = line.split(None, 1)
                if parts and parts[0].isdigit():
                    llmworker_pids.append(int(parts[0]))
    return {
        "ps": ps,
        "matching_process_lines": lines,
        "llmworker_pids": sorted(set(llmworker_pids)),
    }


def port_inventory() -> dict[str, Any]:
    return {
        "all_listeners": run_command(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], timeout=10),
        "port_1234": run_command(["lsof", "-nP", "-iTCP:1234", "-sTCP:LISTEN"], timeout=10),
        "port_1235": run_command(["lsof", "-nP", "-iTCP:1235", "-sTCP:LISTEN"], timeout=10),
        "port_8080": run_command(["lsof", "-nP", "-iTCP:8080", "-sTCP:LISTEN"], timeout=10),
    }


def worker_memory() -> list[dict[str, Any]]:
    inventory = process_inventory()
    workers = []
    for pid in inventory["llmworker_pids"]:
        workers.append({
            "pid": pid,
            "footprint_wide": run_command(["footprint", "--wide", str(pid)], timeout=30),
            "vmmap_summary": run_command(["vmmap", "-summary", str(pid)], timeout=30),
        })
    return workers


def capture_state(label: str) -> dict[str, Any]:
    files = []
    for rel in IMMUTABLE_FILES:
        path = REPO_ROOT / rel
        files.append({
            "path": rel,
            "exists": path.exists(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size if path.exists() else None,
            "mtime_ns": path.stat().st_mtime_ns if path.exists() else None,
        })
    return {
        "label": label,
        "timestamp": wall_time(),
        "repository": str(REPO_ROOT),
        "write_boundary": str(RUN_ROOT),
        "known_handoff_hashes": {
            "phase3-tabletop/rendering/serve.py": "5c00e629ff7723456ee9b946b78de6ba4f83ddfd15eb7e6eecf8e06db4bbbc55",
            "phase3-tabletop/mapping/scene_description.json": "c8b6287b9ac307c4cb8f397d81d6d9cd10e3b699e9eebdc77cdfb3a5aad3f26c",
            "phase3-tabletop/conversation/scene_modifiers.json": "7208e6516cb5aa6c30108d3a3942d4a98479e50deb3140caf3160a8f6fe18bff",
            "production_equivalent_payload": PRODUCTION_PAYLOAD_HASH,
        },
        "files": files,
        "commands": {
            "git_status_porcelain_v1": run_command(["git", "status", "--porcelain=v1"], timeout=10),
            "git_rev_parse_head": run_command(["git", "rev-parse", "HEAD"], timeout=10),
            "lms_ps_json": run_command(["lms", "ps", "--json"], timeout=20),
            "lms_runtime_ls": run_command(["lms", "runtime", "ls"], timeout=20),
            "lms_ls": run_command(["lms", "ls"], timeout=20),
            "lms_ls_llm": run_command(["lms", "ls", "--llm"], timeout=20),
            "sysctl_iogpu_wired_limit_mb": run_command(["sysctl", "iogpu.wired_limit_mb"], timeout=10),
            "memory_pressure": run_command(["memory_pressure"], timeout=30),
            "vm_stat": run_command(["vm_stat"], timeout=10),
        },
        "process_inventory": process_inventory(),
        "port_inventory": port_inventory(),
        "worker_memory": worker_memory(),
    }


def load_production_constants() -> Any:
    spec = importlib.util.spec_from_file_location("tw_serve_final_mlx_campaign", SERVE_PATH)
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


def build_payload(command: str, *, model: str | None = None, stream: bool = True) -> dict[str, Any]:
    production = load_production_constants()
    scene_path = (RENDERING_DIR / production.SCENE_DESC_PATH).resolve()
    modifiers_path = (RENDERING_DIR / production.MODIFIERS_PATH).resolve()
    scene_context = read_scene_context(scene_path)
    current_modifiers = load_modifiers(modifiers_path, production.MODIFIER_SCHEMA)
    prompt = (
        f"Current scene objects: {scene_context}\n"
        f"Current modifiers: {json.dumps(current_modifiers)}\n"
        f"User request: {command.strip()}\n"
        "Return the modifier JSON:"
    )
    return {
        "model": model or production.LMSTUDIO_MODEL,
        "messages": [
            {"role": "system", "content": production.SYSTEM_PROMPT},
            {"role": "user", "content": f"{prompt} /no_think"},
        ],
        "temperature": 0.3,
        "stream": stream,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def strip_think_and_fences(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    return match.group(0).strip() if match else raw


def validate_output(command: str, content: str, before_modifiers: dict[str, Any] | None = None) -> dict[str, Any]:
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
            "range_ok": False,
            "semantic_direction_ok": False,
        }

    actual_keys = set(parsed)
    missing = sorted(EXPECTED_KEYS - actual_keys)
    extra = sorted(actual_keys - EXPECTED_KEYS)
    range_errors = []
    for key, (lo, hi) in RANGES.items():
        value = parsed.get(key)
        if not isinstance(value, (int, float)) or not (lo <= float(value) <= hi):
            range_errors.append({"key": key, "value": value, "range": [lo, hi]})
    if not isinstance(parsed.get("mood"), str):
        range_errors.append({"key": "mood", "value": parsed.get("mood"), "range": "string"})

    command_l = command.lower()
    semantic_checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: Any) -> None:
        semantic_checks.append({"name": name, "passed": bool(passed), "detail": detail})

    if "storm" in command_l:
        add("storm_has_rain", isinstance(parsed.get("rain_amount"), (int, float)) and parsed["rain_amount"] >= 0.5, parsed.get("rain_amount"))
        add("storm_has_lightning", isinstance(parsed.get("lightning_amount"), (int, float)) and parsed["lightning_amount"] >= 0.3, parsed.get("lightning_amount"))
        add("storm_mood", "storm" in str(parsed.get("mood", "")).lower(), parsed.get("mood"))
    if "warm" in command_l and "sunset" in command_l:
        add("sunset_warmth", isinstance(parsed.get("light_warmth"), (int, float)) and parsed["light_warmth"] >= 0.65, parsed.get("light_warmth"))
        add("sunset_haze", isinstance(parsed.get("sky_haze"), (int, float)) and parsed["sky_haze"] >= 0.3, parsed.get("sky_haze"))
        add("sunset_low_light", isinstance(parsed.get("light_elevation"), (int, float)) and parsed["light_elevation"] <= 25, parsed.get("light_elevation"))
    if "moonlit" in command_l or "night" in command_l:
        add("night_sky_below_horizon", isinstance(parsed.get("sky_elevation"), (int, float)) and parsed["sky_elevation"] < 0, parsed.get("sky_elevation"))
        add("night_no_mist", parsed.get("mist_amount") == 0, parsed.get("mist_amount"))
        add("night_no_rain", parsed.get("rain_amount") == 0, parsed.get("rain_amount"))
        add("night_no_lightning", parsed.get("lightning_amount") == 0, parsed.get("lightning_amount"))
    if "mist" in command_l and ("thicker" in command_l or "active" in command_l):
        add("mist_amount_rises", isinstance(parsed.get("mist_amount"), (int, float)) and parsed["mist_amount"] >= 0.5, parsed.get("mist_amount"))
        add("mist_motion_rises", isinstance(parsed.get("mist_motion"), (int, float)) and parsed["mist_motion"] >= 0.5, parsed.get("mist_motion"))
        if before_modifiers:
            for key in ["light_elevation", "light_azimuth", "light_level", "light_warmth"]:
                add(f"preserve_{key}", parsed.get(key) == before_modifiers.get(key), {"before": before_modifiers.get(key), "after": parsed.get(key)})
    if "remove" in command_l and "rain" in command_l and "lightning" in command_l:
        add("remove_rain_zero", parsed.get("rain_amount") == 0, parsed.get("rain_amount"))
        add("remove_lightning_zero", parsed.get("lightning_amount") == 0, parsed.get("lightning_amount"))

    semantic_direction_ok = all(item["passed"] for item in semantic_checks) if semantic_checks else True
    return {
        "json_parse_success": True,
        "cleaned_content": cleaned,
        "parsed": parsed,
        "contract_ok": not missing and not extra,
        "missing_keys": missing,
        "extra_keys": extra,
        "range_ok": not range_errors,
        "range_errors": range_errors,
        "semantic_checks": semantic_checks,
        "semantic_direction_ok": semantic_direction_ok,
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


def start_vm_stat_log(path: Path) -> subprocess.Popen[str]:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    handle = path.open("w")
    proc = subprocess.Popen(
        ["vm_stat", "1"],
        cwd=REPO_ROOT,
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    proc._codex_log_handle = handle  # type: ignore[attr-defined]
    return proc


def stop_vm_stat_log(proc: subprocess.Popen[str]) -> None:
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    handle = getattr(proc, "_codex_log_handle", None)
    if handle is not None:
        handle.close()


def one_request(
    *,
    label: str,
    command: str,
    endpoint: str,
    model: str,
    timeout: float,
    index: int,
    before_modifiers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_results_dir()
    payload = build_payload(command, model=model, stream=True)
    vm_log = RESULTS_DIR / f"{label}_request_{index:02d}_vm_stat.log"
    before_state = capture_state(f"{label}_request_{index:02d}_before")
    vm_proc = start_vm_stat_log(vm_log)
    time.sleep(0.2)
    started = time.perf_counter()
    try:
        with requests.post(endpoint, json=payload, stream=True, timeout=timeout) as response:
            headers_s = time.perf_counter() - started
            status_code = response.status_code
            response.raise_for_status()
            streamed = consume_stream(response, started)
    finally:
        stop_vm_stat_log(vm_proc)
    after_state = capture_state(f"{label}_request_{index:02d}_after")
    result = {
        "index": index,
        "timestamp": wall_time(),
        "endpoint": endpoint,
        "model": model,
        "command": command,
        "payload_sha256": sha256_json(payload),
        "known_production_payload_sha256": PRODUCTION_PAYLOAD_HASH,
        "payload": payload,
        "diagnostic_difference": "production payload with stream changed false -> true only",
        "http_status": status_code,
        "response_headers_s": headers_s,
        **streamed,
        "validation": validate_output(command, streamed.get("content", ""), before_modifiers),
        "vm_stat_log": str(vm_log),
        "state_before": before_state,
        "state_after": after_state,
    }
    return result


def command_audit(args: argparse.Namespace) -> None:
    ensure_results_dir()
    stamp = timestamp_slug()
    path = RESULTS_DIR / f"audit_{args.label}_{stamp}.json"
    data = capture_state(args.label)
    write_new_json(path, data)
    print(path)


def command_payload(args: argparse.Namespace) -> None:
    payload = build_payload(args.command, model=args.model, stream=True)
    print(sha256_json(payload))
    if args.show:
        print(json.dumps(payload, indent=2))


def command_request(args: argparse.Namespace) -> None:
    ensure_results_dir()
    label = f"{args.label}_{timestamp_slug()}"
    before_modifiers = None
    try:
        production = load_production_constants()
        modifiers_path = (RENDERING_DIR / production.MODIFIERS_PATH).resolve()
        before_modifiers = load_modifiers(modifiers_path, production.MODIFIER_SCHEMA)
    except Exception:
        before_modifiers = None
    requests_out = []
    for index in range(1, args.requests + 1):
        result = one_request(
            label=label,
            command=args.command,
            endpoint=args.endpoint,
            model=args.model,
            timeout=args.timeout,
            index=index,
            before_modifiers=before_modifiers,
        )
        requests_out.append(result)
        print(
            f"{label} request {index}/{args.requests}: "
            f"ttft={result['ttft_s']:.3f}s total={result['total_s']:.3f}s"
        )
        if args.delay_s and index < args.requests:
            time.sleep(args.delay_s)
    output = {
        "run_id": label,
        "timestamp": wall_time(),
        "requests": requests_out,
    }
    output_path = RESULTS_DIR / f"{label}.json"
    write_new_json(output_path, output)
    print(output_path)


def command_compare_audits(args: argparse.Namespace) -> None:
    before = json.loads(Path(args.before).read_text())
    after = json.loads(Path(args.after).read_text())
    before_files = {item["path"]: item for item in before["files"]}
    after_files = {item["path"]: item for item in after["files"]}
    changes = []
    for path, before_item in before_files.items():
        after_item = after_files.get(path)
        if after_item is None:
            changes.append({"path": path, "before": before_item, "after": None})
        elif before_item.get("sha256") != after_item.get("sha256"):
            changes.append({
                "path": path,
                "before_sha256": before_item.get("sha256"),
                "after_sha256": after_item.get("sha256"),
            })
    result = {
        "timestamp": wall_time(),
        "before": args.before,
        "after": args.after,
        "hash_changes": changes,
        "git_status_before": before["commands"]["git_status_porcelain_v1"]["stdout"],
        "git_status_after": after["commands"]["git_status_porcelain_v1"]["stdout"],
        "lms_ps_before": before["commands"]["lms_ps_json"]["stdout"],
        "lms_ps_after": after["commands"]["lms_ps_json"]["stdout"],
        "sysctl_before": before["commands"]["sysctl_iogpu_wired_limit_mb"]["stdout"],
        "sysctl_after": after["commands"]["sysctl_iogpu_wired_limit_mb"]["stdout"],
    }
    path = RESULTS_DIR / f"audit_compare_{timestamp_slug()}.json"
    write_new_json(path, result)
    print(json.dumps(result, indent=2))
    print(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command_name", required=True)

    audit = sub.add_parser("audit")
    audit.add_argument("--label", required=True)
    audit.set_defaults(func=command_audit)

    payload = sub.add_parser("payload")
    payload.add_argument("--command", default="make it stormy")
    payload.add_argument("--model", default="qwen/qwen3-8b")
    payload.add_argument("--show", action="store_true")
    payload.set_defaults(func=command_payload)

    request = sub.add_parser("request")
    request.add_argument("--label", required=True)
    request.add_argument("--command", default="make it stormy")
    request.add_argument("--endpoint", default="http://127.0.0.1:1234/v1/chat/completions")
    request.add_argument("--model", default="qwen/qwen3-8b")
    request.add_argument("--requests", type=int, default=1)
    request.add_argument("--delay-s", type=float, default=0.0)
    request.add_argument("--timeout", type=float, default=90.0)
    request.set_defaults(func=command_request)

    compare = sub.add_parser("compare-audits")
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)
    compare.set_defaults(func=command_compare_audits)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
