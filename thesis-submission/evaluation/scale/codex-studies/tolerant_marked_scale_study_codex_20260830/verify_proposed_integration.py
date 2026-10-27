#!/usr/bin/env python3
"""Verify the unapplied follow-up patch inside its copied tree only."""

from __future__ import annotations

import json
import os
import runpy
from pathlib import Path

from tolerant_parser import resolve_input


ROOT = Path(__file__).resolve().parent
TREE = ROOT / "raw" / "patch_apply_check" / "phase3-tabletop" / "rendering"
PRODUCTION = ROOT.parent
holdout = json.loads((ROOT / "holdout_cases.json").read_text(encoding="utf-8"))

previous_cwd = Path.cwd()
os.chdir(TREE)
try:
    proposed = runpy.run_path(str(TREE / "serve.py"), run_name="proposed_serve")
finally:
    os.chdir(previous_cwd)

parse_marked_scale = proposed["parse_marked_scale"]
fields = (
    "meaning", "generation_meaning", "explicit_scale_intent",
    "target_size", "scale_source",
)
checks = []
for case in holdout["cases"]:
    routed = resolve_input(case["text"], case["input_mode"], "A", case.get("typed_object_key"))
    if routed["route"] != "assignment":
        continue
    expected = case["expected"]["A"]
    actual = parse_marked_scale(routed["meaning"])
    checks.append({
        "id": case["id"],
        "pass": all(actual[field] == expected[field] for field in fields),
    })

production_index = (PRODUCTION / "index.html").read_bytes()
isolated_index = (TREE / "index.html").read_bytes()
production_serve = (PRODUCTION / "serve.py").read_text(encoding="utf-8")
isolated_serve = (TREE / "serve.py").read_text(encoding="utf-8")

result = {
    "proposed_assignment_cases": {
        "pass_count": sum(item["pass"] for item in checks),
        "total": len(checks),
        "all_pass": all(item["pass"] for item in checks),
        "failed_ids": [item["id"] for item in checks if not item["pass"]],
    },
    "strict_comma_backward_compatible": parse_marked_scale("a car, scale tiny")["target_size"] == 0.35,
    "no_comma_tolerant": parse_marked_scale("a car scale tiny")["target_size"] == 0.35,
    "scaled_alias_rejected": parse_marked_scale("a car scaled tiny")["target_size"] == 1.0,
    "voice_index_byte_identical": production_index == isolated_index,
    "only_server_parser_region_changed": (
        "Project decision, 30 Aug 2026" in isolated_serve
        and "(?:scale|scaled|make\\s+it)" in isolated_serve
        and production_serve != isolated_serve
    ),
    "qwen_scale_calls_added": 0,
}
result["all_pass"] = (
    result["proposed_assignment_cases"]["all_pass"]
    and result["strict_comma_backward_compatible"]
    and result["no_comma_tolerant"]
    and result["scaled_alias_rejected"]
    and result["voice_index_byte_identical"]
    and result["only_server_parser_region_changed"]
    and result["qwen_scale_calls_added"] == 0
)

out = ROOT / "raw" / "proposed_integration_results.json"
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
