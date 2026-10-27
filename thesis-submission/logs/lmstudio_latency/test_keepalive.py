"""test whether tiny periodic qwen calls keep the lm studio working set hot.

this is diagnostic-only. it does not edit production files or become part of
participant startup. it uses one tiny seed request, then one tiny request every
30 seconds for five minutes, then one production-sized streamed probe.

usage:
    python test_keepalive.py
"""

import json
import time
from datetime import datetime

import requests

import capture_request as capture


keepalive_interval_s = 30.0
keepalive_duration_s = 300.0
keepalive_prompt = "say ok /no_think"


def wall_time():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def build_keepalive_payload(production):
    # this request is intentionally tiny. max_tokens=1 is supported by lm
    # studio's openai-compatible chat endpoint and limits diagnostic decode work.
    # ref: 26 aug 2026. supported /v1/chat/completions payload parameters.
    # https://lmstudio.ai/docs/developer/openai-compat/chat-completions
    return {
        "model": production.LMSTUDIO_MODEL,
        "messages": [{"role": "user", "content": keepalive_prompt}],
        "temperature": 0.3,
        "max_tokens": 1,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def run_streamed(production, payload):
    # ref: 26 aug 2026. perf_counter is monotonic for elapsed-time measurement.
    # https://docs.python.org/3/library/time.html#time.perf_counter
    started = time.perf_counter()
    started_wall = wall_time()

    try:
        # ref: 26 aug 2026. requests stream=True keeps the response body lazy.
        # https://requests.readthedocs.io/en/latest/user/advanced/#body-content-workflow
        with requests.post(
            production.LMSTUDIO_URL,
            json=payload,
            stream=True,
            timeout=60,
        ) as response:
            headers_s = time.perf_counter() - started
            response.raise_for_status()
            streamed = capture.consume_stream(response, started)
            status_code = response.status_code
    except requests.RequestException as exc:
        raise RuntimeError(f"lm studio request failed: {exc}") from exc

    return {
        "timestamp": started_wall,
        "http_status": status_code,
        "response_headers_s": headers_s,
        **streamed,
    }


def print_probe(label, result):
    ttft = result["ttft_s"]
    ttft_text = "none" if ttft is None else f"{ttft:.3f}s"
    print(
        f"{label}: {result['timestamp']}  "
        f"ttft={ttft_text}  total={result['total_s']:.3f}s"
    )


def main():
    if not capture.serve_path.exists():
        raise SystemExit(f"missing production file: {capture.serve_path}")

    production = capture.load_production_constants()
    scene_path = (capture.rendering_dir / production.SCENE_DESC_PATH).resolve()
    modifiers_path = (capture.rendering_dir / production.MODIFIERS_PATH).resolve()

    scene_context = capture.read_scene_context(scene_path)
    current_modifiers = capture.load_modifiers(
        modifiers_path,
        production.MODIFIER_SCHEMA,
    )
    production_payload = capture.build_payload(
        production,
        "make it stormy",
        scene_context,
        current_modifiers,
    )
    keepalive_payload = build_keepalive_payload(production)

    # the final probe must stay identical to capture_request.py's verified
    # production-equivalent request shape. the keep-alive is the only request
    # allowed to add max_tokens.
    if "max_tokens" in production_payload or "stream_options" in production_payload:
        raise RuntimeError("production probe drifted from capture_request.py")
    if keepalive_payload.get("max_tokens") != 1:
        raise RuntimeError("keep-alive must remain a one-token residency probe")

    starting_hashes = {
        "production_file_sha256": capture.sha256_file(capture.serve_path),
        "scene_file_sha256": capture.sha256_file(scene_path),
        "modifiers_file_sha256": capture.sha256_file(modifiers_path),
        "production_payload_sha256": capture.sha256_json(production_payload),
        "keepalive_payload_sha256": capture.sha256_json(keepalive_payload),
    }

    print("diagnostic only: production files will not be modified")
    print(f"model: {production.LMSTUDIO_MODEL}")
    print(f"keep-alive interval: {keepalive_interval_s:.0f}s")
    print(f"keep-alive window: {keepalive_duration_s / 60:.0f} minutes")
    print(f"production payload sha256: {starting_hashes['production_payload_sha256']}")
    print()

    # seed request establishes a hot worker before the timed maintenance window.
    # this is diagnostic-only and must not be copied into participant startup.
    seed = run_streamed(production, keepalive_payload)
    print_probe("seed", seed)

    keepalives = []
    maintenance_started = time.perf_counter()
    next_due = maintenance_started + keepalive_interval_s
    number = 1

    # schedule from the maintenance-window start, never concurrently. if one
    # request overruns its slot, the next starts only after it has completed.
    # ref: 26 aug 2026. sleep suspends the current thread for the given duration.
    # https://docs.python.org/3/library/time.html#time.sleep
    while next_due <= maintenance_started + keepalive_duration_s:
        delay = next_due - time.perf_counter()
        if delay > 0:
            time.sleep(delay)

        result = run_streamed(production, keepalive_payload)
        result["scheduled_offset_s"] = number * keepalive_interval_s
        keepalives.append(result)
        print_probe(f"keepalive {number:02d}", result)

        number += 1
        next_due = maintenance_started + number * keepalive_interval_s

    ending_hashes = {
        "production_file_sha256": capture.sha256_file(capture.serve_path),
        "scene_file_sha256": capture.sha256_file(scene_path),
        "modifiers_file_sha256": capture.sha256_file(modifiers_path),
    }
    state_unchanged = all(
        ending_hashes[key] == starting_hashes[key]
        for key in ending_hashes
    )

    if not state_unchanged:
        raise RuntimeError(
            "production/scene/modifier files changed during the test; "
            "final probe withheld because the comparison would be confounded"
        )

    final_probe = run_streamed(production, production_payload)
    print_probe("final production probe", final_probe)

    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%z")
    capture.results_dir.mkdir(exist_ok=True)
    result_path = capture.results_dir / f"keepalive_{stamp}.json"

    result = {
        "timestamp": wall_time(),
        "test": "30-second tiny keep-alive for five minutes",
        "diagnostic_only": True,
        "model": production.LMSTUDIO_MODEL,
        "endpoint": production.LMSTUDIO_URL,
        "keepalive_interval_s": keepalive_interval_s,
        "keepalive_duration_s": keepalive_duration_s,
        "keepalive_count": len(keepalives),
        "keepalive_payload": keepalive_payload,
        "production_payload": production_payload,
        "starting_hashes": starting_hashes,
        "ending_hashes": ending_hashes,
        "state_unchanged": state_unchanged,
        "seed": seed,
        "keepalives": keepalives,
        "final_production_probe": final_probe,
    }

    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    print()
    print(f"result: {result_path}")
    print("production files changed: no")


if __name__ == "__main__":
    main()
