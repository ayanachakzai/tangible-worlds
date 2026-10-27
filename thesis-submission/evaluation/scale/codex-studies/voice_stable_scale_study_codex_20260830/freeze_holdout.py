#!/usr/bin/env python3
"""Freeze the voice-stable marker oracle before candidate parser execution."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "holdout_cases.json"

TARGETS = {
    "tiny": ("very_small", 0.35),
    "miniature": ("very_small", 0.35),
    "small": ("small", 0.65),
    "big": ("large", 1.80),
    "large": ("large", 1.80),
    "huge": ("very_large", 3.00),
}


def assignment(meaning: str, key: str, generation: str | None = None, modifier: str | None = None) -> dict:
    if modifier is None:
        return {
            "route": "assignment", "object_key": key, "meaning": meaning,
            "generation_meaning": meaning, "explicit_scale_intent": "neutral",
            "target_size": 1.0, "scale_source": "neutral_default",
            "explicit_detected": False,
        }
    intent, target = TARGETS[modifier]
    return {
        "route": "assignment", "object_key": key, "meaning": meaning,
        "generation_meaning": generation, "explicit_scale_intent": intent,
        "target_size": target, "scale_source": "participant_marked",
        "explicit_detected": True,
    }


def atmosphere() -> dict:
    return {
        "route": "atmosphere", "object_key": None, "meaning": None,
        "generation_meaning": None, "explicit_scale_intent": None,
        "target_size": None, "scale_source": None, "explicit_detected": False,
    }


cases: list[dict] = []


def add(case_id: str, category: str, mode: str, text: str, expected: dict, candidate: str | None = None, typed_key: str | None = None, tags: list[str] | None = None) -> None:
    if candidate is None:
        expected_by_candidate = {"A": expected, "B": expected, "C": expected}
    else:
        neutral = assignment(expected["meaning"], expected["object_key"])
        expected_by_candidate = {"A": neutral, "B": neutral, "C": neutral}
        expected_by_candidate[candidate] = expected
    cases.append({
        "id": case_id, "category": category,
        "input_mode": "voice" if mode == "atmosphere" else mode,
        "typed_object_key": typed_key if mode == "typed" else None,
        "text": text, "tags": tags or [], "expected": expected_by_candidate,
    })


def add_neutral(case_id: str, category: str, mode: str, text: str, meaning: str | None = None, key: str = "2", tags: list[str] | None = None) -> None:
    expected = atmosphere() if mode == "atmosphere" else assignment(meaning if meaning is not None else text.strip(), key)
    add(case_id, category, mode, text, expected, typed_key=key, tags=tags)


# 24 positives per candidate: four variations for every supported word.
markers = {"A": "size", "B": "size is", "C": "scale"}
for candidate, marker in markers.items():
    for word_index, modifier in enumerate(TARGETS, start=1):
        prefix = f"{candidate}{word_index}"
        examples = [
            ("1", "typed", f"a car {marker} {modifier}", f"a car {marker} {modifier}", "a car", "2", ["typed", "article"]),
            ("2", "typed", f"  Car,   {marker.upper()}   {modifier.upper()}!  ", f"Car,   {marker.upper()}   {modifier.upper()}!", "Car", "3", ["case", "spacing", "punctuation", "comma"]),
            ("3", "voice", f"object two is a castle {marker} {modifier}", f"a castle {marker} {modifier}", "a castle", "2", ["word_id", "voice"]),
            ("4", "voice", f"object 04 is a luminous VFX city, with towers, bridges, and banners {marker} {modifier}.", f"a luminous VFX city, with towers, bridges, and banners {marker} {modifier}", "a luminous VFX city, with towers, bridges, and banners", "4", ["numeric_id", "voice", "internal_commas", "long_vfx"]),
        ]
        for suffix, mode, text, original, generation, key, tags in examples:
            add(prefix + suffix, f"valid_candidate_{candidate.lower()}", mode, text, assignment(original, key, generation, modifier), candidate, key, tags)


# 10 bare assignments.
bare = [
    ("N01", "typed", "a car", None, "1"),
    ("N02", "voice", "object two is a car", "a car", "2"),
    ("N03", "voice", "object 4 is Big Ben.", "Big Ben", "4"),
    ("N04", "typed", "a miniature painting", None, "5"),
    ("N05", "voice", "object six is a large language model", "a large language model", "6"),
    ("N06", "typed", "a tiny window on a house", None, "7"),
    ("N07", "voice", "object eight is a huge fan of castles", "a huge fan of castles", "8"),
    ("N08", "typed", "small talk stage", None, "9"),
    ("N09", "voice", "object ten is an ordinary bridge", "an ordinary bridge", "10"),
    ("N10", "typed", "  a neutral mushroom.  ", "a neutral mushroom.", "11"),
]
for case_id, mode, text, meaning, key in bare:
    add_neutral(case_id, "bare_assignment", mode, text, meaning, key)


# 10 atmosphere commands that do not match the outer assignment route.
for i, text in enumerate([
    "make it foggy", "make it feel tiny", "increase the size of the moon",
    "add huge lightning", "turn the sky orange", "scale the rain down",
    "make the mist larger", "object two moves near object three",
    "size tiny", "a car size tiny",
], start=1):
    add_neutral(f"T{i:02d}", "atmosphere_command", "atmosphere", text)


# 20 ordinary semantic uses of size/sized. Six natural terminal phrases expose
# B, and three common label/apparel phrases expose A.
semantic_size = [
    ("S01", "typed", "life size statue", None, ["life_size"]),
    ("S02", "typed", "full size car", None, ["full_size"]),
    ("S03", "typed", "size comparison chart", None, ["comparison"]),
    ("S04", "typed", "a size tiny label", None, ["marker_not_terminal"]),
    ("S05", "typed", "a tiny size label", None, ["marker_not_terminal"]),
    ("S06", "typed", "the size is tiny on the label", None, ["marker_not_terminal"]),
    ("S07", "typed", "a medium-sized prop", None, ["sized"]),
    ("S08", "voice", "object two is a life sized statue", "a life sized statue", ["sized", "voice"]),
    ("S09", "typed", "a chart comparing object size", None, ["size_semantic"]),
    ("S10", "typed", "a label that says size tiny in blue", None, ["marker_not_terminal"]),
    ("S11", "typed", "a house whose size is tiny", None, ["candidate_b_collision"]),
    ("S12", "typed", "a model whose size is miniature", None, ["candidate_b_collision"]),
    ("S13", "typed", "a VFX proxy whose size is small", None, ["candidate_b_collision"]),
    ("S14", "typed", "a wheel whose size is big", None, ["candidate_b_collision"]),
    ("S15", "typed", "a prop whose size is large", None, ["candidate_b_collision"]),
    ("S16", "typed", "a backdrop whose size is huge", None, ["candidate_b_collision"]),
    ("S17", "typed", "a T-shirt size small", None, ["candidate_a_collision"]),
    ("S18", "typed", "a costume size large", None, ["candidate_a_collision"]),
    ("S19", "typed", "a prop label reading size tiny", None, ["candidate_a_collision"]),
    ("S20", "typed", "the object is standard size", None, ["size_semantic"]),
]
for case_id, mode, text, meaning, tags in semantic_size:
    add_neutral(case_id, "semantic_size_phrase", mode, text, meaning, "2", tags)


# 12 semantic scale/scaled cases retained from earlier failure families.
semantic_scale = [
    ("L01", "typed", "scale model car", None),
    ("L02", "typed", "scaled mesh", None),
    ("L03", "typed", "large scale map", None),
    ("L04", "typed", "small-scale model", None),
    ("L05", "typed", "a scaled replica of Big Ben", None),
    ("L06", "typed", "a car already scaled tiny", None),
    ("L07", "typed", "a source mesh uniformly scaled big", None),
    ("L08", "typed", "a scale tiny label", None),
    ("L09", "typed", "a tiny scale label", None),
    ("L10", "voice", "object two is a large scale map", "a large scale map"),
    ("L11", "typed", "Big Ben scale model", None),
    ("L12", "typed", "a scale study for a miniature painting", None),
]
for case_id, mode, text, meaning in semantic_scale:
    add_neutral(case_id, "semantic_scale_phrase", mode, text, meaning, "2")


# 10 malformed/non-generalised forms.
malformed = [
    "a car size", "a car size is", "a car scale", "a car sized tiny",
    "a car scaled tiny", "a car size very small", "a car size is enormous",
    "a car size tiny please", "a car; size tiny", "a car scaling tiny",
]
for i, text in enumerate(malformed, start=1):
    add_neutral(f"M{i:02d}", "malformed_marker", "typed", text, key="2")


# 8 multiple/conflicting terminal controls.
conflicts = [
    "a car size tiny size huge", "a car size is tiny size is huge",
    "a car scale tiny scale huge", "a car size tiny scale huge",
    "a car scale tiny size huge", "a car size is small scale huge",
    "a car size tiny, with red paint", "a car scale tiny size is huge",
]
for i, text in enumerate(conflicts, start=1):
    add_neutral(f"C{i:02d}", "conflicting_marker", "typed", text, key="2")


# 6 unsupported synonyms/comparatives.
for i, text in enumerate([
    "a car size teeny", "a car size is enormous", "a car scale colossal",
    "a car size little", "a car size bigger", "a car scale very large",
], start=1):
    add_neutral(f"U{i:02d}", "unsupported_synonym", "typed", text, key="2")


assert len(cases) == 148, len(cases)
if OUT.exists():
    raise SystemExit(f"refusing to overwrite frozen holdout: {OUT}")
OUT.write_text(json.dumps({
    "study": "Tangible Worlds voice-stable marked size grammar study",
    "frozen_on": "2026-08-30",
    "case_count": len(cases),
    "candidates": {
        "A": "terminal size <supported-value>",
        "B": "terminal size is <supported-value>",
        "C": "current terminal scale <supported-value>",
    },
    "oracle_note": "Expected scale outputs were frozen before candidate parser execution.",
    "cases": cases,
}, indent=2) + "\n", encoding="utf-8")
print(f"frozen {len(cases)} cases at {OUT}")
