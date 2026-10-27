#!/usr/bin/env python3
"""Freeze the marked-scale qualification holdout before parser execution.

This script intentionally refuses to overwrite the preregistration. The
generated JSON is the test oracle; the candidate parser never imports this
module or derives expected values from its own output.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "holdout_cases.json"

SCALE = {
    "tiny": ("very_small", 0.35),
    "miniature": ("very_small", 0.35),
    "small": ("small", 0.65),
    "big": ("large", 1.80),
    "large": ("large", 1.80),
    "huge": ("very_large", 3.00),
}


def assignment_expectation(
    meaning: str,
    generation_meaning: str | None = None,
    modifier: str | None = None,
    object_key: str = "2",
) -> dict:
    if modifier is None:
        intent, target, explicit, source = "neutral", 1.0, False, "neutral_default"
        generation_meaning = meaning
    else:
        intent, target = SCALE[modifier]
        explicit, source = True, "participant_marked"
    return {
        "route": "assignment",
        "object_key": object_key,
        "meaning": meaning,
        "generation_meaning": generation_meaning,
        "explicit_scale_intent": intent,
        "target_size": target,
        "scale_source": source,
        "explicit_detected": explicit,
    }


def atmosphere_expectation() -> dict:
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


def add_valid(
    case_id: str,
    grammar: str,
    mode: str,
    text: str,
    original: str,
    generation: str,
    modifier: str,
    object_key: str = "2",
    category: str | None = None,
) -> None:
    explicit = assignment_expectation(original, generation, modifier, object_key)
    neutral = assignment_expectation(original, object_key=object_key)
    cases.append({
        "id": case_id,
        "category": category or f"valid_grammar_{grammar.lower()}",
        "input_mode": mode,
        "typed_object_key": object_key if mode == "typed" else None,
        "text": text,
        "expected": {
            "A": explicit if grammar == "A" else neutral,
            "B": explicit if grammar == "B" else neutral,
        },
    })


def add_neutral(
    case_id: str,
    category: str,
    mode: str,
    text: str,
    original: str | None = None,
    object_key: str = "2",
) -> None:
    if mode == "atmosphere":
        expected = atmosphere_expectation()
        input_mode = "voice"
        typed_key = None
    else:
        expected = assignment_expectation(original if original is not None else text, object_key=object_key)
        input_mode = mode
        typed_key = object_key if mode == "typed" else None
    cases.append({
        "id": case_id,
        "category": category,
        "input_mode": input_mode,
        "typed_object_key": typed_key,
        "text": text,
        "expected": {"A": expected, "B": expected},
    })


# Grammar A positives. The exact reserved suffix is ", scale <word>".
add_valid("A01", "A", "voice", "object two is a castle, scale tiny", "a castle, scale tiny", "a castle", "tiny")
add_valid("A02", "A", "typed", "castle, scale miniature", "castle, scale miniature", "castle", "miniature", "7")
add_valid("A03", "A", "voice", "Object 003 is toy car, scale tiny.", "toy car, scale tiny", "toy car", "tiny", "3")
add_valid("A04", "A", "typed", "  a red mushroom, scale miniature  ", "a red mushroom, scale miniature", "a red mushroom", "miniature", "10")
add_valid("A05", "A", "voice", "OBJECT NUMBER FOUR IS THE HOUSE, SCALE TINY!!!", "THE HOUSE, SCALE TINY", "THE HOUSE", "tiny", "4")
add_valid("A06", "A", "typed", "bridge, scale small", "bridge, scale small", "bridge", "small", "1")
add_valid("A07", "A", "voice", "object five is a narrow stone bridge, scale small", "a narrow stone bridge, scale small", "a narrow stone bridge", "small", "5")
add_valid("A08", "A", "typed", "the house with three chimneys, scale small?", "the house with three chimneys, scale small?", "the house with three chimneys", "small", "8")
add_valid("A09", "A", "voice", "  object six is mushroom,   scale   small.  ", "mushroom,   scale   small", "mushroom", "small", "6")
add_valid("A10", "A", "typed", "a tower, with a clock, scale small", "a tower, with a clock, scale small", "a tower, with a clock", "small", "9")
add_valid("A11", "A", "voice", "object seven is Big Ben, scale big", "Big Ben, scale big", "Big Ben", "big", "7")
add_valid("A12", "A", "typed", "a castle on a rocky island, scale large", "a castle on a rocky island, scale large", "a castle on a rocky island", "large", "11")
add_valid("A13", "A", "voice", "object 8 is a blue, two-door toy car, scale LARGE.", "a blue, two-door toy car, scale LARGE", "a blue, two-door toy car", "large", "8")
add_valid("A14", "A", "typed", "mushroom-shaped observatory,scale big!", "mushroom-shaped observatory,scale big!", "mushroom-shaped observatory", "big", "12")
add_valid("A15", "A", "voice", "object nine is the house that Jack built, scale large", "the house that Jack built, scale large", "the house that Jack built", "large", "9")
add_valid("A16", "A", "typed", "castle, scale huge", "castle, scale huge", "castle", "huge", "2")
add_valid("A17", "A", "voice", "object ten is an old wooden bridge, scale huge", "an old wooden bridge, scale huge", "an old wooden bridge", "huge", "10")
add_valid("A18", "A", "typed", "a house, a garden, and a gate, scale huge.", "a house, a garden, and a gate, scale huge.", "a house, a garden, and a gate", "huge", "13")
add_valid("A19", "A", "voice", "object 14 is mushroom with a tiny door, SCALE HUGE?", "mushroom with a tiny door, SCALE HUGE", "mushroom with a tiny door", "huge", "14")
add_valid("A20", "A", "typed", "Toy Car,   ScAlE   HuGe", "Toy Car,   ScAlE   HuGe", "Toy Car", "huge", "15")

# Grammar B positives. The exact reserved suffix is ", make it <word>".
add_valid("B01", "B", "voice", "object two is a castle, make it tiny", "a castle, make it tiny", "a castle", "tiny")
add_valid("B02", "B", "typed", "castle, make it miniature", "castle, make it miniature", "castle", "miniature", "7")
add_valid("B03", "B", "voice", "Object 003 is toy car, make it tiny.", "toy car, make it tiny", "toy car", "tiny", "3")
add_valid("B04", "B", "typed", "  a red mushroom, make it miniature  ", "a red mushroom, make it miniature", "a red mushroom", "miniature", "10")
add_valid("B05", "B", "voice", "OBJECT NUMBER FOUR IS THE HOUSE, MAKE IT TINY!!!", "THE HOUSE, MAKE IT TINY", "THE HOUSE", "tiny", "4")
add_valid("B06", "B", "typed", "bridge, make it small", "bridge, make it small", "bridge", "small", "1")
add_valid("B07", "B", "voice", "object five is a narrow stone bridge, make it small", "a narrow stone bridge, make it small", "a narrow stone bridge", "small", "5")
add_valid("B08", "B", "typed", "the house with three chimneys, make it small?", "the house with three chimneys, make it small?", "the house with three chimneys", "small", "8")
add_valid("B09", "B", "voice", "  object six is mushroom,   make   it   small.  ", "mushroom,   make   it   small", "mushroom", "small", "6")
add_valid("B10", "B", "typed", "a tower, with a clock, make it small", "a tower, with a clock, make it small", "a tower, with a clock", "small", "9")
add_valid("B11", "B", "voice", "object seven is Big Ben, make it big", "Big Ben, make it big", "Big Ben", "big", "7")
add_valid("B12", "B", "typed", "a castle on a rocky island, make it large", "a castle on a rocky island, make it large", "a castle on a rocky island", "large", "11")
add_valid("B13", "B", "voice", "object 8 is a blue, two-door toy car, make it LARGE.", "a blue, two-door toy car, make it LARGE", "a blue, two-door toy car", "large", "8")
add_valid("B14", "B", "typed", "mushroom-shaped observatory,make it big!", "mushroom-shaped observatory,make it big!", "mushroom-shaped observatory", "big", "12")
add_valid("B15", "B", "voice", "object nine is the house that Jack built, make it large", "the house that Jack built, make it large", "the house that Jack built", "large", "9")
add_valid("B16", "B", "typed", "castle, make it huge", "castle, make it huge", "castle", "huge", "2")
add_valid("B17", "B", "voice", "object ten is an old wooden bridge, make it huge", "an old wooden bridge, make it huge", "an old wooden bridge", "huge", "10")
add_valid("B18", "B", "typed", "a house, a garden, and a gate, make it huge.", "a house, a garden, and a gate, make it huge.", "a house, a garden, and a gate", "huge", "13")
add_valid("B19", "B", "voice", "object 14 is mushroom with a tiny door, MAKE IT HUGE?", "mushroom with a tiny door, MAKE IT HUGE", "mushroom with a tiny door", "huge", "14")
add_valid("B20", "B", "typed", "Toy Car,   MaKe   It   HuGe", "Toy Car,   MaKe   It   HuGe", "Toy Car", "huge", "15")

# Bare assignments are the fifth (neutral) intent for both grammars.
add_neutral("N01", "bare_assignment", "typed", "castle", object_key="2")
add_neutral("N02", "bare_assignment", "voice", "object two is a castle", "a castle", "2")
add_neutral("N03", "bare_assignment", "voice", "Object 04 is Big Ben.", "Big Ben", "4")
add_neutral("N04", "bare_assignment", "typed", "a small-scale model", object_key="5")
add_neutral("N05", "bare_assignment", "voice", "object six is a large scale map", "a large scale map", "6")
add_neutral("N06", "bare_assignment", "typed", "a scale model of a bridge", object_key="7")
add_neutral("N07", "bare_assignment", "voice", "object eight is a house with a tiny window", "a house with a tiny window", "8")
add_neutral("N08", "bare_assignment", "typed", "mushroom, bridge, house", object_key="9")
add_neutral("N09", "bare_assignment", "voice", "object number ten is the Make It Right workshop", "the Make It Right workshop", "10")
add_neutral("N10", "bare_assignment", "typed", "  an ordinary toy car.  ", "an ordinary toy car.", "11")

# Semantic uses of candidate words that are not the exact reserved suffix.
add_neutral("S01", "semantic_scale_phrase", "typed", "Big Ben", object_key="1")
add_neutral("S02", "semantic_scale_phrase", "voice", "object two is a miniature painting", "a miniature painting", "2")
add_neutral("S03", "semantic_scale_phrase", "typed", "a large language model", object_key="3")
add_neutral("S04", "semantic_scale_phrase", "voice", "object four is a scale model", "a scale model", "4")
add_neutral("S05", "semantic_scale_phrase", "typed", "a sign that reads scale tiny", object_key="5")
add_neutral("S06", "semantic_scale_phrase", "voice", "object six is a map at large scale", "a map at large scale", "6")
add_neutral("S07", "semantic_make_it_phrase", "typed", "a note saying make it tiny", object_key="7")
add_neutral("S08", "semantic_make_it_phrase", "voice", "object eight is the Make It Big theatre", "the Make It Big theatre", "8")
add_neutral("S09", "semantic_make_it_phrase", "typed", "a director shouting make it huge at a castle", object_key="9")
add_neutral("S10", "semantic_scale_phrase", "voice", "object ten is a small talk stage", "a small talk stage", "10")

# Malformed markers and unsupported punctuation all fail to neutral.
add_neutral("M01", "malformed_marker", "typed", "castle scale tiny", object_key="1")
add_neutral("M02", "malformed_marker", "voice", "object two is castle; scale tiny", "castle; scale tiny", "2")
add_neutral("M03", "malformed_marker", "typed", "castle, scale", object_key="3")
add_neutral("M04", "malformed_marker", "voice", "object four is castle, make tiny", "castle, make tiny", "4")
add_neutral("M05", "malformed_marker", "typed", "castle, scale tiny please", object_key="5")
add_neutral("M06", "malformed_marker", "voice", "object six is castle, please make it huge", "castle, please make it huge", "6")
add_neutral("M07", "malformed_marker", "typed", "castle, scale very small", object_key="7")
add_neutral("M08", "malformed_marker", "voice", "object eight is castle, make it", "castle, make it", "8")

# More than one control-looking suffix is rejected, even if the last is valid.
add_neutral("C01", "multiple_markers", "typed", "castle, scale tiny, scale huge", object_key="1")
add_neutral("C02", "multiple_markers", "voice", "object two is castle, make it small, make it huge", "castle, make it small, make it huge", "2")
add_neutral("C03", "conflicting_markers", "typed", "castle, scale tiny, make it huge", object_key="3")
add_neutral("C04", "conflicting_markers", "voice", "object four is castle, make it tiny, scale huge", "castle, make it tiny, scale huge", "4")
add_neutral("C05", "multiple_markers", "typed", "castle, scale small, scale small", object_key="5")
add_neutral("C06", "conflicting_markers", "voice", "object six is castle, scale huge, make it tiny", "castle, scale huge, make it tiny", "6")

# Unsupported synonyms do not silently acquire scale.
add_neutral("U01", "unsupported_synonym", "typed", "castle, scale teeny", object_key="1")
add_neutral("U02", "unsupported_synonym", "voice", "object two is castle, scale enormous", "castle, scale enormous", "2")
add_neutral("U03", "unsupported_synonym", "typed", "castle, make it little", object_key="3")
add_neutral("U04", "unsupported_synonym", "voice", "object four is castle, make it colossal", "castle, make it colossal", "4")
add_neutral("U05", "unsupported_synonym", "typed", "castle, scale bigger", object_key="5")
add_neutral("U06", "unsupported_synonym", "voice", "object six is castle, make it smaller", "castle, make it smaller", "6")

# These never match the existing object-assignment route and stay atmosphere.
add_neutral("T01", "atmosphere_command", "atmosphere", "make it foggy")
add_neutral("T02", "atmosphere_command", "atmosphere", "make it tiny and misty")
add_neutral("T03", "atmosphere_command", "atmosphere", "scale the rain down")
add_neutral("T04", "atmosphere_command", "atmosphere", "add huge lightning")
add_neutral("T05", "atmosphere_command", "atmosphere", "make the world feel small")
add_neutral("T06", "atmosphere_command", "atmosphere", "object two moves near object three")
add_neutral("T07", "atmosphere_command", "atmosphere", "turn the sky orange")
add_neutral("T08", "atmosphere_command", "atmosphere", "make it a large storm")
add_neutral("T09", "atmosphere_command", "atmosphere", "scale tiny")
add_neutral("T10", "atmosphere_command", "atmosphere", "a castle, scale tiny")


if OUT.exists():
    raise SystemExit(f"refusing to overwrite frozen holdout: {OUT}")

payload = {
    "study": "Tangible Worlds marked single-utterance scale grammar qualification",
    "frozen_on": "2026-08-30",
    "case_count": len(cases),
    "candidate_grammars": ["A", "B"],
    "oracle_note": "Expected records were frozen before candidate parser execution.",
    "cases": cases,
}
OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"frozen {len(cases)} cases at {OUT}")
