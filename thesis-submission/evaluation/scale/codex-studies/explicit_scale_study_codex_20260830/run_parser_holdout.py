"""Run the frozen explicit-scale holdout against the two frozen designs."""

import csv
import json
from collections import defaultdict
from pathlib import Path

from explicit_scale_parser import parse_anywhere, parse_leading


ROOT = Path(__file__).resolve().parent
DESIGNS = {"D1_anywhere": parse_anywhere, "D2_leading": parse_leading}


def metrics(rows):
    expected_positive = lambda row: row["expected_intent"] != "neutral"
    tp = sum(expected_positive(row) and row["detected"] for row in rows)
    fp = sum(not expected_positive(row) and row["detected"] for row in rows)
    fn = sum(expected_positive(row) and not row["detected"] for row in rows)
    tn = sum(not expected_positive(row) and not row["detected"] for row in rows)
    return {
        "cases": len(rows),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "intent_exact": sum(row["intent_match"] for row in rows),
        "generation_exact": sum(row["generation_match"] for row in rows),
    }


def main():
    cases = json.loads((ROOT / "holdout_cases.json").read_text())["cases"]
    if len(cases) != 60:
        raise SystemExit("frozen holdout count changed")
    records = []
    raw_root = ROOT / "raw" / "parser"
    for design, parser in DESIGNS.items():
        for case in cases:
            output = parser(case["phrase"])
            row = {
                "design": design,
                "case_id": case["id"],
                "category": case["category"],
                "phrase": case["phrase"],
                "expected_intent": case["expected_intent"],
                "expected_generation_meaning": case["expected_generation_meaning"],
                **output,
                "intent_match": output["explicit_scale_intent"] == case["expected_intent"],
                "generation_match": output["generation_meaning"].casefold() == case["expected_generation_meaning"].casefold(),
            }
            records.append(row)
            raw_root.mkdir(parents=True, exist_ok=True)
            (raw_root / f"{design}__{case['id']}.json").write_text(json.dumps(row, indent=2) + "\n")

    summary = {}
    for design in DESIGNS:
        summary[design] = metrics([row for row in records if row["design"] == design])
    result = {"holdout": "explicit_scale_parser_holdout_v1", "summary": summary, "records": records}
    (ROOT / "parser_results.json").write_text(json.dumps(result, indent=2) + "\n")
    fields = list(records[0])
    with (ROOT / "parser_results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
