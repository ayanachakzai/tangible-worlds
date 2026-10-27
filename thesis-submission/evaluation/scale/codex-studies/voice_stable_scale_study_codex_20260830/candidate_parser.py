#!/usr/bin/env python3
"""Deterministic isolated parsers for three voice-stable marker candidates."""

from __future__ import annotations

import re
from typing import Any


TARGETS = {
    "tiny": ("very_small", 0.35), "miniature": ("very_small", 0.35),
    "small": ("small", 0.65), "big": ("large", 1.80),
    "large": ("large", 1.80), "huge": ("very_large", 3.00),
}
NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}
VOICE_RE = re.compile(
    r"^object\s+(?:number\s+)?"
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s+is\s+(.+?)\s*[.!?]*$", re.IGNORECASE,
)
WORDS = "tiny|miniature|small|big|large|huge"
PATTERNS = {
    "A": re.compile(rf"^(?P<generation>.+?)(?:\s*,\s*|\s+)size\s+(?P<modifier>{WORDS})\s*[.!?]*\s*$", re.IGNORECASE),
    "B": re.compile(rf"^(?P<generation>.+?)(?:\s*,\s*|\s+)size\s+is\s+(?P<modifier>{WORDS})\s*[.!?]*\s*$", re.IGNORECASE),
    "C": re.compile(rf"^(?P<generation>.+?)(?:\s*,\s*|\s+)scale\s+(?P<modifier>{WORDS})\s*[.!?]*\s*$", re.IGNORECASE),
}
CONTROL_FRAGMENT_RE = re.compile(
    rf",\s*(?:size(?:\s+is)?|scale|scaled|make\s+it)\s+\S+"
    rf"|(?:^|\s)(?:size(?:\s+is)?|scale|scaled|make\s+it)\s+(?:{WORDS})(?=$|[\s,.!?])",
    re.IGNORECASE,
)


def parse_voice(text: str) -> dict[str, str] | None:
    match = VOICE_RE.fullmatch((text or "").strip())
    if not match:
        return None
    spoken = match.group(1).lower()
    key = str(int(spoken)) if spoken.isdigit() else NUMBER_WORDS[spoken]
    meaning = match.group(2).rstrip(".!?").strip()
    return {"object_key": key, "meaning": meaning} if meaning else None


def parse_marker(meaning: str, candidate: str) -> dict[str, Any]:
    original = (meaning or "").strip()
    neutral = {
        "meaning": original, "generation_meaning": original,
        "explicit_scale_intent": "neutral", "target_size": 1.0,
        "scale_source": "neutral_default", "explicit_detected": False,
    }
    match = PATTERNS[candidate].fullmatch(original)
    if not match:
        return neutral
    generation = match.group("generation").strip()
    if not generation or generation.endswith((";", ":")) or CONTROL_FRAGMENT_RE.search(generation):
        return neutral
    modifier = match.group("modifier").lower()
    intent, target = TARGETS[modifier]
    return {
        "meaning": original, "generation_meaning": generation,
        "explicit_scale_intent": intent, "target_size": target,
        "scale_source": "participant_marked", "explicit_detected": True,
    }


def resolve(text: str, mode: str, candidate: str, typed_key: str | None = None) -> dict[str, Any]:
    if mode == "typed":
        routed = {"object_key": str(typed_key or ""), "meaning": text.strip()}
    elif mode == "voice":
        routed = parse_voice(text)
        if routed is None:
            return {
                "route": "atmosphere", "object_key": None, "meaning": None,
                "generation_meaning": None, "explicit_scale_intent": None,
                "target_size": None, "scale_source": None, "explicit_detected": False,
            }
    else:
        raise ValueError(mode)
    return {"route": "assignment", "object_key": routed["object_key"], **parse_marker(routed["meaning"], candidate)}
