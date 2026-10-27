"""Isolated deterministic explicit-scale parsers and assignment contract builder."""

import re


MODIFIERS = {
    "tiny": ("very_small", 0.35),
    "miniature": ("very_small", 0.35),
    "small": ("small", 0.65),
    "big": ("large", 1.80),
    "large": ("large", 1.80),
    "huge": ("very_large", 3.00),
}
NEUTRAL_INTENT = "neutral"
NEUTRAL_TARGET = 1.00
TOKEN_PATTERN = r"tiny|miniature|small|big|large|huge"

# ref: https://docs.python.org/3/library/re.html
ANYWHERE_RE = re.compile(rf"\b(?P<modifier>{TOKEN_PATTERN})\b", re.IGNORECASE)
LEADING_RE = re.compile(
    rf"^\s*(?:(?P<article>a|an)\s+)?"
    rf"(?P<modifier>{TOKEN_PATTERN})\s+"
    rf"(?P<rest>.+?)\s*[.!?]*\s*$",
    re.IGNORECASE,
)


def _collapse_whitespace(text):
    return " ".join(text.strip().split())


def _neutral(phrase):
    original = phrase.strip()
    return {
        "participant_phrase": original,
        "generation_meaning": _collapse_whitespace(original),
        "explicit_scale_intent": NEUTRAL_INTENT,
        "target_size": NEUTRAL_TARGET,
        "scale_source": "neutral_default",
        "matched_modifier": None,
        "detected": False,
    }


def parse_anywhere(phrase):
    result = _neutral(phrase)
    match = ANYWHERE_RE.search(result["participant_phrase"])
    if not match:
        return result
    modifier = match.group("modifier").lower()
    before = result["participant_phrase"][: match.start()]
    after = result["participant_phrase"][match.end() :]
    generation = _collapse_whitespace((before + " " + after).strip(" .!?"))
    intent, target = MODIFIERS[modifier]
    result.update({
        "generation_meaning": generation,
        "explicit_scale_intent": intent,
        "target_size": target,
        "scale_source": "participant_explicit",
        "matched_modifier": modifier,
        "detected": True,
    })
    return result


def parse_leading(phrase):
    result = _neutral(phrase)
    match = LEADING_RE.match(result["participant_phrase"])
    if not match:
        return result
    modifier = match.group("modifier").lower()
    article = match.group("article")
    rest = _collapse_whitespace(match.group("rest").strip(" .!?"))
    generation = f"{article.lower()} {rest}" if article else rest
    intent, target = MODIFIERS[modifier]
    result.update({
        "generation_meaning": generation,
        "explicit_scale_intent": intent,
        "target_size": target,
        "scale_source": "participant_explicit",
        "matched_modifier": modifier,
        "detected": True,
    })
    return result


def build_assignment(object_key, phrase, parser=parse_leading):
    parsed = parser(phrase)
    return {
        "object_key": str(object_key).strip(),
        "meaning": parsed["participant_phrase"],
        "generation_meaning": parsed["generation_meaning"],
        "explicit_scale_intent": parsed["explicit_scale_intent"],
        "target_size": parsed["target_size"],
        "scale_source": parsed["scale_source"],
    }
