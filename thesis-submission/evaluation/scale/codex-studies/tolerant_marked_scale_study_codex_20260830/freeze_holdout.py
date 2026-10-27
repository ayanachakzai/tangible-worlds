#!/usr/bin/env python3
"""Freeze the tolerant marked-scale oracle before candidate parser execution."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HOLDOUT_OUT = ROOT / "holdout_cases.json"
VOICE_OUT = ROOT / "voice_transcript_cases.json"

SCALES = {
    "tiny": ("very_small", 0.35),
    "miniature": ("very_small", 0.35),
    "small": ("small", 0.65),
    "big": ("large", 1.80),
    "large": ("large", 1.80),
    "huge": ("very_large", 3.00),
}


def assignment(
    meaning: str,
    object_key: str,
    generation: str | None = None,
    modifier: str | None = None,
) -> dict:
    if modifier is None:
        return {
            "route": "assignment",
            "object_key": object_key,
            "meaning": meaning,
            "generation_meaning": meaning,
            "explicit_scale_intent": "neutral",
            "target_size": 1.0,
            "scale_source": "neutral_default",
            "explicit_detected": False,
        }
    intent, target = SCALES[modifier]
    return {
        "route": "assignment",
        "object_key": object_key,
        "meaning": meaning,
        "generation_meaning": generation,
        "explicit_scale_intent": intent,
        "target_size": target,
        "scale_source": "participant_marked",
        "explicit_detected": True,
    }


def atmosphere() -> dict:
    return {
        "route": "atmosphere",
        "object_key": None,
        "meaning": None,
        "generation_meaning": None,
        "explicit_scale_intent": None,
        "target_size": None,
        "scale_source": None,
        "explicit_detected": False,
    }


cases: list[dict] = []


def add_case(
    case_id: str,
    category: str,
    mode: str,
    text: str,
    expected_a: dict,
    expected_b: dict | None = None,
    typed_key: str | None = None,
    tags: list[str] | None = None,
) -> None:
    cases.append({
        "id": case_id,
        "category": category,
        "input_mode": "voice" if mode == "atmosphere" else mode,
        "typed_object_key": typed_key if mode == "typed" else None,
        "text": text,
        "tags": tags or [],
        "expected": {"A": expected_a, "B": expected_b or expected_a},
    })


def add_neutral(
    case_id: str,
    category: str,
    mode: str,
    text: str,
    meaning: str | None = None,
    object_key: str = "4",
    tags: list[str] | None = None,
) -> None:
    if mode == "atmosphere":
        expected = atmosphere()
    else:
        expected = assignment(meaning if meaning is not None else text.strip(), object_key)
    add_case(case_id, category, mode, text, expected, typed_key=object_key, tags=tags)


# 36 common positives: six orthographic/input variants for every size word.
# Candidate A and B both accept these because the participant says "scale".
for index, modifier in enumerate(SCALES, start=1):
    intent_word = modifier.upper() if modifier in {"tiny", "big", "huge"} else modifier.title()
    prefix = f"P{index}"
    if modifier == "tiny":
        examples = [
            ("01", "voice", "object four is a car, scale tiny", "a car, scale tiny", "a car", "4", ["voice_required", "comma"]),
            ("02", "voice", "object four is a car scale tiny", "a car scale tiny", "a car", "4", ["voice_required", "no_comma"]),
            ("03", "voice", "object 4 is a car scale tiny", "a car scale tiny", "a car", "4", ["voice_required", "numeric_id", "no_comma"]),
            ("04", "typed", "car, scale tiny", "car, scale tiny", "car", "2", ["comma", "no_article"]),
            ("05", "typed", "car scale tiny", "car scale tiny", "car", "2", ["no_comma", "no_article"]),
            ("06", "typed", "a large scale map scale tiny", "a large scale map scale tiny", "a large scale map", "9", ["semantic_scale_in_base", "no_comma"]),
        ]
    else:
        examples = [
            ("01", "typed", f"a car, scale {modifier}", f"a car, scale {modifier}", "a car", "2", ["comma"]),
            ("02", "typed", f"car scale {modifier}", f"car scale {modifier}", "car", "3", ["no_comma", "no_article"]),
            ("03", "voice", f"object four is a castle scale {modifier}", f"a castle scale {modifier}", "a castle", "4", ["word_id", "no_comma"]),
            ("04", "voice", f"object 05 is an old bridge, scale {modifier}.", f"an old bridge, scale {modifier}", "an old bridge", "5", ["numeric_id", "comma", "punctuation"]),
            ("05", "typed", f"  A VFX proxy,   ScAlE   {intent_word}!  ", f"A VFX proxy,   ScAlE   {intent_word}!", "A VFX proxy", "6", ["mixed_case", "extra_spaces", "punctuation"]),
            ("06", "typed", f"a luminous city, with bridges, towers, and drifting banners scale {modifier}?", f"a luminous city, with bridges, towers, and drifting banners scale {modifier}?", "a luminous city, with bridges, towers, and drifting banners", "7", ["internal_commas", "long_creative", "no_comma", "punctuation"]),
        ]
    for suffix, mode, text, original, generation, key, tags in examples:
        expected = assignment(original, key, generation, modifier)
        add_case(prefix + suffix, "valid_scale_marker", mode, text, expected, typed_key=key, tags=tags)


# 12 observed-transcript alias positives for Candidate B only. Candidate A
# deliberately treats these strings as neutral.
for index, modifier in enumerate(SCALES, start=1):
    typed_text = f"a car scaled {modifier}"
    typed_neutral = assignment(typed_text, "4")
    typed_b = assignment(typed_text, "4", "a car", modifier)
    add_case(
        f"B{index}1", "valid_scaled_alias_b", "typed", typed_text,
        typed_neutral, typed_b, typed_key="4", tags=["scaled_alias"]
    )
    voice_text = f"object four is a car scaled {modifier}."
    voice_original = f"a car scaled {modifier}"
    voice_neutral = assignment(voice_original, "4")
    voice_b = assignment(voice_original, "4", "a car", modifier)
    tags = ["scaled_alias", "voice_required"] if modifier == "tiny" else ["scaled_alias", "word_id"]
    add_case(f"B{index}2", "valid_scaled_alias_b", "voice", voice_text, voice_neutral, voice_b, tags=tags)


# 12 bare neutral assignments.
bare_cases = [
    ("N01", "typed", "a car", None, "1"),
    ("N02", "voice", "object four is a car", "a car", "4"),
    ("N03", "voice", "Object 004 is Big Ben.", "Big Ben", "4"),
    ("N04", "typed", "a castle with a tiny window", None, "5"),
    ("N05", "voice", "object six is a miniature painting", "a miniature painting", "6"),
    ("N06", "typed", "large language model", None, "7"),
    ("N07", "voice", "object eight is small talk stage", "small talk stage", "8"),
    ("N08", "typed", "a huge fan of castles", None, "9"),
    ("N09", "voice", "object ten is a big wheel clock", "a big wheel clock", "10"),
    ("N10", "typed", "toy car, bridge, and house", None, "11"),
    ("N11", "voice", "object one is an atmospheric VFX proxy", "an atmospheric VFX proxy", "1"),
    ("N12", "typed", "  a neutral mushroom.  ", "a neutral mushroom.", "12"),
]
for case_id, mode, text, original, key in bare_cases:
    add_neutral(case_id, "bare_assignment", mode, text, original, key)


# 10 normal atmosphere commands; none match the outer assignment route.
for index, text in enumerate([
    "make it foggy",
    "make it tiny and misty",
    "scale the rain down",
    "add huge lightning",
    "make the world feel small",
    "object four moves near object five",
    "turn the sky orange",
    "make it a large storm",
    "scale tiny",
    "a car scale tiny",
], start=1):
    add_neutral(f"T{index:02d}", "atmosphere_command", "atmosphere", text)


# 14 ordinary semantic uses of scale. Exact terminal "scale <size>" is the
# reserved control form; quoted/non-terminal occurrences remain semantic.
semantic_scale = [
    ("S01", "voice", "object four is a tiny scale model car", "a tiny scale model car", ["voice_required", "scale_model"]),
    ("S02", "voice", "object four is a scale model car", "a scale model car", ["voice_required", "scale_model"]),
    ("S03", "voice", "object four is a large scale map", "a large scale map", ["voice_required", "large_scale"]),
    ("S04", "typed", "scale model of a castle", None, ["scale_model"]),
    ("S05", "typed", "small-scale model", None, ["hyphenated"]),
    ("S06", "typed", "a car on a large scale", None, ["scale_semantic"]),
    ("S07", "typed", "a car with a tiny scale", None, ["scale_semantic"]),
    ("S08", "typed", "a scale tiny car", None, ["marker_not_terminal"]),
    ("S09", "typed", "Big Ben scale model", None, ["proper_noun", "scale_model"]),
    ("S10", "typed", "large language model scale diagram", None, ["scale_semantic"]),
    ("S11", "typed", "miniature painting scale study", None, ["scale_semantic"]),
    ("S12", "typed", "a sign reading 'scale tiny'", None, ["quoted_marker"]),
    ("S13", "typed", "a label reading scale tiny in blue", None, ["marker_not_terminal"]),
    ("S14", "voice", "object nine is a city rendered at architectural scale", "a city rendered at architectural scale", ["scale_semantic"]),
]
for case_id, mode, text, original, tags in semantic_scale:
    add_neutral(case_id, "semantic_scale_phrase", mode, text, original, "4" if mode == "voice" else "2", tags)


# 12 semantic uses of "scaled". The first six intentionally end in a
# supported size word and expose Candidate B's unavoidable ambiguity.
semantic_scaled = [
    ("D01", "typed", "a VFX asset already scaled tiny", None, ["terminal_scaled_semantic"]),
    ("D02", "voice", "object four is a forced-perspective castle scaled small", "a forced-perspective castle scaled small", ["terminal_scaled_semantic"]),
    ("D03", "typed", "a source mesh uniformly scaled big", None, ["terminal_scaled_semantic"]),
    ("D04", "voice", "object six is a background house intentionally scaled large", "a background house intentionally scaled large", ["terminal_scaled_semantic"]),
    ("D05", "typed", "a toy car prop scaled miniature", None, ["terminal_scaled_semantic"]),
    ("D06", "voice", "object eight is a bridge proxy scaled huge", "a bridge proxy scaled huge", ["terminal_scaled_semantic"]),
    ("D07", "voice", "object four is a car scaled model", "a car scaled model", ["voice_required", "scaled_model"]),
    ("D08", "typed", "scaled model car", None, ["scaled_model"]),
    ("D09", "typed", "a scaled replica of Big Ben", None, ["scaled_replica", "proper_noun"]),
    ("D10", "typed", "a mesh scaled for projection", None, ["scaled_semantic"]),
    ("D11", "typed", "a scaled-down miniature painting", None, ["hyphenated"]),
    ("D12", "typed", "the Scaled Composites aircraft", None, ["proper_noun"]),
]
for case_id, mode, text, original, tags in semantic_scaled:
    add_neutral(case_id, "semantic_scaled_phrase", mode, text, original, "4" if mode == "voice" else "2", tags)


# 10 malformed or non-generalised forms.
malformed = [
    ("M01", "typed", "a car scale", None),
    ("M02", "typed", "a car scale enormous", None),
    ("M03", "voice", "object four is a car scale tiny and huge", "a car scale tiny and huge"),
    ("M04", "typed", "a car, scale tiny, with red paint", None),
    ("M05", "typed", "a car scaling tiny", None),
    ("M06", "voice", "object four is a car scale it tiny", "a car scale it tiny"),
    ("M07", "typed", "a car make it tiny", None),
    ("M08", "typed", "a car scales tiny", None),
    ("M09", "voice", "object five is a car scale very small", "a car scale very small"),
    ("M10", "typed", "a car; scale tiny", None),
]
for case_id, mode, text, original in malformed:
    add_neutral(case_id, "malformed_marker", mode, text, original, "4" if mode == "voice" else "2")


# 8 multiple/conflicting forms: refuse instead of taking the final token.
conflicts = [
    ("C01", "typed", "a car scale tiny scale huge", None),
    ("C02", "voice", "object four is a car, scale tiny, scale huge", "a car, scale tiny, scale huge"),
    ("C03", "typed", "a car scale tiny scaled huge", None),
    ("C04", "voice", "object four is a car scaled tiny scale huge", "a car scaled tiny scale huge"),
    ("C05", "typed", "a car scale small, make it huge", None),
    ("C06", "typed", "a car make it small scale huge", None),
    ("C07", "voice", "object six is a car scale tiny, with red paint", "a car scale tiny, with red paint"),
    ("C08", "typed", "a car scale tiny, scale tiny", None),
]
for case_id, mode, text, original in conflicts:
    add_neutral(case_id, "conflicting_marker", mode, text, original, "4" if mode == "voice" else "2")


# 6 unsupported synonyms/comparatives.
for index, text in enumerate([
    "a car scale teeny",
    "a car scale enormous",
    "a car scale little",
    "a car scale colossal",
    "a car scale bigger",
    "a car scale very large",
], start=1):
    add_neutral(f"U{index:02d}", "unsupported_synonym", "typed", text, object_key="2")


assert len(cases) == 120, len(cases)
if HOLDOUT_OUT.exists() or VOICE_OUT.exists():
    raise SystemExit("refusing to overwrite frozen holdout outputs")

payload = {
    "study": "Tangible Worlds tolerant marked-scale grammar qualification",
    "frozen_on": "2026-08-30",
    "case_count": len(cases),
    "candidate_A": "optional comma plus terminal scale <supported-size>",
    "candidate_B": "Candidate A plus terminal scaled <supported-size> transcript alias",
    "oracle_note": "Expected records were frozen before candidate parser code existed or ran.",
    "cases": cases,
}
HOLDOUT_OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

required_voice_ids = ["P101", "P102", "B12", "P103", "S01", "S02", "S03", "D07"]
voice_payload = {
    "case_count": len(required_voice_ids),
    "case_ids": required_voice_ids,
    "cases": [next(case for case in cases if case["id"] == case_id) for case_id in required_voice_ids],
}
VOICE_OUT.write_text(json.dumps(voice_payload, indent=2) + "\n", encoding="utf-8")
print(f"frozen {len(cases)} cases and {len(required_voice_ids)} required voice transcripts")
