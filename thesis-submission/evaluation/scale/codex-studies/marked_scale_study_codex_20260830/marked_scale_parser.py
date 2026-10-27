#!/usr/bin/env python3
"""Isolated deterministic candidates for the marked-scale study.

This module duplicates only the already-live voice assignment grammar and adds
the two frozen suffix candidates. It has no model calls or dependencies.
"""

from __future__ import annotations

import re
from typing import Any


SCALE_WORDS = {
    "tiny": ("very_small", 0.35),
    "miniature": ("very_small", 0.35),
    "small": ("small", 0.65),
    "big": ("large", 1.80),
    "large": ("large", 1.80),
    "huge": ("very_large", 3.00),
}

NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}

VOICE_ASSIGNMENT_RE = re.compile(
    r"^object\s+(?:number\s+)?"
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s+is\s+(.+?)\s*[.!?]*$",
    re.IGNORECASE,
)

_WORDS = "tiny|miniature|small|big|large|huge"
GRAMMAR_PATTERNS = {
    "A": re.compile(
        rf"^(?P<generation>.+?)\s*,\s*scale\s+"
        rf"(?P<modifier>{_WORDS})\s*[.!?]*\s*$",
        re.IGNORECASE,
    ),
    "B": re.compile(
        rf"^(?P<generation>.+?)\s*,\s*make\s+it\s+"
        rf"(?P<modifier>{_WORDS})\s*[.!?]*\s*$",
        re.IGNORECASE,
    ),
}

# A second control-looking fragment before the terminal suffix makes the whole
# phrase ambiguous. Reject it instead of choosing the final modifier.
CONTROL_FRAGMENT_RE = re.compile(
    r",\s*(?:scale|make\s+it)\s+\S+",
    re.IGNORECASE,
)


def parse_voice_assignment(text: str) -> dict[str, str] | None:
    """Mirror the working-tree browser's object assignment route."""
    match = VOICE_ASSIGNMENT_RE.fullmatch((text or "").strip())
    if not match:
        return None
    spoken_key = match.group(1).lower()
    object_key = str(int(spoken_key)) if spoken_key.isdigit() else NUMBER_WORDS[spoken_key]
    meaning = match.group(2).rstrip(".!?").strip()
    if not object_key or not meaning:
        return None
    return {"object_key": object_key, "meaning": meaning}


def parse_marked_meaning(meaning: str, grammar: str) -> dict[str, Any]:
    """Parse exactly one terminal candidate marker or return neutral."""
    original = (meaning or "").strip()
    neutral = {
        "meaning": original,
        "generation_meaning": original,
        "explicit_scale_intent": "neutral",
        "target_size": 1.0,
        "scale_source": "neutral_default",
        "explicit_detected": False,
    }
    pattern = GRAMMAR_PATTERNS[grammar]
    match = pattern.fullmatch(original)
    if not match:
        return neutral

    generation = match.group("generation").strip()
    modifier = match.group("modifier").lower()
    if not generation or CONTROL_FRAGMENT_RE.search(generation):
        return neutral

    intent, target = SCALE_WORDS[modifier]
    return {
        "meaning": original,
        "generation_meaning": generation,
        "explicit_scale_intent": intent,
        "target_size": target,
        "scale_source": "participant_marked",
        "explicit_detected": True,
    }


def resolve_input(
    text: str,
    input_mode: str,
    grammar: str,
    typed_object_key: str | None = None,
) -> dict[str, Any]:
    """Resolve typed or voice input at the existing assignment boundary."""
    if input_mode == "typed":
        assignment = {
            "object_key": str(typed_object_key or "").strip(),
            "meaning": (text or "").strip(),
        }
    elif input_mode == "voice":
        assignment = parse_voice_assignment(text)
        if assignment is None:
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
    else:
        raise ValueError(f"unsupported input mode: {input_mode}")

    parsed = parse_marked_meaning(assignment["meaning"], grammar)
    return {"route": "assignment", "object_key": assignment["object_key"], **parsed}
