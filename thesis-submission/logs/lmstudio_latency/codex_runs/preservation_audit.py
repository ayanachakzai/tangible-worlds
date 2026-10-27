"""Write a read-only preservation audit for the latency investigation.

This script is diagnostic-only. It creates audit JSON under codex_runs/results
and never writes production files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True


RUN_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = RUN_ROOT / "results"
REPO_ROOT = RUN_ROOT.parents[3]

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

KNOWN_HANDOFF_HASHES = {
    "phase3-tabletop/rendering/serve.py": (
        "5c00e629ff7723456ee9b946b78de6ba4f83ddfd15eb7e6eecf8e06db4bbbc55"
    ),
    "phase3-tabletop/mapping/scene_description.json": (
        "c8b6287b9ac307c4cb8f397d81d6d9cd10e3b699e9eebdc77cdfb3a5aad3f26c"
    ),
    "phase3-tabletop/conversation/scene_modifiers.json": (
        "7208e6516cb5aa6c30108d3a3942d4a98479e50deb3140caf3160a8f6fe18bff"
    ),
    "production_equivalent_streaming_payload": (
        "a74201574636fd0d567ed72e06e3a93c8a00d223fa253dc0cb7f35f976068438"
    ),
}


def run(command: list[str]) -> dict[str, object]:
    try:
        proc = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "command": command,
            "error": str(exc),
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }

    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(rel_path: str) -> dict[str, object]:
    path = REPO_ROOT / rel_path
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {
            "path": rel_path,
            "exists": False,
            "sha256": None,
            "size_bytes": None,
            "mtime_ns": None,
        }

    return {
        "path": rel_path,
        "exists": path.is_file(),
        "sha256": sha256_file(path),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, choices=["before", "after"])
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%z")
    audit = {
        "label": args.label,
        "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "repository": str(REPO_ROOT),
        "write_boundary": str(RUN_ROOT),
        "known_handoff_hashes": KNOWN_HANDOFF_HASHES,
        "commands": {
            "git_status_short_branch": run(["git", "status", "--short", "--branch"]),
            "git_rev_parse_head": run(["git", "rev-parse", "HEAD"]),
            "lms_ps_json": run(["lms", "ps", "--json"]),
            "sysctl_iogpu_wired_limit_mb": run(["sysctl", "iogpu.wired_limit_mb"]),
        },
        "files": [file_record(path) for path in IMMUTABLE_FILES],
    }

    out_path = RESULTS_DIR / f"audit_{args.label}_{stamp}.json"
    with out_path.open("w") as handle:
        json.dump(audit, handle, indent=2)

    print(out_path)


if __name__ == "__main__":
    main()
