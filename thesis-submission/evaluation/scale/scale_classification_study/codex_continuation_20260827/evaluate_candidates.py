"""Fresh holdout evaluator for Tangible Worlds semantic scale candidates.

This isolated script reads the frozen holdout and writes only inside its own
continuation directory. It does not import or modify production code.
"""

import argparse
import csv
import json
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests


# Authoritative API references:
# https://lmstudio.ai/docs/developer/openai-compat/chat-completions
# https://lmstudio.ai/docs/developer/core/structured-output
URL = "http://127.0.0.1:1234/v1/chat/completions"
MODELS_URL = "http://127.0.0.1:1234/v1/models"
MODEL = "qwen/qwen3-8b"
CLASSES = (
    "micro", "handheld", "body_scale", "room_scale", "vehicle_scale",
    "building_scale", "infrastructure_scale", "landform_scale",
    "colossal_scale", "ambiguous",
)

SHARED = """You classify an assigned meaning for Tangible Worlds into one semantic relative-scale class.

The physical tabletop prop is only a handle. Ignore the prop's physical size.
Classify the REAL-WORLD OR INTENDED REPRESENTED SCALE of the assigned meaning.
The classes are compressed visual ordering bins for a miniature 3D environment, not literal metre measurements and not object-category labels.

Classes:
- micro: clearly much smaller than normal handheld objects.
- handheld: normally held or carried in the hands.
- body_scale: roughly person, animal, or furniture scale.
- room_scale: roughly room or small shelter scale.
- vehicle_scale: ordinary mobile vehicle or vessel scale.
- building_scale: one substantial building or building-like structure.
- infrastructure_scale: a very large built structure or complex beyond one ordinary building.
- landform_scale: a geographic terrain or natural landform feature.
- colossal_scale: city, continent, astronomical, or similarly enormous extent beyond an ordinary landform.
- ambiguous: no stable physical scale can be inferred, or the meaning is abstract, non-physical, an event, or too underspecified.

Decision rules:
- classify typical physical extent, not the noun's category.
- honour explicit size and comparison language over the subject noun's ordinary size.
- choose the nearest single class for a concrete physical meaning.
- use ambiguous conservatively when physical extent is genuinely unstable.
"""

ENUM_SUFFIX = """
Return ONLY one exact class name:
micro
handheld
body_scale
room_scale
vehicle_scale
building_scale
infrastructure_scale
landform_scale
colossal_scale
ambiguous

Do not explain. Do not output punctuation, JSON, markdown, or any other text.
"""

STRUCTURED_SUFFIX = """
Return ONLY one JSON object with exactly these keys:
{\"scale_basis\":\"<short observable physical size reference>\",\"semantic_scale_class\":\"<class>\"}

scale_basis must be a short noun phrase naming the physical extent or explicit comparison that controls the class. It is not an explanation or private reasoning.
semantic_scale_class must be exactly one of: micro, handheld, body_scale, room_scale, vehicle_scale, building_scale, infrastructure_scale, landform_scale, colossal_scale, ambiguous.
No markdown or extra keys.
"""

SYSTEM_A = SHARED + ENUM_SUFFIX
SYSTEM_B = SHARED + STRUCTURED_SUFFIX
SYSTEM_C = SHARED + ENUM_SUFFIX

JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "semantic_scale_classification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "scale_basis": {"type": "string", "minLength": 1, "maxLength": 80},
                "semantic_scale_class": {"type": "string", "enum": list(CLASSES)},
            },
            "required": ["scale_basis", "semantic_scale_class"],
            "additionalProperties": False,
        },
    },
}


def strip_think(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def parse_enum(text):
    cleaned = strip_think(text).lower().strip("`* .,:;\"'\n\t")
    return cleaned if cleaned in CLASSES else None


def parse_structured(text):
    try:
        value = json.loads(strip_think(text))
    except (json.JSONDecodeError, TypeError):
        return None, None
    if not isinstance(value, dict) or set(value) != {"scale_basis", "semantic_scale_class"}:
        return None, None
    basis = value.get("scale_basis")
    result = value.get("semantic_scale_class")
    if not isinstance(basis, str) or not basis.strip() or result not in CLASSES:
        return None, None
    return basis.strip(), result


def modifier_basis(meaning):
    text = meaning.strip()
    patterns = (
        ("comparison_as", r"^.+?\s+as\s+(?:tall|wide|long|large|big)\s+as\s+(.+)$"),
        ("comparison_size_of", r"^.+?\s+the\s+size\s+of\s+(.+)$"),
        ("reference_sized", r"^(.+?)-sized\s+.+$"),
        ("full_scale_representation", r"^(?:life-size|life-sized|full-size|full-sized|full-scale)\s+(?:model|replica)\s+(?:of\s+)?(.+)$"),
        ("small_representation", r"^(?:miniature|toy)(?:\s+version)?(?:\s+model)?(?:\s+replica)?(?:\s+of)?\s+.+$"),
    )
    for rule, pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        if rule == "small_representation":
            return "a small portable toy or miniature model", rule
        basis = match.group(1).strip(" .")
        if rule == "full_scale_representation":
            return f"an ordinary full-size {basis}", rule
        if rule == "reference_sized":
            normalised = basis.lower()
            if normalised in {"hand", "palm"}:
                basis = "an object that fits in one hand"
            elif normalised == "pocket":
                basis = "an object that fits inside a clothing pocket"
        return basis, rule
    return text, "ordinary_unmodified"


def request_model(system, user, timeout, response_format=None, max_tokens=20):
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if response_format is not None:
        payload["response_format"] = response_format
    started = time.perf_counter()
    response = requests.post(URL, json=payload, timeout=timeout)
    latency = time.perf_counter() - started
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"], latency


def classify(candidate, meaning, timeout):
    if candidate == "A_direct_enum":
        basis, rule = meaning, "model_direct"
        user = f'Assigned semantic meaning: "{meaning}"\nClassify the intended represented real-world scale. /no_think'
        raw, latency = request_model(SYSTEM_A, user, timeout)
        return raw, parse_enum(raw), basis, rule, latency
    if candidate == "B_structured_basis":
        basis, rule = "", "model_structured"
        user = f'Assigned semantic meaning: "{meaning}"\nIdentify the observable scale basis and classify the intended represented real-world scale. /no_think'
        raw, latency = request_model(SYSTEM_B, user, timeout, JSON_SCHEMA, 80)
        basis, parsed = parse_structured(raw)
        return raw, parsed, basis, rule, latency
    if candidate == "C_modifier_preparser":
        basis, rule = modifier_basis(meaning)
        user = (
            f'Assigned semantic meaning: "{meaning}"\n'
            f'Deterministically extracted intended scale basis: "{basis}"\n'
            'Classify the physical extent expressed by the scale basis. /no_think'
        )
        raw, latency = request_model(SYSTEM_C, user, timeout)
        return raw, parse_enum(raw), basis, rule, latency
    raise ValueError(candidate)


def summarise(records, cases):
    by_candidate = {}
    case_lookup = {case["id"]: case for case in cases}
    for candidate in sorted({row["candidate"] for row in records}):
        rows = [row for row in records if row["candidate"] == candidate]
        first = [row for row in rows if row["run"] == 1]
        groups = {}
        for group in sorted({row["group"] for row in first}):
            grouped = [row for row in first if row["group"] == group]
            groups[group] = {
                "cases": len(grouped),
                "valid": sum(row["valid_contract"] for row in grouped),
                "acceptable": sum(row["acceptable_match"] for row in grouped),
            }
        repeated_ids = [case["id"] for case in cases if case["repeat"]]
        repeated = []
        for case_id in repeated_ids:
            outputs = [row["parsed_class"] for row in rows if row["case_id"] == case_id]
            repeated.append({
                "case_id": case_id,
                "meaning": case_lookup[case_id]["meaning"],
                "outputs": outputs,
                "exact_agreement": len(outputs) == 3 and None not in outputs and len(set(outputs)) == 1,
            })
        by_candidate[candidate] = {
            "holdout_cases": len(first),
            "valid_contract": sum(row["valid_contract"] for row in first),
            "acceptable": sum(row["acceptable_match"] for row in first),
            "modifier_cases": groups["modifier"]["cases"],
            "modifier_valid": groups["modifier"]["valid"],
            "modifier_acceptable": groups["modifier"]["acceptable"],
            "repeat_cases": len(repeated),
            "repeat_exact_agreement": sum(item["exact_agreement"] for item in repeated),
            "groups": groups,
            "repeat_details": repeated,
        }
    return by_candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--output", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = Path(args.output).resolve()
    cases = json.loads((root / "holdout_cases.json").read_text())["cases"]
    if len(cases) != 72 or sum(case["group"] == "modifier" for case in cases) != 20:
        raise SystemExit("frozen holdout count changed")
    models = requests.get(MODELS_URL, timeout=args.timeout)
    models.raise_for_status()
    ids = [item.get("id") for item in models.json().get("data", [])]
    if MODEL not in ids:
        raise SystemExit(f"{MODEL} not available: {ids}")

    candidates = ("A_direct_enum", "B_structured_basis", "C_modifier_preparser")
    records = []
    raw_root = output / "raw"
    for candidate in candidates:
        for index, case in enumerate(cases, start=1):
            runs = 3 if case["repeat"] else 1
            for run in range(1, runs + 1):
                error = ""
                raw = ""
                parsed = None
                basis = None
                rule = ""
                latency = 0.0
                try:
                    raw, parsed, basis, rule, latency = classify(candidate, case["meaning"], args.timeout)
                except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    error = f"{type(exc).__name__}: {exc}"
                row = {
                    "candidate": candidate,
                    "case_id": case["id"],
                    "case_index": index,
                    "group": case["group"],
                    "meaning": case["meaning"],
                    "acceptable": case["acceptable"],
                    "repeat_preregistered": case["repeat"],
                    "run": run,
                    "raw_output": raw,
                    "parsed_class": parsed,
                    "scale_basis": basis,
                    "preparser_rule": rule,
                    "valid_contract": parsed is not None,
                    "acceptable_match": parsed in case["acceptable"] if parsed else False,
                    "latency_s": round(latency, 3),
                    "error": error,
                }
                records.append(row)
                raw_path = raw_root / candidate / f'{case["id"]}_run{run}.json'
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_text(json.dumps(row, indent=2) + "\n")
                shown = parsed or "INVALID"
                marker = "ok" if row["acceptable_match"] else "review"
                print(f"[{candidate} {index:02d}/72 r{run}/{runs}] {case['meaning']} -> {shown} [{marker}]", flush=True)

    summary = summarise(records, cases)
    result = {
        "metadata": {
            "created_at": datetime.now().astimezone().isoformat(),
            "model": MODEL,
            "url": URL,
            "temperature": 0.0,
            "thinking": False,
            "holdout": "fresh_holdout_v1",
            "holdout_cases": len(cases),
            "modifier_cases": sum(case["group"] == "modifier" for case in cases),
            "repeat_cases": sum(case["repeat"] for case in cases),
            "expected_labels_frozen_before_inference": True,
        },
        "summary": summary,
        "records": records,
    }
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    fields = list(records[0])
    with (output / "results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in records:
            flat = dict(row)
            flat["acceptable"] = "|".join(row["acceptable"])
            writer.writerow(flat)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
