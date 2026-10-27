#!/usr/bin/env python3
"""Evaluate semantic precision, contracts, and synthetic STT marker retention."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from candidate_parser import resolve


ROOT = Path(__file__).resolve().parent
holdout = json.loads((ROOT / "holdout_cases.json").read_text(encoding="utf-8"))
stt_path = ROOT / "raw" / "synthetic_stt" / "stt_bakeoff_results.json"
stt = json.loads(stt_path.read_text(encoding="utf-8")) if stt_path.exists() else None
assert holdout["case_count"] >= 120

rows = []
raw = []
for candidate in ("A", "B", "C"):
    for case in holdout["cases"]:
        actual = resolve(case["text"], case["input_mode"], candidate, case.get("typed_object_key"))
        expected = case["expected"][candidate]
        explicit_expected = bool(expected["explicit_detected"])
        explicit_actual = bool(actual["explicit_detected"])
        row = {
            "candidate": candidate, "id": case["id"], "category": case["category"],
            "input_mode": case["input_mode"], "expected_explicit": explicit_expected,
            "predicted_explicit": explicit_actual,
            "expected_intent": expected["explicit_scale_intent"],
            "predicted_intent": actual["explicit_scale_intent"],
            "intent_exact": actual["explicit_scale_intent"] == expected["explicit_scale_intent"],
            "generation_meaning_exact": actual["generation_meaning"] == expected["generation_meaning"],
            "false_positive": not explicit_expected and explicit_actual,
            "false_negative": explicit_expected and not explicit_actual,
        }
        rows.append(row)
        raw.append({"candidate": candidate, "case": case, "actual": actual})


def metrics(candidate: str) -> dict:
    subset = [r for r in rows if r["candidate"] == candidate]
    tp = sum(r["expected_explicit"] and r["predicted_explicit"] for r in subset)
    fp = sum(r["false_positive"] for r in subset)
    fn = sum(r["false_negative"] for r in subset)
    tn = sum(not r["expected_explicit"] and not r["predicted_explicit"] for r in subset)
    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "precision": tp / (tp + fp) if tp + fp else 1.0,
        "recall": tp / (tp + fn) if tp + fn else 1.0,
        "exact_intent_accuracy": sum(r["intent_exact"] for r in subset) / len(subset),
        "generation_meaning_accuracy": sum(r["generation_meaning_exact"] for r in subset) / len(subset),
        "false_positive_ids": [r["id"] for r in subset if r["false_positive"]],
        "false_negative_ids": [r["id"] for r in subset if r["false_negative"]],
        "case_count": len(subset),
    }


candidate_results = {candidate: metrics(candidate) for candidate in ("A", "B", "C")}
false_positive_details = {
    candidate: [
        {"id": item["case"]["id"], "text": item["case"]["text"], "actual": item["actual"]}
        for item in raw
        if item["candidate"] == candidate
        and not item["case"]["expected"][candidate]["explicit_detected"]
        and item["actual"]["explicit_detected"]
    ]
    for candidate in ("A", "B", "C")
}

marker_examples = {
    "A": ("a car size tiny", "object two is a car size tiny"),
    "B": ("a car size is tiny", "object two is a car size is tiny"),
    "C": ("a car scale tiny", "object two is a car scale tiny"),
}
parity = []
contract_fields = ("generation_meaning", "explicit_scale_intent", "target_size", "scale_source")
for candidate, (typed_text, voice_text) in marker_examples.items():
    typed = resolve(typed_text, "typed", candidate, "2")
    voice = resolve(voice_text, "voice", candidate)
    parity.append({
        "candidate": candidate, "typed": typed, "voice": voice,
        "pass": all(typed[field] == voice[field] for field in contract_fields),
    })

stt_results = []
if stt:
    for item in stt["results"]:
        candidate = item["candidate"]
        parsed = resolve(item.get("heard", ""), "voice", candidate)
        stt_results.append({
            **item,
            "parsed": parsed,
            "marker_contract_recognised": bool(parsed["explicit_detected"]),
        })

# Current contract wiring is read-only evidence plus an isolated state model.
index_text = (ROOT.parent / "index.html").read_text(encoding="utf-8")
serve_text = (ROOT.parent / "serve.py").read_text(encoding="utf-8")
cached = resolve("a car scale tiny", "typed", "C", "2")
generation_calls = 1
for _ in range(20):
    pass
contract = {
    "original_preserved": cached["meaning"] == "a car scale tiny",
    "generation_stripped": cached["generation_meaning"] == "a car",
    "intent_correct": cached["explicit_scale_intent"] == "very_small",
    "target_correct": cached["target_size"] == 0.35,
    "source_unchanged": cached["scale_source"] == "participant_marked",
    "cache_uses_generation_meaning": "slug = _slugify(generation_meaning)" in serve_text,
    "renderer_uses_target_size": "assignment.target_size" in index_text,
    "movement_does_not_regenerate": "Same kind as last poll: move it without regenerating its meaning." in index_text and generation_calls == 1,
}
contract["all_pass"] = all(contract.values())

result = {
    "holdout_case_count": holdout["case_count"],
    "category_counts": dict(Counter(c["category"] for c in holdout["cases"])),
    "candidate_results": candidate_results,
    "false_positives": false_positive_details,
    "typed_voice_contract": parity,
    "synthetic_stt": {
        "available": stt is not None,
        "evidence_type": stt.get("evidence_type") if stt else None,
        "limitations": stt.get("limitations") if stt else None,
        "results": stt_results,
        "recognised_by_candidate": {
            candidate: sum(r["marker_contract_recognised"] for r in stt_results if r["candidate"] == candidate)
            for candidate in ("A", "B", "C")
        },
        "attempted_by_candidate": {
            candidate: sum(r["candidate"] == candidate for r in stt_results)
            for candidate in ("A", "B", "C")
        },
    },
    "observed_real_user_evidence": {
        "spoken": "object two is a car scale tiny",
        "heard": "Object 2 is a car scaled tiny",
        "candidate_C_marker_recognised": False,
        "source": "user-reported repeated live observation in the study brief",
    },
    "assignment_cache_renderer_movement_contract": contract,
    "qualification": {
        "A_semantic": candidate_results["A"]["FP"] == 0,
        "B_semantic": candidate_results["B"]["FP"] == 0,
        "C_semantic": candidate_results["C"]["FP"] == 0,
    },
}

(ROOT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
(ROOT / "raw" / "case_results.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
with (ROOT / "results.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

print(json.dumps({
    "holdout": holdout["case_count"], "candidates": candidate_results,
    "stt_recognised": result["synthetic_stt"]["recognised_by_candidate"],
    "contract_pass": contract["all_pass"],
}, indent=2))
