#!/usr/bin/env python3
"""Emit the preregistered voice-only scaled-alias holdout as JSON.

This file defines cases and expected outcomes only.  It intentionally contains
no candidate normalizer implementation.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime


SIZES = {
    "tiny": ("very_small", 0.35),
    "miniature": ("very_small", 0.35),
    "small": ("small", 0.65),
    "big": ("large", 1.80),
    "large": ("large", 1.80),
    "huge": ("very_large", 3.00),
}

NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}

cases: list[dict] = []


def object_key(token: str) -> str:
    bare = token.removeprefix("number ")
    return NUMBER_WORDS.get(bare, str(int(bare))) if bare.isdigit() else NUMBER_WORDS[bare]


def voice_text(token: str, meaning: str, style: int = 0) -> str:
    variants = (
        f"object {token} is {meaning}",
        f"Object {token} is {meaning}.",
        f"OBJECT {token} IS {meaning}!",
        f" object  {token}  is  {meaning} ?",
    )
    return variants[style % len(variants)]


def add_assignment(
    category: str,
    token: str,
    original_meaning: str,
    *,
    style: int = 0,
    intended_alias: bool = False,
    reserved_alias: bool = False,
    sent_meaning: str | None = None,
    generation_meaning: str | None = None,
    scale_word: str | None = None,
) -> None:
    sent = sent_meaning if sent_meaning is not None else original_meaning
    if scale_word is None:
        intent, target, source = "neutral", 1.0, "neutral_default"
        generation = sent if generation_meaning is None else generation_meaning
    else:
        intent, target = SIZES[scale_word]
        source = "participant_marked"
        generation = generation_meaning
        if generation is None:
            raise ValueError("explicit scale case needs generation_meaning")
    cases.append({
        "id": f"V{len(cases) + 1:03d}",
        "category": category,
        "transcript": voice_text(token, original_meaning, style),
        "expected_route": "assignment",
        "expected_object_key": object_key(token),
        "expected_original_meaning": original_meaning,
        "human_intended_alias": intended_alias,
        "reserved_grammar_alias": reserved_alias,
        "expected_sent_meaning": sent,
        "expected_generation_meaning": generation,
        "expected_explicit_scale_intent": intent,
        "expected_target_size": target,
        "expected_scale_source": source,
    })


def add_converse(category: str, transcript: str) -> None:
    cases.append({
        "id": f"V{len(cases) + 1:03d}",
        "category": category,
        "transcript": transcript,
        "expected_route": "converse",
        "expected_object_key": None,
        "expected_original_meaning": None,
        "human_intended_alias": False,
        "reserved_grammar_alias": False,
        "expected_sent_meaning": None,
        "expected_generation_meaning": None,
        "expected_explicit_scale_intent": None,
        "expected_target_size": None,
        "expected_scale_source": None,
    })


# 24 genuine STT substitutions: every supported word, with articles, numeric
# and spoken ids, casing, punctuation, and varied open-vocabulary subjects.
subjects = ["a car", "castle", "the bridge", "a mushroom"]
tokens = ["two", "2", "number two", "four", "4", "ten"]
for size_index, size in enumerate(SIZES):
    for subject_index, subject in enumerate(subjects):
        if size == "miniature" and subject_index == 3:
            subject = "a toy car"
        generation = subject
        original = f"{subject} scaled {size}"
        sent = f"{subject} scale {size}"
        add_assignment(
            "intended_stt_alias",
            tokens[(size_index + subject_index) % len(tokens)],
            original,
            style=size_index + subject_index,
            intended_alias=True,
            reserved_alias=True,
            sent_meaning=sent,
            generation_meaning=generation,
            scale_word=size,
        )

# 12 already-correct voice forms must not be rewritten, but must retain the
# existing server-side marked-scale result.
for index, size in enumerate(SIZES):
    for comma in (False, True):
        subject = ("an intricate VFX portal" if index % 2 else "a car")
        delimiter = ", scale " if comma else " scale "
        meaning = f"{subject}{delimiter}{size}"
        add_assignment(
            "existing_scale_form",
            tokens[(index * 2 + int(comma)) % len(tokens)],
            meaning,
            style=index + int(comma),
            generation_meaning=subject,
            scale_word=size,
        )

# 12 literal semantic endings.  They are human-intent negatives, but the
# reserved voice grammar deliberately consumes them.  This is the decision's
# explicit loss of unrestricted literal voice semantics, not hidden test data.
collisions = [
    ("a VFX asset already scaled tiny", "tiny"),
    ("a source mesh uniformly scaled big", "big"),
    ("a toy car prop scaled miniature", "miniature"),
    ("a background house intentionally scaled large", "large"),
    ("a bridge proxy scaled huge", "huge"),
    ("a foreground mushroom manually scaled small", "small"),
    ("a photogrammetry scan already scaled small", "small"),
    ("a compositing plate uniformly scaled large", "large"),
    ("a practical model carefully scaled tiny", "tiny"),
    ("a castle asset deliberately scaled huge", "huge"),
    ("a vehicle mesh previously scaled big", "big"),
    ("a miniature set prop scaled miniature", "miniature"),
]
for index, (meaning, size) in enumerate(collisions):
    prefix = meaning[: -(len("scaled ") + len(size))].rstrip()
    add_assignment(
        "literal_semantic_collision",
        tokens[index % len(tokens)],
        meaning,
        style=index,
        reserved_alias=True,
        sent_meaning=f"{prefix} scale {size}",
        generation_meaning=prefix,
        scale_word=size,
    )

# 10 non-terminal uses remain literal semantic language.
for index, meaning in enumerate([
    "a VFX asset scaled tiny for the foreground",
    "a source mesh scaled big before export",
    "a toy car scaled miniature with red paint",
    "a bridge scaled huge in the previs file",
    "a house scaled large beside the actor",
    "a mushroom scaled small then duplicated",
    "a tiny scaled model car",
    "a scaled tiny label on a crate",
    "a note saying scaled huge on the prop",
    "a character named Scaled Tiny Returns",
]):
    add_assignment("nonterminal_scaled_language", tokens[index % len(tokens)], meaning, style=index)

# 10 malformed or incomplete endings.
for index, meaning in enumerate([
    "a car scaled", "a car scaled tiny please", "scaled tiny", "a car was scaled to tiny",
    "a car, scaled: tiny", "a car scaled very tiny", "a car scaled tiny twice",
    "a car scaled-tiny", "a car scaled tiny-ish", "a car scaled tiny and",
]):
    add_assignment("malformed_alias", tokens[index % len(tokens)], meaning, style=index)

# 8 unsupported synonyms remain neutral.
for index, synonym in enumerate([
    "enormous", "gigantic", "little", "microscopic", "massive", "medium", "normal", "teeny",
]):
    add_assignment("unsupported_synonym", tokens[index % len(tokens)], f"a car scaled {synonym}", style=index)

# 8 multiple/conflicting control-looking endings remain unchanged and neutral.
for index, meaning in enumerate([
    "a car scale small scaled huge",
    "a car scaled small scaled huge",
    "a car scaled tiny scale huge",
    "a car scale huge scaled tiny",
    "a car, scale small, scaled large",
    "a car scaled miniature scaled big",
    "a car scaled huge scaled small",
    "a car scale tiny and scaled huge",
]):
    add_assignment("multiple_or_conflicting", tokens[index % len(tokens)], meaning, style=index)

# 10 atmosphere/conversation strings must never enter assignment routing.
for transcript in [
    "make it foggy", "make the world huge", "scale the sunlight down",
    "add tiny points of light", "the atmosphere is large scale", "make it sunset",
    "object two should glow", "turn the sky red", "add lightning", "make the fog miniature",
]:
    add_converse("atmosphere_or_nonassignment", transcript)

# 10 accepted assignments with proper nouns and internal size/scale language.
for index, meaning in enumerate([
    "Big Ben", "Small Scale Industries", "a life size statue", "a full size car",
    "a size comparison chart", "a scale model car", "a large scale map",
    "a small-scale city", "a scaled mesh", "a film called Scaled Huge Returns",
]):
    add_assignment("ordinary_assignment", tokens[index % len(tokens)], meaning, style=index)


document = {
    "study_date": "2026-08-30",
    "frozen_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "oracle_note": (
        "Frozen before candidate normalizer implementation. Human-intent labels score semantic "
        "collisions; reserved-grammar labels score the proposed project contract."
    ),
    "case_count": len(cases),
    "category_counts": dict(sorted(Counter(case["category"] for case in cases).items())),
    "cases": cases,
}
print(json.dumps(document, indent=2, ensure_ascii=False))
