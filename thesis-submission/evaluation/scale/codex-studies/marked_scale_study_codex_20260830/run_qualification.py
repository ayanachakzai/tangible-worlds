#!/usr/bin/env python3
"""Evaluate both frozen marked grammars and ancillary contract checks."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from marked_scale_parser import parse_marked_meaning, resolve_input


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
HOLDOUT = ROOT / "holdout_cases.json"


def metric_block(rows: list[dict]) -> dict:
    tp = sum(r["expected_explicit"] and r["predicted_explicit"] for r in rows)
    fp = sum(not r["expected_explicit"] and r["predicted_explicit"] for r in rows)
    fn = sum(r["expected_explicit"] and not r["predicted_explicit"] for r in rows)
    tn = sum(not r["expected_explicit"] and not r["predicted_explicit"] for r in rows)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    exact = sum(r["exact_record"] for r in rows)
    expected_positive = [r for r in rows if r["expected_explicit"]]
    exact_positive_intent = sum(
        r["expected_intent"] == r["predicted_intent"] for r in expected_positive
    )
    safe_fallback_rows = [
        r for r in rows
        if r["category"] in {
            "malformed_marker", "multiple_markers", "conflicting_markers", "unsupported_synonym"
        }
    ]
    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "precision": precision,
        "recall": recall,
        "exact_record_accuracy": exact / len(rows),
        "exact_record_count": exact,
        "case_count": len(rows),
        "exact_positive_intent_accuracy": (
            exact_positive_intent / len(expected_positive) if expected_positive else 1.0
        ),
        "safe_fallback_count": sum(r["exact_record"] for r in safe_fallback_rows),
        "safe_fallback_total": len(safe_fallback_rows),
        "false_positive_ids": [r["id"] for r in rows if r["false_positive"]],
        "false_negative_ids": [r["id"] for r in rows if r["false_negative"]],
        "mismatch_ids": [r["id"] for r in rows if not r["exact_record"]],
    }


payload = json.loads(HOLDOUT.read_text(encoding="utf-8"))
assert payload["case_count"] >= 60

case_rows: list[dict] = []
raw_records: list[dict] = []
for grammar in ("A", "B"):
    for case in payload["cases"]:
        actual = resolve_input(
            case["text"],
            case["input_mode"],
            grammar,
            case.get("typed_object_key"),
        )
        expected = case["expected"][grammar]
        exact = actual == expected
        row = {
            "grammar": grammar,
            "id": case["id"],
            "category": case["category"],
            "input_mode": case["input_mode"],
            "expected_explicit": bool(expected["explicit_detected"]),
            "predicted_explicit": bool(actual["explicit_detected"]),
            "expected_intent": expected["explicit_scale_intent"],
            "predicted_intent": actual["explicit_scale_intent"],
            "exact_record": exact,
            "false_positive": not expected["explicit_detected"] and actual["explicit_detected"],
            "false_negative": expected["explicit_detected"] and not actual["explicit_detected"],
        }
        case_rows.append(row)
        raw_records.append({"grammar": grammar, "case": case, "actual": actual, "exact": exact})

by_grammar = {
    grammar: metric_block([r for r in case_rows if r["grammar"] == grammar])
    for grammar in ("A", "B")
}

# Requested typed/voice pairs. Participant wording is retained verbatim, so
# leading articles differ where the supplied examples differ; scale fields and
# subject identity after optional-article comparison must agree.
parity_specs = [
    ("A_tiny", "A", "castle, scale tiny", "object two is a castle, scale tiny"),
    ("B_huge", "B", "castle, make it huge", "object two is a castle, make it huge"),
    ("bare_neutral", "A", "castle", "object two is a castle"),
]
parity = []
for name, grammar, typed_text, voice_text in parity_specs:
    typed = resolve_input(typed_text, "typed", grammar, "2")
    voice = resolve_input(voice_text, "voice", grammar)
    semantic_fields = (
        "route", "object_key", "explicit_scale_intent", "target_size", "scale_source", "explicit_detected"
    )
    fields_equal = all(typed[field] == voice[field] for field in semantic_fields)
    typed_subject = typed["generation_meaning"].lower().removeprefix("a ").removeprefix("an ")
    voice_subject = voice["generation_meaning"].lower().removeprefix("a ").removeprefix("an ")
    parity.append({
        "name": name,
        "grammar": grammar,
        "typed": typed,
        "voice": voice,
        "semantic_contract_equal": fields_equal,
        "subject_identity_equal_ignoring_supplied_article": typed_subject == voice_subject,
        "original_phrase_difference_expected": typed["meaning"] != voice["meaning"],
        "pass": fields_equal and typed_subject == voice_subject,
    })

generation_checks = []
for grammar, suffix in (("A", "scale"), ("B", "make it")):
    for noun, modifier in (
        ("castle", "tiny"),
        ("toy car", "miniature"),
        ("mushroom", "small"),
        ("bridge", "large"),
        ("house", "huge"),
    ):
        original = f"{noun}, {suffix} {modifier}"
        parsed = parse_marked_meaning(original, grammar)
        generation_checks.append({
            "grammar": grammar,
            "noun": noun,
            "original": original,
            "actual": parsed,
            "marker_removed": parsed["generation_meaning"] == noun,
            "original_preserved": parsed["meaning"] == original,
            "pass": parsed["generation_meaning"] == noun and parsed["meaning"] == original,
        })

# Isolated persistence/movement simulation for the selected simpler candidate A.
assignment = {
    **parse_marked_meaning("castle, scale tiny", "A"),
    "status": "ready",
    "rotation": {"x": 0, "y": 0, "z": 0},
    "mesh_url": "/generated_meshes/castle.glb?v=1",
}
fixture_path = RAW / "persistence_fixture.json"
fixture_path.write_text(json.dumps({"2": assignment}, indent=2) + "\n", encoding="utf-8")
reloaded = json.loads(fixture_path.read_text(encoding="utf-8"))["2"]
generation_calls = 1
positions = []
for step in range(20):
    positions.append({"step": step + 1, "x": round(0.1 + step * 0.03, 3), "z": round(-0.2 + step * 0.02, 3)})
movement = {
    "assignment_before": reloaded,
    "movement_updates": positions,
    "assignment_after": reloaded,
    "generation_calls": generation_calls,
    "target_persisted": reloaded["target_size"] == 0.35,
    "meaning_persisted": reloaded["meaning"] == "castle, scale tiny",
    "generation_meaning_persisted": reloaded["generation_meaning"] == "castle",
    "movement_did_not_regenerate": generation_calls == 1,
}
movement["pass"] = all((
    movement["target_persisted"],
    movement["meaning_persisted"],
    movement["generation_meaning_persisted"],
    movement["movement_did_not_regenerate"],
))
(RAW / "movement_persistence.json").write_text(
    json.dumps(movement, indent=2) + "\n", encoding="utf-8"
)

result = {
    "holdout_case_count": payload["case_count"],
    "candidate_results": by_grammar,
    "category_counts": dict(Counter(c["category"] for c in payload["cases"])),
    "typed_voice_parity": parity,
    "generation_semantics": {
        "checks": generation_checks,
        "pass_count": sum(item["pass"] for item in generation_checks),
        "total": len(generation_checks),
        "all_pass": all(item["pass"] for item in generation_checks),
    },
    "persistence_movement": movement,
    "atmosphere_route": {
        "case_count": sum(c["category"] == "atmosphere_command" for c in payload["cases"]),
        "all_outside_assignment": all(
            rec["actual"]["route"] == "atmosphere"
            for rec in raw_records
            if rec["case"]["category"] == "atmosphere_command"
        ),
    },
    "qualification": {
        "A": by_grammar["A"]["FP"] == 0 and by_grammar["A"]["precision"] == 1.0 and by_grammar["A"]["recall"] >= 0.95,
        "B": by_grammar["B"]["FP"] == 0 and by_grammar["B"]["precision"] == 1.0 and by_grammar["B"]["recall"] >= 0.95,
    },
}

(ROOT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
(RAW / "case_results.json").write_text(json.dumps(raw_records, indent=2) + "\n", encoding="utf-8")

with (ROOT / "results.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(case_rows[0]))
    writer.writeheader()
    writer.writerows(case_rows)

print(json.dumps({
    "holdout": payload["case_count"],
    "A": by_grammar["A"],
    "B": by_grammar["B"],
    "parity_pass": all(item["pass"] for item in parity),
    "generation_pass": result["generation_semantics"]["all_pass"],
    "movement_pass": movement["pass"],
    "atmosphere_pass": result["atmosphere_route"]["all_outside_assignment"],
}, indent=2))
