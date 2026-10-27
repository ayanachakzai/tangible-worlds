"""Isolated typed/voice parity, persistence, and movement simulation."""

import json
import re
from pathlib import Path

from explicit_scale_parser import build_assignment


ROOT = Path(__file__).resolve().parent
NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}
VOICE_RE = re.compile(
    r"^object\s+(?:number\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s+is\s+(.+?)\s*[.!?]*$",
    re.IGNORECASE,
)


def parse_voice_assignment(text):
    match = VOICE_RE.match((text or "").strip())
    if not match:
        return None
    spoken = match.group(1).lower()
    object_key = str(int(spoken)) if spoken.isdigit() else NUMBER_WORDS.get(spoken)
    meaning = re.sub(r"[.!?]+$", "", match.group(2)).strip()
    return {"object_key": object_key, "meaning": meaning} if object_key and meaning else None


def main():
    typed_request = {"object_key": "2", "meaning": "a tiny castle"}
    voice_request = parse_voice_assignment("object two is a tiny castle")
    atmosphere_request = parse_voice_assignment("make it foggy")
    typed_contract = build_assignment(typed_request["object_key"], typed_request["meaning"])
    voice_contract = build_assignment(voice_request["object_key"], voice_request["meaning"])

    generation_calls = 0
    assignment_cache = {}

    def assign(contract):
        nonlocal generation_calls
        generation_calls += 1
        assignment_cache[contract["object_key"]] = {**contract, "status": "ready", "mesh_url": "/fixture/a-castle.glb"}

    assign(voice_contract)
    positions = []
    for step in range(20):
        positions.append({"x": round(-0.8 + step * 0.08, 3), "z": round(0.5 - step * 0.03, 3)})
        # Movement reads the cached record but never calls assign/generate.
        assert assignment_cache["2"]["target_size"] == 0.35

    fixture_path = ROOT / "raw" / "assignment_state_fixture.json"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(json.dumps(assignment_cache, indent=2) + "\n")
    reloaded = json.loads(fixture_path.read_text())

    result = {
        "typed_request": typed_request,
        "voice_request": voice_request,
        "atmosphere_routes_to_assignment": atmosphere_request is not None,
        "typed_contract": typed_contract,
        "voice_contract": voice_contract,
        "typed_voice_equal": typed_contract == voice_contract,
        "generation_calls_after_assignment_and_20_moves": generation_calls,
        "movement_positions": positions,
        "target_persisted_after_reload": reloaded["2"]["target_size"] == 0.35,
        "scale_source_persisted_after_reload": reloaded["2"]["scale_source"] == "participant_explicit",
    }
    (ROOT / "assignment_contract_results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
