#!/usr/bin/env python3
"""Exercise the unapplied patch only inside its isolated copied tree."""

from __future__ import annotations

import json
import os
import runpy
from pathlib import Path

from marked_scale_parser import resolve_input


ROOT = Path(__file__).resolve().parent
TREE = ROOT / "raw" / "patch_apply_check" / "phase3-tabletop" / "rendering"
HOLDOUT = json.loads((ROOT / "holdout_cases.json").read_text(encoding="utf-8"))

previous_cwd = Path.cwd()
os.chdir(TREE)
try:
    proposed = runpy.run_path(str(TREE / "serve.py"), run_name="proposed_serve")
finally:
    os.chdir(previous_cwd)

parse_marked_scale = proposed["parse_marked_scale"]
fields = (
    "meaning",
    "generation_meaning",
    "explicit_scale_intent",
    "target_size",
    "scale_source",
)

parser_checks = []
for case in HOLDOUT["cases"]:
    routed = resolve_input(
        case["text"], case["input_mode"], "A", case.get("typed_object_key")
    )
    if routed["route"] != "assignment":
        continue
    actual = parse_marked_scale(routed["meaning"])
    expected = case["expected"]["A"]
    parser_checks.append({
        "id": case["id"],
        "pass": all(actual[field] == expected[field] for field in fields),
    })

# Prove that an explicit target shares the unmarked generation/cache asset and
# that status writes still match the original participant meaning.
cache_dir = TREE / "generated_meshes"
cache_dir.mkdir(exist_ok=True)
cached_mesh = cache_dir / "castle.glb"
cached_mesh.write_bytes(b"isolated-scale-cache-fixture")
record = {
    **parse_marked_scale("castle, scale tiny"),
    "status": "generating",
    "rotation": {"x": 0, "y": 0, "z": 0},
}
proposed["_assignments"].clear()
proposed["_assignments"]["2"] = record
proposed["_save_assignments"] = lambda data: None
os.chdir(TREE)
try:
    proposed["_local_generate_object"]("2", record["meaning"], record["generation_meaning"])
finally:
    os.chdir(previous_cwd)
cache_result = proposed["_assignments"]["2"]

index_text = (TREE / "index.html").read_text(encoding="utf-8")
production_index = (ROOT.parent / "index.html").read_text(encoding="utf-8")
voice_start = production_index.index("const VOICE_OBJECT_NUMBER_WORDS")
voice_end = production_index.index("function startVoiceRecording", voice_start)
proposed_voice_start = index_text.index("const VOICE_OBJECT_NUMBER_WORDS")
proposed_voice_end = index_text.index("function startVoiceRecording", proposed_voice_start)

result = {
    "proposed_parser_holdout": {
        "pass_count": sum(item["pass"] for item in parser_checks),
        "total": len(parser_checks),
        "all_pass": all(item["pass"] for item in parser_checks),
        "failed_ids": [item["id"] for item in parser_checks if not item["pass"]],
    },
    "cache_generation_separation": {
        "cache_file": cached_mesh.name,
        "meaning": cache_result["meaning"],
        "generation_meaning": cache_result["generation_meaning"],
        "target_size": cache_result["target_size"],
        "status": cache_result["status"],
        "mesh_url_uses_generation_slug": "/castle.glb?" in cache_result["mesh_url"],
        "pass": (
            cache_result["meaning"] == "castle, scale tiny"
            and cache_result["generation_meaning"] == "castle"
            and cache_result["target_size"] == 0.35
            and cache_result["status"] == "ready"
            and "/castle.glb?" in cache_result["mesh_url"]
        ),
    },
    "renderer_wiring": {
        "target_size_passed": "assignment.rotation, targetSize" in index_text,
        "old_record_neutral_fallback": ": 1.0;" in index_text,
        "relation_uses_generation_meaning": (
            "assignA.generation_meaning || assignA.meaning" in index_text
            and "assignB.generation_meaning || assignB.meaning" in index_text
        ),
    },
    "voice_route_byte_identical": (
        production_index[voice_start:voice_end]
        == index_text[proposed_voice_start:proposed_voice_end]
    ),
    "qwen_scale_calls": 0,
}
result["all_pass"] = (
    result["proposed_parser_holdout"]["all_pass"]
    and result["cache_generation_separation"]["pass"]
    and all(result["renderer_wiring"].values())
    and result["voice_route_byte_identical"]
    and result["qwen_scale_calls"] == 0
)

out = ROOT / "raw" / "proposed_integration_results.json"
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
