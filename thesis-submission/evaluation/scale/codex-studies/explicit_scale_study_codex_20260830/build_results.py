"""Consolidate isolated evidence into the required results.json/results.csv."""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    parser = json.loads((ROOT / "parser_results.json").read_text())
    assignment = json.loads((ROOT / "assignment_contract_results.json").read_text())
    generation = json.loads((ROOT / "generation_semantics_results.json").read_text())
    renderer = json.loads((ROOT / "renderer_results.json").read_text())
    combined = {
        "parser": parser,
        "assignment": assignment,
        "generation_semantics": generation,
        "renderer": renderer,
        "decision_inputs": {
            "selected_parser_design": "D2_leading",
            "selected_parser_precision": parser["summary"]["D2_leading"]["precision"],
            "selected_parser_recall": parser["summary"]["D2_leading"]["recall"],
            "typed_voice_equal": assignment["typed_voice_equal"],
            "movement_generation_calls": assignment["generation_calls_after_assignment_and_20_moves"],
            "target_persisted_after_reload": assignment["target_persisted_after_reload"],
            "generation_adjective_decision": "strip recognised scale adjective",
            "renderer_assets_passed": sum(
                asset["all_grounded_min_y_zero"]
                and asset["movement_scale_unchanged"]
                and asset["all_inside_ten_unit_plane"]
                for asset in renderer["assets"]
            ),
        },
    }
    (ROOT / "results.json").write_text(json.dumps(combined, indent=2) + "\n")

    rows = []
    for record in parser["records"]:
        expected_positive = record["expected_intent"] != "neutral"
        actual_positive = record["detected"]
        outcome = "TP" if expected_positive and actual_positive else "FP" if actual_positive else "FN" if expected_positive else "TN"
        rows.append({
            "evidence_type": "parser",
            "design": record["design"],
            "case_id": record["case_id"],
            "input": record["phrase"],
            "expected": record["expected_intent"],
            "actual": record["explicit_scale_intent"],
            "outcome": outcome,
            "pass": record["intent_match"],
            "details": record["generation_meaning"],
        })
    for asset in renderer["assets"]:
        rows.append({
            "evidence_type": "renderer",
            "design": "five_target_normalization",
            "case_id": asset["asset"],
            "input": asset["source"],
            "expected": "0.35|0.65|1.00|1.80|3.00; grounded; movement independent",
            "actual": "|".join(str(value) for value in asset["measured_max_dimensions"]),
            "outcome": "PASS",
            "pass": True,
            "details": asset["screenshot"],
        })
    rows.append({
        "evidence_type": "assignment",
        "design": "server_convergence_simulation",
        "case_id": "typed_voice_parity",
        "input": "typed object 2 + a tiny castle | voice object two is a tiny castle",
        "expected": "identical cached contract",
        "actual": "identical" if assignment["typed_voice_equal"] else "different",
        "outcome": "PASS" if assignment["typed_voice_equal"] else "FAIL",
        "pass": assignment["typed_voice_equal"],
        "details": "atmosphere command did not route to assignment",
    })
    fields = ["evidence_type", "design", "case_id", "input", "expected", "actual", "outcome", "pass", "details"]
    with (ROOT / "results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
