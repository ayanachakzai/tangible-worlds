#!/usr/bin/env python3
"""Run the candidate against the actual server parser and an isolated cache."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types


STUDY = Path(__file__).resolve().parent
RENDERING = STUDY.parent
SERVER = RENDERING / "serve.py"
CAR_FIXTURE = RENDERING / "generated_meshes" / "a-car.glb"
CANDIDATE = STUDY / "candidate_normalizer.mjs"


def js_normalize(meaning: str) -> str:
    source = (
        f"import {{ normalizeVoiceScaleAlias }} from {json.dumps(CANDIDATE.as_uri())};"
        f"process.stdout.write(normalizeVoiceScaleAlias({json.dumps(meaning)}));"
    )
    return subprocess.check_output(
        ["node", "--input-type=module", "--eval", source], text=True
    )


def main() -> None:
    if not CAR_FIXTURE.exists():
        raise SystemExit(f"missing existing cache fixture: {CAR_FIXTURE}")

    voice_original = "a car scaled tiny"
    current_correct = "a car scale tiny"
    voice_sent = js_normalize(voice_original)

    with tempfile.TemporaryDirectory(prefix="voice-scaled-alias-") as temp_name:
        temp = Path(temp_name)
        isolated_server = temp / "serve_isolated.py"
        shutil.copy2(SERVER, isolated_server)
        cache_dir = temp / "generated_meshes"
        cache_dir.mkdir()
        shutil.copy2(CAR_FIXTURE, cache_dir / "a-car.glb")

        previous_cwd = Path.cwd()
        os.chdir(temp)
        try:
            # The host's system Python lacks requests.  Network paths are not
            # exercised here, so a process-local placeholder lets the actual
            # parser/cache code import without adding a dependency.
            sys.modules.setdefault("requests", types.ModuleType("requests"))
            spec = importlib.util.spec_from_file_location("serve_isolated", isolated_server)
            if spec is None or spec.loader is None:
                raise RuntimeError("could not load isolated server")
            server = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(server)

            alias_record = server.parse_marked_scale(voice_sent)
            correct_record = server.parse_marked_scale(current_correct)
            typed_record = server.parse_marked_scale(voice_original)
            alias_slug = server._slugify(alias_record["generation_meaning"])
            correct_slug = server._slugify(correct_record["generation_meaning"])

            generator_calls = []
            server._generate_mesh_local = lambda *args, **kwargs: generator_calls.append((args, kwargs))
            server._assignments = {
                "2": {
                    **alias_record,
                    "status": "generating",
                    "rotation": {"x": 0, "y": 0, "z": 0},
                }
            }
            cache_stdout = io.StringIO()
            with contextlib.redirect_stdout(cache_stdout):
                server._local_generate_object("2", voice_sent, alias_record["generation_meaning"])
            cache_result = server._assignments["2"]

            result = {
                "production_server_sha256_source": subprocess.check_output(
                    ["shasum", "-a", "256", str(SERVER)], text=True
                ).split()[0],
                "existing_fixture": str(CAR_FIXTURE),
                "existing_fixture_size_bytes": CAR_FIXTURE.stat().st_size,
                "voice_transcript": "object two is a car scaled tiny",
                "voice_original_meaning": voice_original,
                "normalized_assignment_meaning": voice_sent,
                "existing_correct_assignment_meaning": current_correct,
                "alias_record": alias_record,
                "correct_record": correct_record,
                "typed_record": typed_record,
                "alias_cache_slug": alias_slug,
                "correct_cache_slug": correct_slug,
                "cache_file": str(cache_dir / f"{alias_slug}.glb"),
                "cache_file_exists": (cache_dir / f"{alias_slug}.glb").exists(),
                "generator_call_count": len(generator_calls),
                "final_assignment_status": cache_result.get("status"),
                "final_mesh_url": cache_result.get("mesh_url"),
                "cache_path_stdout": cache_stdout.getvalue().strip(),
                "same_object_repeat_is_server_noop": voice_sent == current_correct,
            }
            result["pass"] = all([
                voice_sent == current_correct,
                alias_record["generation_meaning"] == "a car",
                correct_record["generation_meaning"] == "a car",
                alias_record["target_size"] == 0.35,
                correct_record["target_size"] == 0.35,
                alias_slug == correct_slug == "a-car",
                result["cache_file_exists"],
                result["generator_call_count"] == 0,
                cache_result.get("status") == "ready",
                typed_record["meaning"] == voice_original,
                typed_record["generation_meaning"] == voice_original,
                typed_record["target_size"] == 1.0,
                typed_record["scale_source"] == "neutral_default",
            ])
            print(json.dumps(result, indent=2))
        finally:
            os.chdir(previous_cwd)


if __name__ == "__main__":
    main()
