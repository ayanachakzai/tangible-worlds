"""
isolated qwen semantic-scale classification battery for tangible worlds.

this file does not import or modify production code. it calls the existing
local lm studio qwen endpoint and writes study results beside the script.

smoke test:
    python qwen_scale_classification_test.py --limit 12 --runs 1

full battery:
    python qwen_scale_classification_test.py --runs 3
"""

import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests


# ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
# ref: https://huggingface.co/Qwen/Qwen3-8B
LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODELS_URL = "http://127.0.0.1:1234/v1/models"
LMSTUDIO_MODEL = "qwen/qwen3-8b"

CLASSES = (
    "micro",
    "handheld",
    "body_scale",
    "room_scale",
    "vehicle_scale",
    "building_scale",
    "infrastructure_scale",
    "landform_scale",
    "colossal_scale",
    "ambiguous",
)

SYSTEM_PROMPT = """You classify an assigned meaning for Tangible Worlds into one semantic relative-scale class.

The physical tabletop prop is only a handle. Ignore the prop's physical size.
Classify the REAL-WORLD OR INTENDED REPRESENTED SCALE of the assigned meaning.
The classes are visual ordering bins for a miniature 3D environment, not literal metre measurements.

Return ONLY one exact class name from this list:
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

Class guide:
- micro: clearly much smaller than normal handheld objects, such as an ant, grain of rice, or button.
- handheld: normally held or carried in the hands, such as a mug, phone, book, or backpack.
- body_scale: roughly person, animal, or furniture scale, such as a person, dog, horse, chair, or sofa.
- room_scale: roughly room or small shelter scale, such as a tent, kiosk, small shed, or shipping container.
- vehicle_scale: ordinary mobile vehicle or vessel scale, such as a car, bus, train carriage, boat, or aircraft.
- building_scale: a single substantial building or building-like structure, such as a house, church, tower, or office block.
- infrastructure_scale: a very large built structure or built complex beyond one ordinary building, such as a castle complex, stadium, major bridge, dam, refinery, or airport complex.
- landform_scale: a geographic terrain or natural landform feature, such as a mountain, cliff, canyon, glacier, or island.
- colossal_scale: meaningfully beyond ordinary landform scale for this scene, such as a city, continent, moon, planet, or similarly enormous entity.
- ambiguous: no stable physical scale can be inferred, the meaning is abstract/non-physical, or the wording is too underspecified to classify responsibly.

Scale decision rule:
- the class names are scale bins, not object-category labels.
- classify by the typical physical extent of the represented thing in the scene.
- do not choose building_scale merely because something is architecturally a building.
- use infrastructure_scale when a built thing is typically substantially larger in spatial extent than one ordinary substantial building.
- for example, a stadium, large castle, or fortress complex can be infrastructure_scale even though it contains buildings.

Rules:
- honour explicit size modifiers when they clearly change the intended represented scale, for example toy, miniature, giant, pocket-sized, or city-sized.
- choose the nearest single class for a concrete physical meaning.
- use ambiguous for abstractions, events, weather, emotions, or genuinely scale-unstable concepts.
- do not explain.
- do not output punctuation, JSON, markdown, or any text other than the class name.
"""

# Pre-registered review expectations. A list means more than one classification is
# defensible. These labels are evaluation anchors, not training examples shown to Qwen.
CASES = [
    # seven renderer calibration anchors
    {"group": "anchors", "meaning": "coffee mug", "expected": ["handheld"]},
    {"group": "anchors", "meaning": "wooden chair", "expected": ["body_scale"]},
    {"group": "anchors", "meaning": "small tent", "expected": ["room_scale"]},
    {"group": "anchors", "meaning": "car", "expected": ["vehicle_scale"]},
    {"group": "anchors", "meaning": "house", "expected": ["building_scale"]},
    {"group": "anchors", "meaning": "castle", "expected": ["building_scale", "infrastructure_scale"]},
    {"group": "anchors", "meaning": "mountain", "expected": ["landform_scale"]},

    # clear micro
    {"group": "micro", "meaning": "ant", "expected": ["micro"]},
    {"group": "micro", "meaning": "grain of rice", "expected": ["micro"]},
    {"group": "micro", "meaning": "shirt button", "expected": ["micro"]},
    {"group": "micro", "meaning": "paperclip", "expected": ["micro", "handheld"]},
    {"group": "micro", "meaning": "coin", "expected": ["micro", "handheld"]},
    {"group": "micro", "meaning": "ladybird", "expected": ["micro"]},
    {"group": "micro", "meaning": "acorn", "expected": ["micro", "handheld"]},
    {"group": "micro", "meaning": "matchstick", "expected": ["micro"]},

    # clear handheld
    {"group": "handheld", "meaning": "smartphone", "expected": ["handheld"]},
    {"group": "handheld", "meaning": "camera", "expected": ["handheld"]},
    {"group": "handheld", "meaning": "book", "expected": ["handheld"]},
    {"group": "handheld", "meaning": "football", "expected": ["handheld"]},
    {"group": "handheld", "meaning": "backpack", "expected": ["handheld"]},
    {"group": "handheld", "meaning": "laptop", "expected": ["handheld"]},
    {"group": "handheld", "meaning": "kettle", "expected": ["handheld"]},
    {"group": "handheld", "meaning": "lantern", "expected": ["handheld"]},
    {"group": "handheld", "meaning": "guitar", "expected": ["handheld", "body_scale"]},
    {"group": "handheld", "meaning": "suitcase", "expected": ["handheld", "body_scale"]},

    # body and furniture scale
    {"group": "body", "meaning": "person", "expected": ["body_scale"]},
    {"group": "body", "meaning": "dog", "expected": ["body_scale"]},
    {"group": "body", "meaning": "horse", "expected": ["body_scale"]},
    {"group": "body", "meaning": "sofa", "expected": ["body_scale"]},
    {"group": "body", "meaning": "bed", "expected": ["body_scale"]},
    {"group": "body", "meaning": "dining table", "expected": ["body_scale"]},
    {"group": "body", "meaning": "grand piano", "expected": ["body_scale", "room_scale"]},
    {"group": "body", "meaning": "motorcycle", "expected": ["body_scale", "vehicle_scale"]},
    {"group": "body", "meaning": "cow", "expected": ["body_scale"]},
    {"group": "body", "meaning": "statue of a person", "expected": ["body_scale"]},

    # room and small shelter scale
    {"group": "room", "meaning": "garden shed", "expected": ["room_scale"]},
    {"group": "room", "meaning": "shipping container", "expected": ["room_scale"]},
    {"group": "room", "meaning": "bus shelter", "expected": ["room_scale"]},
    {"group": "room", "meaning": "market stall", "expected": ["room_scale"]},
    {"group": "room", "meaning": "kiosk", "expected": ["room_scale"]},
    {"group": "room", "meaning": "gazebo", "expected": ["room_scale"]},
    {"group": "room", "meaning": "small greenhouse", "expected": ["room_scale"]},
    {"group": "room", "meaning": "yurt", "expected": ["room_scale", "building_scale"]},

    # vehicles
    {"group": "vehicle", "meaning": "bus", "expected": ["vehicle_scale"]},
    {"group": "vehicle", "meaning": "lorry", "expected": ["vehicle_scale"]},
    {"group": "vehicle", "meaning": "train carriage", "expected": ["vehicle_scale"]},
    {"group": "vehicle", "meaning": "helicopter", "expected": ["vehicle_scale"]},
    {"group": "vehicle", "meaning": "passenger jet", "expected": ["vehicle_scale"]},
    {"group": "vehicle", "meaning": "fishing boat", "expected": ["vehicle_scale"]},
    {"group": "vehicle", "meaning": "cargo ship", "expected": ["vehicle_scale", "infrastructure_scale"]},
    {"group": "vehicle", "meaning": "tractor", "expected": ["vehicle_scale"]},

    # buildings
    {"group": "building", "meaning": "cottage", "expected": ["building_scale"]},
    {"group": "building", "meaning": "mosque", "expected": ["building_scale"]},
    {"group": "building", "meaning": "church", "expected": ["building_scale"]},
    {"group": "building", "meaning": "lighthouse", "expected": ["building_scale"]},
    {"group": "building", "meaning": "office block", "expected": ["building_scale"]},
    {"group": "building", "meaning": "watchtower", "expected": ["building_scale"]},
    {"group": "building", "meaning": "warehouse", "expected": ["building_scale", "infrastructure_scale"]},
    {"group": "building", "meaning": "skyscraper", "expected": ["building_scale", "infrastructure_scale"]},

    # infrastructure and large built complexes
    {"group": "infrastructure", "meaning": "stadium", "expected": ["infrastructure_scale"]},
    {"group": "infrastructure", "meaning": "major suspension bridge", "expected": ["infrastructure_scale"]},
    {"group": "infrastructure", "meaning": "hydroelectric dam", "expected": ["infrastructure_scale"]},
    {"group": "infrastructure", "meaning": "oil refinery", "expected": ["infrastructure_scale"]},
    {"group": "infrastructure", "meaning": "airport complex", "expected": ["infrastructure_scale"]},
    {"group": "infrastructure", "meaning": "fortress complex", "expected": ["infrastructure_scale"]},
    {"group": "infrastructure", "meaning": "railway station complex", "expected": ["infrastructure_scale"]},

    # natural landforms
    {"group": "landform", "meaning": "cliff", "expected": ["landform_scale"]},
    {"group": "landform", "meaning": "canyon", "expected": ["landform_scale"]},
    {"group": "landform", "meaning": "glacier", "expected": ["landform_scale"]},
    {"group": "landform", "meaning": "volcano", "expected": ["landform_scale"]},
    {"group": "landform", "meaning": "island", "expected": ["landform_scale", "colossal_scale"]},
    {"group": "landform", "meaning": "sand dune", "expected": ["landform_scale"]},
    {"group": "landform", "meaning": "waterfall", "expected": ["landform_scale"]},
    {"group": "landform", "meaning": "boulder", "expected": ["body_scale", "room_scale", "landform_scale"]},

    # deliberately colossal
    {"group": "colossal", "meaning": "city", "expected": ["colossal_scale"]},
    {"group": "colossal", "meaning": "continent", "expected": ["colossal_scale"]},
    {"group": "colossal", "meaning": "the Moon", "expected": ["colossal_scale"]},
    {"group": "colossal", "meaning": "planet", "expected": ["colossal_scale"]},
    {"group": "colossal", "meaning": "ocean", "expected": ["colossal_scale", "landform_scale"]},
    {"group": "colossal", "meaning": "entire mountain range", "expected": ["colossal_scale", "landform_scale"]},

    # explicit modifier stress
    {"group": "modifier", "meaning": "toy car", "expected": ["handheld"]},
    {"group": "modifier", "meaning": "miniature castle model", "expected": ["handheld"]},
    {"group": "modifier", "meaning": "pocket-sized mountain", "expected": ["handheld"]},
    {"group": "modifier", "meaning": "tiny house", "expected": ["building_scale", "room_scale"]},
    {"group": "modifier", "meaning": "giant mushroom", "expected": ["room_scale", "building_scale"]},
    {"group": "modifier", "meaning": "giant ant as tall as a person", "expected": ["body_scale"]},
    {"group": "modifier", "meaning": "city-sized spaceship", "expected": ["colossal_scale"]},
    {"group": "modifier", "meaning": "life-sized model car", "expected": ["vehicle_scale"]},

    # creative and non-physical meanings
    {"group": "ambiguous", "meaning": "memory", "expected": ["ambiguous"]},
    {"group": "ambiguous", "meaning": "loneliness", "expected": ["ambiguous"]},
    {"group": "ambiguous", "meaning": "storm", "expected": ["ambiguous"]},
    {"group": "ambiguous", "meaning": "moonlight", "expected": ["ambiguous"]},
    {"group": "ambiguous", "meaning": "danger", "expected": ["ambiguous"]},
    {"group": "ambiguous", "meaning": "the future", "expected": ["ambiguous"]},
    {"group": "ambiguous", "meaning": "portal", "expected": ["ambiguous", "body_scale", "room_scale"]},
    {"group": "ambiguous", "meaning": "forest", "expected": ["ambiguous", "landform_scale"]},
    {"group": "ambiguous", "meaning": "battlefield", "expected": ["ambiguous", "landform_scale"]},
    {"group": "ambiguous", "meaning": "the end of the world", "expected": ["ambiguous", "colossal_scale"]},
]


def strip_think(text):
    """remove qwen think blocks if a runtime emits them despite /no_think."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def normalize_class(text):
    cleaned = strip_think(text).strip().lower().strip("`* .,:;\"'\n\t")
    if cleaned in CLASSES:
        return cleaned
    # do not silently accept explanatory prose as a successful constrained output.
    return None


def check_lm_studio(timeout):
    try:
        response = requests.get(LMSTUDIO_MODELS_URL, timeout=timeout)
        response.raise_for_status()
        models = response.json().get("data", [])
        ids = [m.get("id") for m in models]
        if LMSTUDIO_MODEL not in ids:
            raise RuntimeError(f"{LMSTUDIO_MODEL} is not listed by LM Studio: {ids}")
    except requests.RequestException as exc:
        raise RuntimeError(f"LM Studio is not reachable at port 1234: {exc}") from exc


def classify(meaning, timeout):
    started = time.perf_counter()
    response = requests.post(
        LMSTUDIO_URL,
        json={
            "model": LMSTUDIO_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f'Assigned semantic meaning: "{meaning}"\n'
                        "Classify the intended represented real-world scale. /no_think"
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": 20,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=timeout,
    )
    latency_s = time.perf_counter() - started
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"]
    parsed = normalize_class(raw)
    return raw, parsed, latency_s


def make_summary(records):
    by_case = {}
    for row in records:
        by_case.setdefault(row["case_index"], []).append(row)

    case_summaries = []
    for case_index, rows in by_case.items():
        outputs = [row["parsed_class"] for row in rows]
        valid_outputs = [value for value in outputs if value is not None]
        agreement = len(set(valid_outputs)) == 1 and len(valid_outputs) == len(outputs)
        expected = rows[0]["expected"]
        expected_match = bool(valid_outputs) and all(value in expected for value in valid_outputs)
        case_summaries.append({
            "case_index": case_index,
            "group": rows[0]["group"],
            "meaning": rows[0]["meaning"],
            "expected": expected,
            "outputs": outputs,
            "valid_every_run": len(valid_outputs) == len(outputs),
            "agreement": agreement,
            "expected_match_every_run": expected_match,
        })

    valid_count = sum(1 for row in records if row["parsed_class"] is not None)
    total = len(records)
    agreement_count = sum(1 for row in case_summaries if row["agreement"])
    expected_count = sum(1 for row in case_summaries if row["expected_match_every_run"])

    return {
        "total_calls": total,
        "valid_enum_calls": valid_count,
        "valid_enum_rate": valid_count / total if total else 0.0,
        "cases": len(case_summaries),
        "fully_consistent_cases": agreement_count,
        "case_consistency_rate": agreement_count / len(case_summaries) if case_summaries else 0.0,
        "expected_match_cases": expected_count,
        "expected_match_rate": expected_count / len(case_summaries) if case_summaries else 0.0,
        "case_results": case_summaries,
    }


def write_outputs(output_dir, records, summary, args):
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "created_at": datetime.now().astimezone().isoformat(),
        "model": LMSTUDIO_MODEL,
        "url": LMSTUDIO_URL,
        "temperature": 0.0,
        "max_tokens": 20,
        "runs_per_case": args.runs,
        "requested_limit": args.limit,
        "class_names": list(CLASSES),
        "note": "Expected labels were pre-registered before inference and are evaluation anchors, not prompt examples.",
    }

    with open(output_dir / "results.json", "w") as f:
        json.dump({"metadata": metadata, "summary": summary, "records": records}, f, indent=2)

    with open(output_dir / "results.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_index",
                "group",
                "meaning",
                "expected",
                "run",
                "raw_output",
                "parsed_class",
                "valid_enum",
                "expected_match",
                "latency_s",
                "error",
            ],
        )
        writer.writeheader()
        for row in records:
            csv_row = dict(row)
            csv_row["expected"] = "|".join(row["expected"])
            writer.writerow(csv_row)

    with open(output_dir / "summary.txt", "w") as f:
        f.write(f"calls: {summary['total_calls']}\n")
        f.write(f"valid enum: {summary['valid_enum_calls']}/{summary['total_calls']} ({summary['valid_enum_rate']:.1%})\n")
        f.write(f"consistent cases: {summary['fully_consistent_cases']}/{summary['cases']} ({summary['case_consistency_rate']:.1%})\n")
        f.write(f"expected-match cases: {summary['expected_match_cases']}/{summary['cases']} ({summary['expected_match_rate']:.1%})\n")
        f.write("\nquestionable cases:\n")
        for case in summary["case_results"]:
            if not case["agreement"] or not case["expected_match_every_run"]:
                f.write(
                    f"- {case['meaning']} | expected={case['expected']} | outputs={case['outputs']} | "
                    f"consistent={case['agreement']}\n"
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3, help="repeated calls per meaning")
    parser.add_argument("--limit", type=int, default=None, help="only run the first N cases")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--output",
        default="scale_classification_results",
        help="output directory, relative to current working directory unless absolute",
    )
    args = parser.parse_args()

    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")

    cases = CASES[: args.limit] if args.limit else CASES
    print(f"[study] cases={len(cases)} runs={args.runs} calls={len(cases) * args.runs}")
    print(f"[study] model={LMSTUDIO_MODEL}")
    check_lm_studio(args.timeout)
    print("[study] LM Studio reachable and model listed")

    records = []
    for case_index, case in enumerate(cases, start=1):
        for run in range(1, args.runs + 1):
            error = ""
            raw = ""
            parsed = None
            latency_s = 0.0
            try:
                raw, parsed, latency_s = classify(case["meaning"], args.timeout)
            except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
                error = str(exc)

            expected_match = parsed in case["expected"] if parsed is not None else False
            record = {
                "case_index": case_index,
                "group": case["group"],
                "meaning": case["meaning"],
                "expected": case["expected"],
                "run": run,
                "raw_output": raw,
                "parsed_class": parsed,
                "valid_enum": parsed is not None,
                "expected_match": expected_match,
                "latency_s": round(latency_s, 3),
                "error": error,
            }
            records.append(record)

            shown = parsed if parsed is not None else f"INVALID: {raw!r} {error}".strip()
            marker = "ok" if expected_match else "review"
            print(
                f"[{case_index:02d}/{len(cases):02d} run {run}/{args.runs}] "
                f"{case['meaning']!r} -> {shown} ({latency_s:.2f}s) [{marker}]"
            )

    summary = make_summary(records)
    output_dir = Path(args.output)
    write_outputs(output_dir, records, summary, args)

    print("\n[summary]")
    print(f"valid enum: {summary['valid_enum_calls']}/{summary['total_calls']} ({summary['valid_enum_rate']:.1%})")
    print(
        f"consistent cases: {summary['fully_consistent_cases']}/{summary['cases']} "
        f"({summary['case_consistency_rate']:.1%})"
    )
    print(
        f"expected-match cases: {summary['expected_match_cases']}/{summary['cases']} "
        f"({summary['expected_match_rate']:.1%})"
    )
    print(f"saved: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
