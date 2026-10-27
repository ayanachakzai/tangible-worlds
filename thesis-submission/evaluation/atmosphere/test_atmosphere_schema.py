"""
test_atmosphere_schema.py
-------------------------
isolated qwen3-8b test for the approved atmosphere schema.

this file does not write scene_modifiers.json and does not touch serve.py,
converse.py, index.html, or the tracker. it only asks the local lm studio model
to translate language into semantic atmosphere controls, then validates them.

run:
    python test_atmosphere_schema.py

refs:
    qwen3-8b model card:
    https://huggingface.co/Qwen/Qwen3-8B

    lm studio openai-compatible chat completions:
    https://lmstudio.ai/docs/developer/openai-compat/chat-completions

    three.js r170 sky:
    https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js

    three.js r170 directional light:
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html

    three.js r170 renderer tone mapping / exposure:
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/renderers/WebGLRenderer.html

    three.js r170 canvas texture:
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/textures/CanvasTexture.html

    three.js r170 mesh standard material alpha map:
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/materials/MeshStandardMaterial.html

    three.js r170 buffer geometry / dynamic attributes / line segments:
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/BufferGeometry.html
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/BufferAttribute.html
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/objects/LineSegments.html
"""

import json
import re
from copy import deepcopy
from pathlib import Path

import requests


LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-8b"
RESULTS_FILE = Path("atmosphere_schema_test_results.json")


# approved semantic atmosphere schema, 21 aug 2026.
# qwen controls these readable semantic values only. the renderer will later
# translate them into three.js-specific values and protect scene readability.
MODIFIER_SCHEMA = {
    # what it does: places the procedural sky sun above or below the horizon.
    # range: -12 = night below horizon, 90 = sun directly overhead.
    # ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js
    "sky_elevation": 45.0,

    # what it does: sets the vertical angle of the visible key light and shadows.
    # range: 0 = horizon / long shadows, 90 = overhead / short shadows.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    "light_elevation": 45.0,

    # what it does: sets which horizontal direction the key light comes from.
    # range: 0..360 degrees around the tabletop.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    "light_azimuth": 45.0,

    # what it does: semantic brightness of the key light before renderer safeguards.
    # range: 0 = minimal direct light, 1 = strong direct light.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    "light_level": 0.65,

    # what it does: moves key-light colour from cool through neutral to warm.
    # range: -1 = cool, 0 = neutral, 1 = warm.
    # renderer mapping target: THREE.DirectionalLight.color.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    "light_warmth": 0.0,

    # what it does: controls how hazy / scattered the procedural sky feels.
    # range: 0 = clear, 1 = strongly hazy.
    # renderer mapping target: Sky turbidity / mie controls, not a flat sky colour.
    # ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js
    "sky_haze": 0.2,

    # what it does: controls how much visible layered mist occupies the scene.
    # range: 0 = none, 1 = dense mist.
    # renderer mapping target: alpha-map opacity of the approved world-space layers.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/materials/MeshStandardMaterial.html
    "mist_amount": 0.0,

    # what it does: controls whether mist hugs the floor or reaches higher into air.
    # range: 0 = ground-hugging, 1 = taller mist band.
    # renderer mapping target: y positions / spread of the approved world-space layers.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/Object3D.html
    "mist_height": 0.35,

    # what it does: controls how noticeably mist drifts and changes shape.
    # range: 0 = still, 1 = strong drift / morphing.
    # renderer mapping target: alpha-map texture offsets and slow layer rotation.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/textures/Texture.html
    "mist_motion": 0.25,

    # what it does: controls the visible amount of falling world-space rain streaks.
    # range: 0 = dry, 1 = heavy rain.
    # renderer mapping target: dynamic BufferGeometry rendered as LineSegments.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/BufferGeometry.html
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/objects/LineSegments.html
    "rain_amount": 0.0,

    # what it does: controls how frequent / strong irregular lightning flashes are.
    # range: 0 = none, 1 = frequent strong flashes.
    # renderer mapping target: brief DirectionalLight + exposure changes.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/renderers/WebGLRenderer.html
    "lightning_amount": 0.0,

    # what it does: records a short descriptive label for ui/logging only.
    # it must never select a renderer preset or override the numeric controls above.
    "mood": "neutral",
}


FIELD_GUIDE = """
field meanings and allowed ranges:
- sky_elevation: -12..90 degrees. below 0 means the procedural sun is below the horizon.
- light_elevation: 0..90 degrees. low means long raking shadows, high means short overhead shadows.
- light_azimuth: 0..360 degrees around the tabletop.
- light_level: 0..1 overall semantic strength of the key light.
- light_warmth: -1..1. -1 cool, 0 neutral, 1 warm.
- sky_haze: 0..1. 0 clear, 1 strongly hazy.
- mist_amount: 0..1. 0 none, 1 dense visible mist.
- mist_height: 0..1. 0 ground-hugging, 1 reaching higher into the scene.
- mist_motion: 0..1. 0 still, 1 strongly drifting and morphing.
- rain_amount: 0..1. 0 dry, 1 heavy rain.
- lightning_amount: 0..1. 0 none, 1 frequent strong lightning flashes.
- mood: short descriptive text for display/logging only. it never selects a preset.
""".strip()


SYSTEM_PROMPT = f"""You translate natural-language atmosphere requests into semantic controls for a 3D tabletop scene.

Return ONLY one valid JSON object with exactly these keys:
{json.dumps(MODIFIER_SCHEMA, indent=2)}

{FIELD_GUIDE}

rules:
- compose the controls from the meaning of the request. never choose a hidden theme or preset.
- all numeric values must stay inside their stated ranges.
- mood is descriptive only. never use it as a shortcut for setting the other fields.
- you will receive current values. change only what the user request implies and copy every untouched field exactly.
- if the user explicitly says to keep something unchanged, preserve the related fields exactly.
- if the user asks to remove an effect, set that effect amount to 0.
- night normally needs sky_elevation below 0. moonlight can still use a positive light_elevation because the key light is separate from the procedural sky sun.
- dawn, dusk, sunset and golden hour normally use low positive sky_elevation and low positive light_elevation.
- midday normally uses high sky_elevation and high light_elevation.
- mist, rain and lightning are independent controls and can be combined with any time of day.
- do not make a scene dark just because the word spooky or eerie appears. keep light_level usable unless the user explicitly asks for near-darkness.
- return every key every time, even if most values are unchanged.
- no explanation, markdown or backticks.
"""


RANGES = {
    "sky_elevation": (-12.0, 90.0),
    "light_elevation": (0.0, 90.0),
    "light_azimuth": (0.0, 360.0),
    "light_level": (0.0, 1.0),
    "light_warmth": (-1.0, 1.0),
    "sky_haze": (0.0, 1.0),
    "mist_amount": (0.0, 1.0),
    "mist_height": (0.0, 1.0),
    "mist_motion": (0.0, 1.0),
    "rain_amount": (0.0, 1.0),
    "lightning_amount": (0.0, 1.0),
}


TESTS = [
    {
        "name": "warm_hazy_sunset",
        "request": "make it a warm hazy sunset",
        "expect": {
            "sky_elevation": (0, 15),
            "light_elevation": (0, 20),
            "light_warmth": (0.45, 1),
            "sky_haze": (0.4, 1),
            "rain_amount": (0, 0.15),
            "lightning_amount": (0, 0.15),
        },
    },
    {
        "name": "spooky_misty_night",
        "request": "make it a spooky misty night, eerie but keep the scene readable",
        "expect": {
            "sky_elevation": (-12, -0.1),
            "light_elevation": (5, 40),
            "light_level": (0.2, 0.7),
            "light_warmth": (-1, 0.1),
            "mist_amount": (0.4, 1),
        },
    },
    {
        "name": "thunderstorm_at_sunset",
        "request": "a violent thunderstorm at sunset with heavy rain and lightning",
        "expect": {
            "sky_elevation": (0, 15),
            "light_elevation": (0, 25),
            "light_warmth": (0.2, 1),
            "sky_haze": (0.4, 1),
            "rain_amount": (0.7, 1),
            "lightning_amount": (0.5, 1),
        },
    },
    {
        "name": "ground_mist_dawn",
        "request": "thick ground-hugging mist at dawn with only a little movement",
        "expect": {
            "sky_elevation": (0, 15),
            "mist_amount": (0.65, 1),
            "mist_height": (0, 0.35),
            "mist_motion": (0, 0.4),
        },
    },
    {
        "name": "dry_moonlit_night",
        "request": "a clear dry moonlit night, no mist, no rain and no lightning",
        "expect": {
            "sky_elevation": (-12, -0.1),
            "light_elevation": (5, 45),
            "light_warmth": (-1, 0.1),
            "mist_amount": (0, 0.01),
            "rain_amount": (0, 0.01),
            "lightning_amount": (0, 0.01),
        },
    },
    {
        "name": "preserve_lighting_add_mist",
        "request": "make the mist much thicker and more active, but keep the lighting exactly as it is",
        "current": {
            **MODIFIER_SCHEMA,
            "sky_elevation": 7.0,
            "light_elevation": 10.0,
            "light_azimuth": 225.0,
            "light_level": 0.88,
            "light_warmth": 0.82,
            "sky_haze": 0.72,
            "mist_amount": 0.15,
            "mist_motion": 0.15,
        },
        "preserve": [
            "sky_elevation", "light_elevation", "light_azimuth",
            "light_level", "light_warmth", "sky_haze",
            "rain_amount", "lightning_amount",
        ],
        "expect": {
            "mist_amount": (0.5, 1),
            "mist_motion": (0.4, 1),
        },
    },
    {
        "name": "stop_storm_preserve_scene",
        "request": "stop the rain and lightning but keep the mist and lighting exactly the same",
        "current": {
            **MODIFIER_SCHEMA,
            "sky_elevation": -6.0,
            "light_elevation": 18.0,
            "light_azimuth": 228.0,
            "light_level": 0.42,
            "light_warmth": -0.35,
            "sky_haze": 0.7,
            "mist_amount": 0.7,
            "mist_height": 0.6,
            "mist_motion": 0.5,
            "rain_amount": 0.9,
            "lightning_amount": 0.8,
            "mood": "thunderstorm",
        },
        "preserve": [
            "sky_elevation", "light_elevation", "light_azimuth",
            "light_level", "light_warmth", "sky_haze",
            "mist_amount", "mist_height", "mist_motion",
        ],
        "expect": {
            "rain_amount": (0, 0.01),
            "lightning_amount": (0, 0.01),
        },
    },
    {
        "name": "clear_midday",
        "request": "a clear neutral midday scene, dry air, no mist or storm",
        "expect": {
            "sky_elevation": (65, 90),
            "light_elevation": (65, 90),
            "light_level": (0.65, 1),
            "light_warmth": (-0.2, 0.2),
            "sky_haze": (0, 0.3),
            "mist_amount": (0, 0.01),
            "rain_amount": (0, 0.01),
            "lightning_amount": (0, 0.01),
        },
    },
    {
        "name": "cold_still_foggy_sunrise",
        "request": "a cold foggy sunrise with very still air",
        "expect": {
            "sky_elevation": (0, 15),
            "light_elevation": (0, 25),
            "light_warmth": (-1, 0.2),
            "mist_amount": (0.45, 1),
            "mist_motion": (0, 0.25),
        },
    },
    {
        "name": "subtle_eerie_evening",
        "request": "make the evening subtly eerie, not too dark, with a little moving mist",
        "expect": {
            "sky_elevation": (-2, 20),
            "light_level": (0.3, 0.75),
            "mist_amount": (0.15, 0.65),
            "mist_motion": (0.1, 0.65),
        },
    },
]


def strip_think(text):
    # ref: qwen3 supports thinking and non-thinking modes; this keeps the test
    # robust if lm studio still returns a stray reasoning block.
    # ref: https://huggingface.co/Qwen/Qwen3-8B
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "<think>" in text:
        text = text.split("<think>")[0]
    return text.strip()


def ask_qwen(request, current):
    # ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
    prompt = (
        f"Current modifiers: {json.dumps(current)}\n"
        f"User request: {request}\n"
        "Return the complete modifier JSON:"
    )

    response = requests.post(
        LMSTUDIO_URL,
        json={
            "model": LMSTUDIO_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{prompt} /no_think"},
            ],
            "temperature": 0.3,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=60,
    )
    response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"].strip()
    raw = strip_think(raw)
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def validate_schema(result):
    errors = []
    expected_keys = set(MODIFIER_SCHEMA)
    actual_keys = set(result)

    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        if missing:
            errors.append(f"missing keys: {missing}")
        if extra:
            errors.append(f"extra keys: {extra}")

    for key, (low, high) in RANGES.items():
        value = result.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{key} is not numeric: {value!r}")
            continue
        if not low <= value <= high:
            errors.append(f"{key} out of range: {value} not in {low}..{high}")

    if not isinstance(result.get("mood"), str) or not result.get("mood", "").strip():
        errors.append("mood must be a non-empty string")

    return errors


def validate_test(test, current, result):
    errors = validate_schema(result)

    for key, (low, high) in test.get("expect", {}).items():
        value = result.get(key)
        if isinstance(value, (int, float)) and not low <= value <= high:
            errors.append(f"expected {key} in {low}..{high}, got {value}")

    for key in test.get("preserve", []):
        if result.get(key) != current.get(key):
            errors.append(
                f"preservation failed for {key}: "
                f"expected {current.get(key)!r}, got {result.get(key)!r}"
            )

    return errors


def main():
    print("tangible worlds atmosphere schema test")
    print(f"model: {LMSTUDIO_MODEL}")
    print(f"tests: {len(TESTS)}")
    print()

    saved = []
    passed = 0

    for index, test in enumerate(TESTS, start=1):
        current = deepcopy(test.get("current", MODIFIER_SCHEMA))
        print(f"[{index}/{len(TESTS)}] {test['name']}")
        print(f"request: {test['request']}")

        try:
            result = ask_qwen(test["request"], current)
            errors = validate_test(test, current, result)
        except requests.RequestException as exc:
            print(f"FAIL: lm studio request failed: {exc}")
            print()
            saved.append({**test, "status": "request_failed", "error": str(exc)})
            continue
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            print(f"FAIL: invalid model response: {exc}")
            print()
            saved.append({**test, "status": "invalid_response", "error": str(exc)})
            continue

        status = "PASS" if not errors else "FAIL"
        if not errors:
            passed += 1

        print(json.dumps(result, indent=2))
        print(status)
        for error in errors:
            print(f"  - {error}")
        print()

        saved.append({
            "name": test["name"],
            "request": test["request"],
            "current": current,
            "result": result,
            "errors": errors,
            "status": status.lower(),
        })

    report = {
        "model": LMSTUDIO_MODEL,
        "passed": passed,
        "total": len(TESTS),
        "tests": saved,
    }
    RESULTS_FILE.write_text(json.dumps(report, indent=2))

    print(f"result: {passed}/{len(TESTS)} passed")
    print(f"saved: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
