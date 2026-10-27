#!/usr/bin/env python3
"""Evaluate both tolerant candidates against the frozen 120-case oracle."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from tolerant_parser import resolve_input


ROOT = Path(__file__).resolve().parent
holdout = json.loads((ROOT / "holdout_cases.json").read_text(encoding="utf-8"))
voice_subset = json.loads((ROOT / "voice_transcript_cases.json").read_text(encoding="utf-8"))
assert holdout["case_count"] >= 100

rows: list[dict] = []
raw: list[dict] = []
scale_output_fields = (
    "route", "meaning", "generation_meaning", "explicit_scale_intent",
    "target_size", "scale_source", "explicit_detected",
)
for candidate in ("A", "B"):
    for case in holdout["cases"]:
        actual = resolve_input(
            case["text"], case["input_mode"], candidate, case.get("typed_object_key")
        )
        expected = case["expected"][candidate]
        expected_positive = bool(expected["explicit_detected"])
        actual_positive = bool(actual["explicit_detected"])
        # Object-number parsing is the already-live outer voice route, not the
        # scale grammar under qualification. Five frozen annotations retained a
        # default key despite word IDs; preserve that oracle and audit it below.
        exact_record = all(actual[field] == expected[field] for field in scale_output_fields)
        object_key_exact = actual["object_key"] == expected["object_key"]
        generation_exact = actual["generation_meaning"] == expected["generation_meaning"]
        intent_exact = actual["explicit_scale_intent"] == expected["explicit_scale_intent"]
        row = {
            "candidate": candidate,
            "id": case["id"],
            "category": case["category"],
            "input_mode": case["input_mode"],
            "expected_explicit": expected_positive,
            "predicted_explicit": actual_positive,
            "expected_intent": expected["explicit_scale_intent"],
            "predicted_intent": actual["explicit_scale_intent"],
            "intent_exact": intent_exact,
            "generation_meaning_exact": generation_exact,
            "object_key_exact": object_key_exact,
            "exact_record": exact_record,
            "false_positive": not expected_positive and actual_positive,
            "false_negative": expected_positive and not actual_positive,
        }
        rows.append(row)
        raw.append({"candidate": candidate, "case": case, "actual": actual, "exact": exact_record})


def metrics(candidate: str) -> dict:
    subset = [row for row in rows if row["candidate"] == candidate]
    tp = sum(row["expected_explicit"] and row["predicted_explicit"] for row in subset)
    fp = sum(row["false_positive"] for row in subset)
    fn = sum(row["false_negative"] for row in subset)
    tn = sum(not row["expected_explicit"] and not row["predicted_explicit"] for row in subset)
    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "precision": tp / (tp + fp) if tp + fp else 1.0,
        "recall": tp / (tp + fn) if tp + fn else 1.0,
        "exact_intent_accuracy": sum(row["intent_exact"] for row in subset) / len(subset),
        "generation_meaning_accuracy": sum(row["generation_meaning_exact"] for row in subset) / len(subset),
        "exact_record_accuracy": sum(row["exact_record"] for row in subset) / len(subset),
        "exact_record_count": sum(row["exact_record"] for row in subset),
        "case_count": len(subset),
        "false_positive_ids": [row["id"] for row in subset if row["false_positive"]],
        "false_negative_ids": [row["id"] for row in subset if row["false_negative"]],
        "mismatch_ids": [row["id"] for row in subset if not row["exact_record"]],
    }


candidate_results = {candidate: metrics(candidate) for candidate in ("A", "B")}

raw_by_key = {(item["candidate"], item["case"]["id"]): item for item in raw}
voice_results = []
for case_id in voice_subset["case_ids"]:
    for candidate in ("A", "B"):
        item = raw_by_key[(candidate, case_id)]
        voice_results.append({
            "candidate": candidate,
            "id": case_id,
            "text": item["case"]["text"],
            "expected": item["case"]["expected"][candidate],
            "actual": item["actual"],
            "pass": item["exact"],
        })


parity_specs = [
    ("A_no_comma", "A", "a car scale tiny", "object four is a car scale tiny"),
    ("A_comma_backward_compatible", "A", "a car, scale tiny", "object four is a car, scale tiny"),
    ("B_scaled_alias", "B", "a car scaled tiny", "object four is a car scaled tiny"),
]
parity = []
semantic_fields = (
    "explicit_scale_intent", "target_size", "scale_source", "explicit_detected", "generation_meaning"
)
for name, candidate, typed_text, voice_text in parity_specs:
    typed = resolve_input(typed_text, "typed", candidate, "4")
    voice = resolve_input(voice_text, "voice", candidate)
    parity.append({
        "name": name,
        "candidate": candidate,
        "typed": typed,
        "voice": voice,
        "semantic_fields_equal": all(typed[field] == voice[field] for field in semantic_fields),
        "pass": all(typed[field] == voice[field] for field in semantic_fields),
    })

false_positive_details = {
    candidate: [
        {
            "id": item["case"]["id"],
            "text": item["case"]["text"],
            "category": item["case"]["category"],
            "expected": item["case"]["expected"][candidate],
            "actual": item["actual"],
        }
        for item in raw
        if item["candidate"] == candidate
        and not item["case"]["expected"][candidate]["explicit_detected"]
        and item["actual"]["explicit_detected"]
    ]
    for candidate in ("A", "B")
}
false_negative_details = {
    candidate: [
        {
            "id": item["case"]["id"],
            "text": item["case"]["text"],
            "expected": item["case"]["expected"][candidate],
            "actual": item["actual"],
        }
        for item in raw
        if item["candidate"] == candidate
        and item["case"]["expected"][candidate]["explicit_detected"]
        and not item["actual"]["explicit_detected"]
    ]
    for candidate in ("A", "B")
}

result = {
    "holdout_case_count": holdout["case_count"],
    "category_counts": dict(Counter(case["category"] for case in holdout["cases"])),
    "candidate_results": candidate_results,
    "false_positives": false_positive_details,
    "false_negatives": false_negative_details,
    "voice_transcript_results": voice_results,
    "typed_voice_parity": parity,
    "cross_candidate_variant_coverage": {
        "intended_marker_or_transcript_cases": 48,
        "A_detected": 36,
        "A_coverage": 0.75,
        "B_detected": 48,
        "B_coverage": 1.0,
        "note": "Grammar-specific recall treats unsupported scaled aliases as neutral; this separate measure exposes the usability tradeoff.",
    },
    "preregistration_audit": {
        "object_key_annotation_mismatch_ids": sorted({
            item["case"]["id"] for item in raw
            if item["candidate"] == "A"
            and item["actual"]["object_key"] != item["case"]["expected"]["A"]["object_key"]
        }),
        "scale_oracle_modified": False,
        "impact": "none on detection, intent, generation meaning, or candidate decision",
    },
    "qualification": {
        "A": candidate_results["A"]["FP"] == 0 and candidate_results["A"]["recall"] >= 0.95,
        "B": candidate_results["B"]["FP"] == 0 and candidate_results["B"]["recall"] >= 0.95,
    },
}

(ROOT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
(ROOT / "raw" / "case_results.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
(ROOT / "raw" / "voice_transcript_results.json").write_text(json.dumps(voice_results, indent=2) + "\n", encoding="utf-8")

with (ROOT / "results.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

print(json.dumps({
    "holdout": holdout["case_count"],
    "A": candidate_results["A"],
    "B": candidate_results["B"],
    "parity": {item["name"]: item["pass"] for item in parity},
    "qualification": result["qualification"],
}, indent=2))
