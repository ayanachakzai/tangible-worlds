#!/usr/bin/env python3

import argparse
import html
import json
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CORPUS_PATH = ROOT / "corpus_dev.json"
AUDIO_DIR = ROOT / "audio_dev"
RESULTS_DIR = ROOT / "results"

SMOKE_IDS = {
    "assign_suspension_bridge_huge_t1",
    "assign_coffee_mug_miniature_t1",
    "robust_mm_petrol_station",
    "robust_hmm_bus_shelter",
    "robust_quiet_delivery",
    "confirm_yes_t1",
    "confirm_no_t1",
    "confirm_ambiguous_yes_no",
    "atmosphere_golden_hour",
    "adversarial_silence_t1",
    "adversarial_silence_t2",
    "adversarial_prop_noise_t1",
    "adversarial_aborted_press_t1",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the frozen audio corpus through a local ASR server."
    )
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8091",
        help="Base URL of the local NeMo-Speech.cpp server.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run all 102 recordings. Without this flag, run the 13-file smoke test.",
    )
    return parser.parse_args()


def expanded_corpus():
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    rows = []
    for template in corpus["templates"]:
        takes = template.get("takes", 1)
        for take in range(1, takes + 1):
            row = dict(template)
            if takes > 1:
                row["recording_id"] = f"{template['id']}_t{take}"
            else:
                row["recording_id"] = template["id"]
            rows.append(row)
    return rows


def check_server(server):
    request = urllib.request.Request(f"{server}/ready")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Parakeet is not ready. Start ./start_parakeet_server.sh in another Terminal."
        ) from error
    if not payload.get("ready"):
        raise RuntimeError(f"The server responded but is not ready: {payload}")
    return payload


def multipart_body(wav_path):
    boundary = f"----bakeoff-{time.time_ns()}"
    parts = []

    def add_text(name, value):
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        parts.append(str(value).encode())
        parts.append(b"\r\n")

    add_text("model", "parakeet-tdt-0.6b-v3")
    add_text("language", "en")
    add_text("response_format", "json")
    add_text("automatic_punctuation", "false")

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        (
            f'Content-Disposition: form-data; name="file"; '
            f'filename="{wav_path.name}"\r\n'
        ).encode()
    )
    parts.append(b"Content-Type: audio/wav\r\n\r\n")
    parts.append(wav_path.read_bytes())
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(parts)


def transcribe(server, wav_path):
    boundary, body = multipart_body(wav_path)
    request = urllib.request.Request(
        f"{server}/v1/audio/transcriptions",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {message}") from error
    latency_s = time.perf_counter() - started
    return str(payload.get("text", "")).strip(), latency_s


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = int(round((len(ordered) - 1) * fraction))
    return ordered[position]


def write_html(path, run):
    rows = []
    for result in run["results"]:
        transcript = result.get("transcript", "")
        error = result.get("error")
        status = "error" if error else ("empty" if not transcript else "result")
        displayed = error or transcript or "[EMPTY]"
        audio_path = f"../audio_dev/{result['recording_id']}.wav"
        rows.append(
            "<tr>"
            f"<td>{html.escape(result['recording_id'])}</td>"
            f"<td>{html.escape(result['category'])}</td>"
            f"<td>{html.escape(result['reference']) or '[EMPTY]'}</td>"
            f"<td class='{status}'>{html.escape(displayed)}</td>"
            f"<td>{result.get('latency_s', 0):.3f}</td>"
            f"<td><audio controls preload='none' src='{html.escape(audio_path)}'></audio></td>"
            "</tr>"
        )

    summary = run["summary"]
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parakeet bake-off results</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #1d1d1f; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ border-bottom: 1px solid #ddd; padding: 9px; text-align: left; vertical-align: top; }}
th {{ position: sticky; top: 0; background: #fff; }}
.empty {{ color: #666; }}
.error {{ color: #b00020; }}
audio {{ width: 190px; height: 32px; }}
.summary {{ display: flex; gap: 22px; margin: 18px 0; flex-wrap: wrap; }}
.summary div {{ background: #f4f4f5; border-radius: 8px; padding: 10px 14px; }}
</style>
</head>
<body>
<h1>Parakeet TDT 0.6B v3 baseline</h1>
<p>Raw output, English selected, punctuation disabled, no prompt or vocabulary boost.</p>
<div class="summary">
<div>Files: {summary['completed']}/{summary['requested']}</div>
<div>Median latency: {summary['median_latency_s']:.3f} s</div>
<div>P95 latency: {summary['p95_latency_s']:.3f} s</div>
<div>Errors: {summary['errors']}</div>
</div>
<table>
<thead><tr><th>ID</th><th>Category</th><th>Reference</th><th>Transcript</th><th>Seconds</th><th>Audio</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def main():
    args = parse_args()
    server = args.server.rstrip("/")
    readiness = check_server(server)
    rows = expanded_corpus()
    if not args.full:
        rows = [row for row in rows if row["recording_id"] in SMOKE_IDS]

    RESULTS_DIR.mkdir(exist_ok=True)
    results = []
    total = len(rows)
    print(f"Server ready: {readiness}")
    print(f"Running {'full corpus' if args.full else 'smoke test'}: {total} files\n")

    for number, row in enumerate(rows, start=1):
        recording_id = row["recording_id"]
        wav_path = AUDIO_DIR / f"{recording_id}.wav"
        result = {
            "recording_id": recording_id,
            "category": row["category"],
            "reference": row["reference"],
            "expected_route": row["expected_route"],
        }
        try:
            transcript, latency_s = transcribe(server, wav_path)
            result["transcript"] = transcript
            result["latency_s"] = round(latency_s, 6)
            shown = transcript if transcript else "[EMPTY]"
            print(f"[{number:03d}/{total:03d}] {recording_id}")
            print(f"  {latency_s:.3f} s | {shown}")
        except Exception as error:
            result["transcript"] = ""
            result["latency_s"] = 0.0
            result["error"] = str(error)
            print(f"[{number:03d}/{total:03d}] {recording_id}")
            print(f"  ERROR | {error}")
        results.append(result)

    latencies = [row["latency_s"] for row in results if not row.get("error")]
    summary = {
        "requested": total,
        "completed": len(latencies),
        "errors": sum(1 for row in results if row.get("error")),
        "median_latency_s": statistics.median(latencies) if latencies else 0.0,
        "p95_latency_s": percentile(latencies, 0.95) or 0.0,
    }
    run = {
        "model": "nvidia/parakeet-tdt-0.6b-v3",
        "runtime": "NVIDIA NeMo-Speech.cpp",
        "settings": {
            "language": "en",
            "automatic_punctuation": False,
            "prompt": None,
            "speech_contexts": None,
        },
        "scope": "full" if args.full else "smoke",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "server_readiness": readiness,
        "summary": summary,
        "results": results,
    }

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"parakeet_tdt_0.6b_v3_baseline_{run['scope']}_{stamp}"
    json_path = RESULTS_DIR / f"{stem}.json"
    html_path = RESULTS_DIR / f"{stem}.html"
    json_path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    write_html(html_path, run)

    print("\nFinished.")
    print(f"JSON: {json_path}")
    print(f"Open this report in your browser: {html_path}")


if __name__ == "__main__":
    main()
