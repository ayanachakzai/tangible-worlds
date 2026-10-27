"""
test_atmosphere_visual_deep_playwright.py
------------------------------------------
one-file deep visual qualification test for tangible worlds atmosphere controls.

this runs the full approved deep suite and saves visual evidence for every
valid qwen result. it does not edit serve.py, converse.py, index.html,
scene_modifiers.json, or the tracker.

106 qwen calls total:
- 68 strict diverse tests
- 8 ambiguous review-only tests
- 15 stateful conversational refinement steps
- 15 repeatability runs

for each experiment it saves named prompt/current/json/png files. screenshots
are named after the actual experiment, never generic preview.png.

run:
    python test_atmosphere_visual_deep_playwright.py

refs:
    qwen3-8b:
    https://huggingface.co/Qwen/Qwen3-8B

    lm studio openai-compatible chat completions:
    https://lmstudio.ai/docs/developer/openai-compat/chat-completions

    playwright python:
    https://playwright.dev/python/docs/intro

    playwright screenshots:
    https://playwright.dev/python/docs/screenshots

    three.js r170 sky:
    https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js

    three.js r170 directional light:
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html

    three.js r170 renderer:
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/renderers/WebGLRenderer.html

    three.js r170 mist/rain mechanisms:
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/materials/MeshStandardMaterial.html
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/textures/Texture.html
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/BufferGeometry.html
    https://github.com/mrdoob/three.js/blob/r170/docs/api/en/objects/LineSegments.html
"""

import argparse
import json
import re
import shutil
import threading
import time
from copy import deepcopy
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

import requests
from playwright.sync_api import sync_playwright


LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-8b"
PLAYWRIGHT_BROWSER = "chromium"


# approved semantic atmosphere schema, 21 aug 2026.
# every field below states what it does, its range, and its renderer source.
MODIFIER_SCHEMA = {
    # what it does: places the procedural sky sun above or below the horizon.
    # range: -12 = night below horizon, 90 = sun directly overhead.
    # renderer target: three.js Sky sunPosition.
    # ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js
    "sky_elevation": 45.0,

    # what it does: sets the vertical angle of the visible key light and shadows.
    # range: 0 = horizon / long shadows, 90 = overhead / short shadows.
    # renderer target: THREE.DirectionalLight position.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    "light_elevation": 45.0,

    # what it does: sets which horizontal direction the key light comes from.
    # range: 0..360 degrees around the tabletop.
    # renderer target: THREE.DirectionalLight position around the table.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    "light_azimuth": 45.0,

    # what it does: semantic brightness of the key light before renderer safeguards.
    # range: 0 = minimal direct light, 1 = strong direct light.
    # renderer target: THREE.DirectionalLight intensity.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    "light_level": 0.65,

    # what it does: moves key-light colour from cool through neutral to warm.
    # range: -1 = cool, 0 = neutral, 1 = warm.
    # renderer target: THREE.DirectionalLight.color.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    "light_warmth": 0.0,

    # what it does: controls how hazy / scattered the procedural sky feels.
    # range: 0 = clear, 1 = strongly hazy.
    # renderer target: Sky turbidity / rayleigh / mie controls.
    # ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js
    "sky_haze": 0.2,

    # what it does: controls how much visible layered mist occupies the scene.
    # range: 0 = none, 1 = dense mist.
    # renderer target: alpha opacity of the approved world-space mist layers.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/materials/MeshStandardMaterial.html
    "mist_amount": 0.0,

    # what it does: controls whether mist hugs the floor or reaches higher into air.
    # range: 0 = ground-hugging, 1 = taller mist band.
    # renderer target: vertical spread of the approved world-space mist layers.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/Object3D.html
    "mist_height": 0.35,

    # what it does: controls how noticeably mist drifts and changes shape.
    # range: 0 = still, 1 = strong drift / morphing.
    # renderer target: texture offsets plus slow layer rotation and wobble.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/textures/Texture.html
    "mist_motion": 0.25,

    # what it does: controls the visible amount of falling world-space rain streaks.
    # range: 0 = dry, 1 = heavy rain.
    # renderer target: visible dynamic LineSegments count / opacity.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/core/BufferGeometry.html
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/objects/LineSegments.html
    "rain_amount": 0.0,

    # what it does: controls how frequent / strong irregular lightning flashes are.
    # range: 0 = none, 1 = frequent strong lightning flashes.
    # renderer target: brief DirectionalLight and tone-mapping exposure boosts.
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html
    # ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/renderers/WebGLRenderer.html
    "lightning_amount": 0.0,

    # what it does: records a short descriptive label for ui/logging only.
    # range: free text.
    # renderer target: none. mood never selects a renderer preset.
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

interpretation rules:
- treat the current values as the existing scene state, not as values that should be protected by default.
- first infer every field whose meaning is directly stated OR clearly implied by the user's request. change those fields.
- preserve only fields that are genuinely unrelated to the request, or fields the user explicitly asks to keep unchanged.
- time-of-day language always implies sky_elevation and usually light_elevation. do not leave those values unchanged when the user says night, dawn, sunrise, morning, midday, afternoon, evening, dusk, sunset or golden hour.
- descriptive words map compositionally to the relevant dials. examples: warm -> light_warmth, hazy -> sky_haze, misty/foggy -> mist controls, rainy -> rain_amount, lightning/thunderstorm -> lightning_amount plus rain when rain is stated or strongly implied.
- compose controls from the whole phrase. never choose a hidden renderer theme or preset.

physical calibration anchors:
- deep or moonlit night: sky_elevation around -6. a separate moon/key light can remain around 15..30 degrees.
- dawn / sunrise / sunset / dusk: sky_elevation usually around 4..10 and key-light elevation around 6..15.
- evening / just after sunset: sky_elevation around -2..12 depending on wording.
- clear midday: sky_elevation and light_elevation usually around 70..85.
- golden/warm sunset light is strongly warm. explicitly hazy air should raise sky_haze.
- clear/dry air should lower sky_haze and set mist_amount to 0 when mist/fog is explicitly absent.
- ground-hugging mist means low mist_height. still air means low mist_motion.
- spooky/eerie does not select a preset. only combine the physical cues that the wording supports, and keep light_level readable unless near-darkness is explicitly requested.

rules:
- all numeric values must stay inside their stated ranges.
- mood is descriptive only. never use it as a shortcut for setting the other fields.
- if the user explicitly says to keep something unchanged, preserve the related fields exactly.
- if the user asks to remove an effect, set that effect amount to 0.
- mist, rain and lightning are independent controls and can be combined with any time of day.
- return every key every time, even if most values are unchanged.
- no explanation, markdown or backticks.

calibration examples. these are examples of continuous semantic mapping, not renderer presets:

example 1 current values:
{{"sky_elevation":45.0,"light_elevation":45.0,"light_azimuth":45.0,"light_level":0.65,"light_warmth":0.0,"sky_haze":0.2,"mist_amount":0.0,"mist_height":0.35,"mist_motion":0.25,"rain_amount":0.0,"lightning_amount":0.0,"mood":"neutral"}}
example 1 request: make it a warm hazy sunset
example 1 answer:
{{"sky_elevation":7.0,"light_elevation":10.0,"light_azimuth":45.0,"light_level":0.85,"light_warmth":0.85,"sky_haze":0.7,"mist_amount":0.0,"mist_height":0.35,"mist_motion":0.25,"rain_amount":0.0,"lightning_amount":0.0,"mood":"warm hazy sunset"}}

example 2 current values:
{{"sky_elevation":45.0,"light_elevation":45.0,"light_azimuth":45.0,"light_level":0.65,"light_warmth":0.0,"sky_haze":0.2,"mist_amount":0.0,"mist_height":0.35,"mist_motion":0.25,"rain_amount":0.0,"lightning_amount":0.0,"mood":"neutral"}}
example 2 request: a clear dry moonlit night, no mist, no rain and no lightning
example 2 answer:
{{"sky_elevation":-6.0,"light_elevation":22.0,"light_azimuth":45.0,"light_level":0.42,"light_warmth":-0.35,"sky_haze":0.1,"mist_amount":0.0,"mist_height":0.35,"mist_motion":0.25,"rain_amount":0.0,"lightning_amount":0.0,"mood":"clear moonlit night"}}

example 3 current values:
{{"sky_elevation":7.0,"light_elevation":10.0,"light_azimuth":225.0,"light_level":0.88,"light_warmth":0.82,"sky_haze":0.72,"mist_amount":0.15,"mist_height":0.35,"mist_motion":0.15,"rain_amount":0.0,"lightning_amount":0.0,"mood":"neutral"}}
example 3 request: make the mist much thicker and more active, but keep the lighting exactly as it is
example 3 answer:
{{"sky_elevation":7.0,"light_elevation":10.0,"light_azimuth":225.0,"light_level":0.88,"light_warmth":0.82,"sky_haze":0.72,"mist_amount":0.82,"mist_height":0.35,"mist_motion":0.72,"rain_amount":0.0,"lightning_amount":0.0,"mood":"neutral"}}
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


# diverse visual samples. most begin from neutral. a few deliberately provide
# existing states so preservation / conversational refinement is also visible.
LIGHTING_FIELDS = ['sky_elevation', 'light_elevation', 'light_azimuth', 'light_level', 'light_warmth', 'sky_haze']
WEATHER_FIELDS = ['mist_amount', 'mist_height', 'mist_motion', 'rain_amount', 'lightning_amount']
ALL_FIELDS = ['sky_elevation',
 'light_elevation',
 'light_azimuth',
 'light_level',
 'light_warmth',
 'sky_haze',
 'mist_amount',
 'mist_height',
 'mist_motion',
 'rain_amount',
 'lightning_amount',
 'mood']
STRICT_TESTS = [{'category': 'time',
  'name': 'deep_midnight',
  'request': 'deep midnight, clear and dry',
  'expect': {'sky_elevation': (-12, -1),
             'light_level': (0.15, 0.65),
             'mist_amount': (0, 0.05),
             'rain_amount': (0, 0.05),
             'lightning_amount': (0, 0.05)}},
 {'category': 'time',
  'name': 'moonlit_night',
  'request': 'a clear moonlit night',
  'expect': {'sky_elevation': (-12, -0.1), 'light_elevation': (5, 45), 'light_warmth': (-1, 0.15)}},
 {'category': 'time',
  'name': 'predawn',
  'request': 'the blue hour just before dawn',
  'expect': {'sky_elevation': (-8, 4), 'light_elevation': (3, 30), 'light_warmth': (-1, 0.2)}},
 {'category': 'time', 'name': 'dawn', 'request': 'soft dawn light', 'expect': {'sky_elevation': (0, 15), 'light_elevation': (0, 25)}},
 {'category': 'time',
  'name': 'sunrise',
  'request': 'warm sunrise',
  'expect': {'sky_elevation': (0, 15), 'light_elevation': (0, 25), 'light_warmth': (0.35, 1)}},
 {'category': 'time',
  'name': 'early_morning',
  'request': 'clear early morning',
  'expect': {'sky_elevation': (8, 40), 'light_elevation': (8, 45)}},
 {'category': 'time',
  'name': 'noon',
  'request': 'bright clear noon',
  'expect': {'sky_elevation': (65, 90), 'light_elevation': (65, 90), 'light_level': (0.65, 1)}},
 {'category': 'time',
  'name': 'afternoon',
  'request': 'bright afternoon sunlight',
  'expect': {'sky_elevation': (35, 80), 'light_elevation': (35, 80)}},
 {'category': 'time',
  'name': 'golden_hour',
  'request': 'golden hour, warm and clear',
  'expect': {'sky_elevation': (3, 15), 'light_elevation': (3, 20), 'light_warmth': (0.5, 1), 'sky_haze': (0, 0.55)}},
 {'category': 'time',
  'name': 'sunset',
  'request': 'a warm sunset',
  'expect': {'sky_elevation': (0, 15), 'light_elevation': (0, 25), 'light_warmth': (0.4, 1)}},
 {'category': 'time',
  'name': 'dusk',
  'request': 'cool dusk after the sun has gone down',
  'expect': {'sky_elevation': (-6, 5), 'light_elevation': (3, 30), 'light_warmth': (-1, 0.15)}},
 {'category': 'time',
  'name': 'evening',
  'request': 'a calm evening just before night',
  'expect': {'sky_elevation': (-2, 20), 'light_elevation': (3, 35)}},
 {'category': 'lighting',
  'name': 'cold_light',
  'request': 'make the light distinctly colder, keep everything else exactly the same',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.45,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'light_warmth': (-1, -0.15)},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'lighting',
  'name': 'warm_light',
  'request': 'make the light much warmer, keep everything else exactly the same',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': -0.4,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'light_warmth': (0.35, 1)},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'lighting',
  'name': 'long_shadows',
  'request': 'give me much longer raking shadows, keep the time of day and all weather unchanged',
  'current': {'sky_elevation': 45,
              'light_elevation': 65,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.3,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'light_elevation': (0, 25)},
  'preserve': ['sky_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount']},
 {'category': 'lighting',
  'name': 'overhead_light',
  'request': 'move the key light high overhead, keep everything else unchanged',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 12,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'light_elevation': (70, 90)},
  'preserve': ['sky_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'lighting',
  'name': 'dim_readable',
  'request': 'make the lighting dimmer but keep the scene readable, change nothing else',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.9,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'light_level': (0.2, 0.65)},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'lighting',
  'name': 'brighter',
  'request': 'make the key light clearly brighter, change nothing else',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.35,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'light_level': (0.6, 1)},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'lighting',
  'name': 'opposite_side',
  'request': 'move the key light to the opposite side of the table, change nothing else',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 30,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'light_azimuth': (180, 240)},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'lighting',
  'name': 'neutral_overcast',
  'request': 'neutral overcast daylight, no rain',
  'expect': {'sky_elevation': (25, 75),
             'light_warmth': (-0.25, 0.25),
             'sky_haze': (0.45, 1),
             'rain_amount': (0, 0.05),
             'lightning_amount': (0, 0.05)}},
 {'category': 'mist',
  'name': 'thin_ground_mist',
  'request': 'a thin layer of ground-hugging mist',
  'expect': {'mist_amount': (0.1, 0.5), 'mist_height': (0, 0.3)}},
 {'category': 'mist',
  'name': 'thick_high_mist',
  'request': 'thick mist reaching high into the scene',
  'expect': {'mist_amount': (0.65, 1), 'mist_height': (0.6, 1)}},
 {'category': 'mist',
  'name': 'still_fog',
  'request': 'dense fog with completely still air',
  'expect': {'mist_amount': (0.55, 1), 'mist_motion': (0, 0.12)}},
 {'category': 'mist',
  'name': 'fast_drifting_mist',
  'request': 'mist drifting and morphing strongly in the wind',
  'expect': {'mist_amount': (0.25, 1), 'mist_motion': (0.65, 1)}},
 {'category': 'mist',
  'name': 'remove_mist',
  'request': 'remove all mist and fog, keep everything else exactly the same',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.8,
              'mist_height': 0.75,
              'mist_motion': 0.8,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'exact': {'mist_amount': 0.0},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'mist',
  'name': 'raise_mist_only',
  'request': 'make the existing mist reach much higher, keep its amount and movement exactly the same and change nothing else',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.55,
              'mist_height': 0.18,
              'mist_motion': 0.42,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'mist_height': (0.55, 1)},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'mist',
  'name': 'lower_mist_only',
  'request': 'pull the existing mist down close to the ground, keep its density and movement exactly the same',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.65,
              'mist_height': 0.8,
              'mist_motion': 0.35,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'mist_height': (0, 0.3)},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'mist',
  'name': 'less_and_slower',
  'request': 'make the mist thinner and slower, keep everything else unchanged',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.85,
              'mist_height': 0.35,
              'mist_motion': 0.8,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'less_than_current': ['mist_amount', 'mist_motion'],
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_height',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'weather',
  'name': 'light_drizzle',
  'request': 'light drizzle, no lightning',
  'expect': {'rain_amount': (0.1, 0.45), 'lightning_amount': (0, 0.05)}},
 {'category': 'weather',
  'name': 'heavy_rain_no_lightning',
  'request': 'heavy rain but absolutely no lightning',
  'expect': {'rain_amount': (0.7, 1), 'lightning_amount': (0, 0.05)}},
 {'category': 'weather',
  'name': 'violent_thunderstorm',
  'request': 'a violent thunderstorm with heavy rain and frequent lightning',
  'expect': {'rain_amount': (0.7, 1), 'lightning_amount': (0.65, 1), 'sky_haze': (0.25, 1)}},
 {'category': 'weather',
  'name': 'dry_lightning',
  'request': 'dry lightning in clear air, no rain',
  'expect': {'rain_amount': (0, 0.05), 'lightning_amount': (0.45, 1)}},
 {'category': 'weather',
  'name': 'stop_rain_keep_lightning',
  'request': 'stop the rain completely but keep the lightning exactly as it is and change nothing else',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.9,
              'lightning_amount': 0.7,
              'mood': 'neutral'},
  'exact': {'rain_amount': 0.0, 'lightning_amount': 0.7},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'lightning_amount',
               'mood']},
 {'category': 'weather',
  'name': 'stop_lightning_keep_rain',
  'request': 'stop all lightning but keep the rain exactly as it is and change nothing else',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.75,
              'lightning_amount': 0.8,
              'mood': 'neutral'},
  'exact': {'rain_amount': 0.75, 'lightning_amount': 0.0},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'mood']},
 {'category': 'weather',
  'name': 'storm_clearing',
  'request': 'the storm is clearing, make the rain and lightning much weaker but do not change the time of day',
  'current': {'sky_elevation': -4,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.95,
              'lightning_amount': 0.9,
              'mood': 'neutral'},
  'less_than_current': ['rain_amount', 'lightning_amount'],
  'preserve': ['sky_elevation']},
 {'category': 'composition',
  'name': 'warm_rainy_sunset',
  'request': 'warm rainy sunset, no lightning',
  'expect': {'sky_elevation': (0, 15),
             'light_elevation': (0, 25),
             'light_warmth': (0.35, 1),
             'rain_amount': (0.2, 1),
             'lightning_amount': (0, 0.05)}},
 {'category': 'composition',
  'name': 'foggy_moonlit_night',
  'request': 'a foggy moonlit night with slow-moving mist',
  'expect': {'sky_elevation': (-12, -0.1), 'light_elevation': (5, 45), 'mist_amount': (0.45, 1), 'mist_motion': (0, 0.45)}},
 {'category': 'composition',
  'name': 'clear_cold_dawn',
  'request': 'cold clear dawn with no mist or rain',
  'expect': {'sky_elevation': (0, 15),
             'light_warmth': (-1, 0.1),
             'sky_haze': (0, 0.4),
             'mist_amount': (0, 0.05),
             'rain_amount': (0, 0.05)}},
 {'category': 'composition',
  'name': 'eerie_dry_evening',
  'request': 'a subtly eerie dry evening, no mist, no rain, no lightning, keep it readable',
  'expect': {'sky_elevation': (-2, 20),
             'light_level': (0.2, 0.75),
             'mist_amount': (0, 0.05),
             'rain_amount': (0, 0.05),
             'lightning_amount': (0, 0.05)}},
 {'category': 'composition',
  'name': 'bright_hazy_midday',
  'request': 'bright hazy midday',
  'expect': {'sky_elevation': (65, 90), 'light_elevation': (65, 90), 'light_level': (0.65, 1), 'sky_haze': (0.4, 1)}},
 {'category': 'composition',
  'name': 'warm_sunrise_ground_fog',
  'request': 'warm sunrise through thick ground fog with very little movement',
  'expect': {'sky_elevation': (0, 15),
             'light_warmth': (0.35, 1),
             'mist_amount': (0.55, 1),
             'mist_height': (0, 0.35),
             'mist_motion': (0, 0.3)}},
 {'category': 'composition',
  'name': 'night_thunderstorm',
  'request': 'a dark but readable night thunderstorm with heavy rain and lightning',
  'expect': {'sky_elevation': (-12, -0.1), 'light_level': (0.15, 0.7), 'rain_amount': (0.65, 1), 'lightning_amount': (0.5, 1)}},
 {'category': 'preservation',
  'name': 'add_mist_preserve_lighting',
  'request': 'add thick active mist but keep all lighting exactly as it is',
  'current': {'sky_elevation': 7,
              'light_elevation': 10,
              'light_azimuth': 225,
              'light_level': 0.82,
              'light_warmth': 0.78,
              'sky_haze': 0.62,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'mist_amount': (0.6, 1), 'mist_motion': (0.5, 1)},
  'preserve': ['sky_elevation', 'light_elevation', 'light_azimuth', 'light_level', 'light_warmth', 'sky_haze']},
 {'category': 'preservation',
  'name': 'warmth_only',
  'request': 'only make the light warmer, change absolutely nothing else',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': -0.25,
              'sky_haze': 0.2,
              'mist_amount': 0.45,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.3,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'light_warmth': (0.15, 1)},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'preservation',
  'name': 'azimuth_only',
  'request': 'only change where the light comes from, rotate it to about 250 degrees',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 40,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.4,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'light_azimuth': (235, 265)},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'preservation',
  'name': 'stop_storm_preserve_scene',
  'request': 'stop the rain and lightning but keep the mist and all lighting exactly the same',
  'current': {'sky_elevation': -6,
              'light_elevation': 18,
              'light_azimuth': 228,
              'light_level': 0.42,
              'light_warmth': -0.35,
              'sky_haze': 0.7,
              'mist_amount': 0.7,
              'mist_height': 0.6,
              'mist_motion': 0.5,
              'rain_amount': 0.9,
              'lightning_amount': 0.8,
              'mood': 'neutral'},
  'exact': {'rain_amount': 0.0, 'lightning_amount': 0.0},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion']},
 {'category': 'preservation',
  'name': 'clear_mist_only',
  'request': 'remove the mist only, keep the rain, lightning and lighting exactly unchanged',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.55,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.8,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.65,
              'lightning_amount': 0.5,
              'mood': 'neutral'},
  'exact': {'mist_amount': 0.0, 'rain_amount': 0.65, 'lightning_amount': 0.5},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'rain_amount',
               'lightning_amount']},
 {'category': 'preservation',
  'name': 'heavier_rain_same_lightning',
  'request': 'make the rain heavier but keep the lightning exactly the same and change nothing else',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.25,
              'lightning_amount': 0.62,
              'mood': 'neutral'},
  'greater_than_current': ['rain_amount'],
  'exact': {'lightning_amount': 0.62},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'lightning_amount',
               'mood']},
 {'category': 'preservation',
  'name': 'make_night_keep_weather',
  'request': 'make it night but keep all mist, rain and lightning exactly as they are',
  'current': {'sky_elevation': 45.0,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.5,
              'mist_height': 0.4,
              'mist_motion': 0.6,
              'rain_amount': 0.45,
              'lightning_amount': 0.2,
              'mood': 'neutral'},
  'expect': {'sky_elevation': (-12, -0.1)},
  'preserve': ['mist_amount', 'mist_height', 'mist_motion', 'rain_amount', 'lightning_amount']},
 {'category': 'preservation',
  'name': 'leave_exactly',
  'request': 'leave the atmosphere exactly as it is, change nothing',
  'current': {'sky_elevation': 8,
              'light_elevation': 12,
              'light_azimuth': 210,
              'light_level': 0.72,
              'light_warmth': 0.6,
              'sky_haze': 0.45,
              'mist_amount': 0.4,
              'mist_height': 0.25,
              'mist_motion': 0.3,
              'rain_amount': 0.2,
              'lightning_amount': 0.1,
              'mood': 'warm rainy dusk'},
  'preserve': ['sky_elevation',
               'light_elevation',
               'light_azimuth',
               'light_level',
               'light_warmth',
               'sky_haze',
               'mist_amount',
               'mist_height',
               'mist_motion',
               'rain_amount',
               'lightning_amount',
               'mood']},
 {'category': 'preservation',
  'name': 'non_atmosphere_mountain',
  'request': 'make the mountain taller',
  'current': {'sky_elevation': 8,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.4,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.2,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'preserve_numeric': ['sky_elevation',
                       'light_elevation',
                       'light_azimuth',
                       'light_level',
                       'light_warmth',
                       'sky_haze',
                       'mist_amount',
                       'mist_height',
                       'mist_motion',
                       'rain_amount',
                       'lightning_amount']},
 {'category': 'preservation',
  'name': 'non_atmosphere_object_colour',
  'request': 'turn the car red',
  'current': {'sky_elevation': -6,
              'light_elevation': 45.0,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0.0,
              'sky_haze': 0.2,
              'mist_amount': 0.5,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.4,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'preserve_numeric': ['sky_elevation',
                       'light_elevation',
                       'light_azimuth',
                       'light_level',
                       'light_warmth',
                       'sky_haze',
                       'mist_amount',
                       'mist_height',
                       'mist_motion',
                       'rain_amount',
                       'lightning_amount']},
 {'category': 'conflict',
  'name': 'spooky_no_mist',
  'request': 'make it spooky at night but absolutely no mist, rain or lightning',
  'expect': {'sky_elevation': (-12, -0.1),
             'mist_amount': (0, 0.05),
             'rain_amount': (0, 0.05),
             'lightning_amount': (0, 0.05),
             'light_level': (0.15, 0.75)}},
 {'category': 'conflict',
  'name': 'stormy_no_precipitation',
  'request': 'stormy dark clouds, but no rain and no lightning',
  'expect': {'sky_haze': (0.35, 1), 'rain_amount': (0, 0.05), 'lightning_amount': (0, 0.05)}},
 {'category': 'conflict',
  'name': 'cold_sunset',
  'request': 'sunset, but make the light distinctly cold rather than warm',
  'expect': {'sky_elevation': (0, 15), 'light_elevation': (0, 25), 'light_warmth': (-1, -0.15)}},
 {'category': 'conflict',
  'name': 'warm_night',
  'request': 'nighttime, but with distinctly warm key lighting',
  'expect': {'sky_elevation': (-12, -0.1), 'light_warmth': (0.25, 1)}},
 {'category': 'conflict',
  'name': 'dark_midday',
  'request': 'midday, but dim and eerie while still readable',
  'expect': {'sky_elevation': (65, 90), 'light_elevation': (65, 90), 'light_level': (0.15, 0.65)}},
 {'category': 'conflict',
  'name': 'storm_keep_lighting',
  'request': 'make it a heavy thunderstorm but keep every lighting value exactly unchanged',
  'current': {'sky_elevation': 8,
              'light_elevation': 12,
              'light_azimuth': 220,
              'light_level': 0.8,
              'light_warmth': 0.7,
              'sky_haze': 0.55,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'rain_amount': (0.65, 1), 'lightning_amount': (0.5, 1)},
  'preserve': ['sky_elevation', 'light_elevation', 'light_azimuth', 'light_level', 'light_warmth', 'sky_haze']},
 {'category': 'conflict',
  'name': 'sunset_keep_sky',
  'request': 'make it feel like sunset but keep the current sky elevation exactly unchanged',
  'current': {'sky_elevation': 45,
              'light_elevation': 45,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': 0,
              'sky_haze': 0.2,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'exact': {'sky_elevation': 45},
  'expect': {'light_elevation': (0, 25), 'light_warmth': (0.3, 1)}},
 {'category': 'conflict',
  'name': 'neutral_midday_reset',
  'request': 'remove the weather effects and return to a clear neutral midday atmosphere',
  'current': {'sky_elevation': -6,
              'light_elevation': 18,
              'light_azimuth': 45.0,
              'light_level': 0.65,
              'light_warmth': -0.4,
              'sky_haze': 0.8,
              'mist_amount': 0.8,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.9,
              'lightning_amount': 0.8,
              'mood': 'neutral'},
  'expect': {'sky_elevation': (65, 90),
             'light_elevation': (65, 90),
             'light_warmth': (-0.25, 0.25),
             'sky_haze': (0, 0.35),
             'mist_amount': (0, 0.05),
             'rain_amount': (0, 0.05),
             'lightning_amount': (0, 0.05)}},
 {'category': 'vocabulary',
  'name': 'twilight',
  'request': 'twilight with clear air',
  'expect': {'sky_elevation': (-5, 12), 'sky_haze': (0, 0.4)}},
 {'category': 'vocabulary',
  'name': 'pea_soup_fog',
  'request': 'pea-soup fog, almost no movement',
  'expect': {'mist_amount': (0.7, 1), 'mist_motion': (0, 0.2)}},
 {'category': 'vocabulary', 'name': 'drizzle_word', 'request': 'a gentle drizzle', 'expect': {'rain_amount': (0.1, 0.5)}},
 {'category': 'vocabulary', 'name': 'downpour_word', 'request': 'a heavy downpour', 'expect': {'rain_amount': (0.7, 1)}},
 {'category': 'vocabulary',
  'name': 'distant_lightning',
  'request': 'occasional lightning flickering in the distance, no rain',
  'expect': {'lightning_amount': (0.15, 0.65), 'rain_amount': (0, 0.05)}},
 {'category': 'vocabulary',
  'name': 'crisp_winter_morning',
  'request': 'a crisp clear cold winter morning',
  'expect': {'sky_elevation': (8, 45), 'light_warmth': (-1, 0.15), 'sky_haze': (0, 0.35)}},
 {'category': 'vocabulary',
  'name': 'foggy_af',
  'request': 'make it foggy af but keep the lighting the same',
  'current': {'sky_elevation': 7,
              'light_elevation': 10,
              'light_azimuth': 45.0,
              'light_level': 0.8,
              'light_warmth': 0.7,
              'sky_haze': 0.4,
              'mist_amount': 0.0,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'mist_amount': (0.55, 1)},
  'preserve': ['sky_elevation', 'light_elevation', 'light_azimuth', 'light_level', 'light_warmth', 'sky_haze']},
 {'category': 'vocabulary',
  'name': 'sunset_vibes_no_storm',
  'request': 'sunset vibes, warm and hazy, but no rain or lightning',
  'expect': {'sky_elevation': (0, 15),
             'light_warmth': (0.4, 1),
             'sky_haze': (0.4, 1),
             'rain_amount': (0, 0.05),
             'lightning_amount': (0, 0.05)}}]
REVIEW_CASES = [{'name': 'cinematic', 'request': 'make it more cinematic'},
 {'name': 'ominous', 'request': 'make the atmosphere ominous'},
 {'name': 'dreamlike', 'request': 'make it dreamlike and quiet'},
 {'name': 'romantic', 'request': 'make the evening romantic'},
 {'name': 'murky', 'request': 'make the air murky'},
 {'name': 'alien_green', 'request': 'an eerie green alien night'},
 {'name': 'geographic', 'request': 'a cold clear evening in the mountains around Quetta'},
 {'name': 'minimal_change', 'request': 'just make it a tiny bit moodier'}]
SEQUENCES = [{'name': 'sunset_to_misty_night',
  'start': {'sky_elevation': 45.0,
            'light_elevation': 45.0,
            'light_azimuth': 45.0,
            'light_level': 0.65,
            'light_warmth': 0.0,
            'sky_haze': 0.2,
            'mist_amount': 0.0,
            'mist_height': 0.35,
            'mist_motion': 0.25,
            'rain_amount': 0.0,
            'lightning_amount': 0.0,
            'mood': 'neutral'},
  'steps': [{'request': 'make it a warm sunset', 'expect': {'sky_elevation': (0, 15), 'light_warmth': (0.4, 1)}},
            {'request': 'add thick mist but keep the lighting exactly as it is',
             'expect': {'mist_amount': (0.6, 1)},
             'preserve_previous': ['sky_elevation', 'light_elevation', 'light_azimuth', 'light_level', 'light_warmth', 'sky_haze']},
            {'request': 'make the mist almost completely still, change nothing else',
             'expect': {'mist_motion': (0, 0.15)},
             'preserve_previous': ['sky_elevation',
                                   'light_elevation',
                                   'light_azimuth',
                                   'light_level',
                                   'light_warmth',
                                   'sky_haze',
                                   'mist_amount',
                                   'mist_height',
                                   'rain_amount',
                                   'lightning_amount',
                                   'mood']},
            {'request': 'turn it into night but keep the mist exactly as it is',
             'expect': {'sky_elevation': (-12, -0.1)},
             'preserve_previous': ['mist_amount', 'mist_height', 'mist_motion']},
            {'request': 'remove the mist only',
             'exact': {'mist_amount': 0.0},
             'preserve_previous': ['sky_elevation',
                                   'light_elevation',
                                   'light_azimuth',
                                   'light_level',
                                   'light_warmth',
                                   'sky_haze',
                                   'rain_amount',
                                   'lightning_amount']}]},
 {'name': 'storm_control',
  'start': {'sky_elevation': 45.0,
            'light_elevation': 45.0,
            'light_azimuth': 45.0,
            'light_level': 0.65,
            'light_warmth': 0.0,
            'sky_haze': 0.2,
            'mist_amount': 0.0,
            'mist_height': 0.35,
            'mist_motion': 0.25,
            'rain_amount': 0.0,
            'lightning_amount': 0.0,
            'mood': 'neutral'},
  'steps': [{'request': 'heavy thunderstorm with frequent lightning', 'expect': {'rain_amount': (0.65, 1), 'lightning_amount': (0.55, 1)}},
            {'request': 'stop the lightning but keep the rain and lighting exactly the same',
             'exact': {'lightning_amount': 0.0},
             'preserve_previous': ['sky_elevation',
                                   'light_elevation',
                                   'light_azimuth',
                                   'light_level',
                                   'light_warmth',
                                   'sky_haze',
                                   'rain_amount',
                                   'mist_amount',
                                   'mist_height',
                                   'mist_motion']},
            {'request': 'reduce the rain to a light drizzle and change nothing else',
             'expect': {'rain_amount': (0.1, 0.45)},
             'preserve_previous': ['sky_elevation',
                                   'light_elevation',
                                   'light_azimuth',
                                   'light_level',
                                   'light_warmth',
                                   'sky_haze',
                                   'mist_amount',
                                   'mist_height',
                                   'mist_motion',
                                   'lightning_amount',
                                   'mood']},
            {'request': 'stop the rain too, change nothing else',
             'exact': {'rain_amount': 0.0},
             'preserve_previous': ['sky_elevation',
                                   'light_elevation',
                                   'light_azimuth',
                                   'light_level',
                                   'light_warmth',
                                   'sky_haze',
                                   'mist_amount',
                                   'mist_height',
                                   'mist_motion',
                                   'lightning_amount',
                                   'mood']},
            {'request': 'now make it clear neutral midday',
             'expect': {'sky_elevation': (65, 90),
                        'light_elevation': (65, 90),
                        'sky_haze': (0, 0.35),
                        'rain_amount': (0, 0.05),
                        'lightning_amount': (0, 0.05)}}]},
 {'name': 'night_refinement',
  'start': {'sky_elevation': 45.0,
            'light_elevation': 45.0,
            'light_azimuth': 45.0,
            'light_level': 0.65,
            'light_warmth': 0.0,
            'sky_haze': 0.2,
            'mist_amount': 0.0,
            'mist_height': 0.35,
            'mist_motion': 0.25,
            'rain_amount': 0.0,
            'lightning_amount': 0.0,
            'mood': 'neutral'},
  'steps': [{'request': 'clear moonlit night', 'expect': {'sky_elevation': (-12, -0.1), 'light_warmth': (-1, 0.15)}},
            {'request': 'make only the key light warmer, keep the time of day exactly the same',
             'expect': {'light_warmth': (0.15, 1)},
             'preserve_previous': ['sky_elevation']},
            {'request': 'add moderate rain but no lightning, keep the lighting exactly the same',
             'expect': {'rain_amount': (0.25, 0.7), 'lightning_amount': (0, 0.05)},
             'preserve_previous': ['sky_elevation', 'light_elevation', 'light_azimuth', 'light_level', 'light_warmth', 'sky_haze']},
            {'request': 'make it eerie but do not make it darker and do not change the weather',
             'preserve_previous': ['light_level', 'mist_amount', 'mist_height', 'mist_motion', 'rain_amount', 'lightning_amount']},
            {'request': 'remove the rain only and keep everything else',
             'exact': {'rain_amount': 0.0},
             'preserve_previous': ['sky_elevation',
                                   'light_elevation',
                                   'light_azimuth',
                                   'light_level',
                                   'light_warmth',
                                   'sky_haze',
                                   'mist_amount',
                                   'mist_height',
                                   'mist_motion',
                                   'lightning_amount',
                                   'mood']}]}]
REPEATABILITY_CASES = [{'name': 'repeat_sunset',
  'request': 'warm hazy sunset',
  'expect': {'sky_elevation': (0, 15), 'light_warmth': (0.4, 1), 'sky_haze': (0.4, 1)}},
 {'name': 'repeat_night', 'request': 'clear moonlit night', 'expect': {'sky_elevation': (-12, -0.1), 'light_warmth': (-1, 0.15)}},
 {'name': 'repeat_mist',
  'request': 'thick ground-hugging mist with little movement',
  'expect': {'mist_amount': (0.6, 1), 'mist_height': (0, 0.35), 'mist_motion': (0, 0.4)}},
 {'name': 'repeat_storm',
  'request': 'heavy thunderstorm with frequent lightning',
  'expect': {'rain_amount': (0.65, 1), 'lightning_amount': (0.55, 1)}},
 {'name': 'repeat_preserve',
  'request': 'make the mist thicker but keep all lighting exactly the same',
  'current': {'sky_elevation': 7,
              'light_elevation': 10,
              'light_azimuth': 225,
              'light_level': 0.85,
              'light_warmth': 0.8,
              'sky_haze': 0.7,
              'mist_amount': 0.2,
              'mist_height': 0.35,
              'mist_motion': 0.25,
              'rain_amount': 0.0,
              'lightning_amount': 0.0,
              'mood': 'neutral'},
  'expect': {'mist_amount': (0.45, 1)},
  'preserve': ['sky_elevation', 'light_elevation', 'light_azimuth', 'light_level', 'light_warmth', 'sky_haze']}]
REPEAT_RUNS = 3

PREVIEW_HTML = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>Tangible Worlds - Atmosphere Schema Preview</title>\n<style>\n    * { box-sizing: border-box; }\n    body { margin: 0; overflow: hidden; background: #111; font-family: monospace; }\n    #info {\n        position: fixed; top: 12px; left: 12px; z-index: 10;\n        color: #d7dde3; background: rgba(0,0,0,0.45);\n        padding: 10px 12px; line-height: 1.45; max-width: 480px;\n    }\n    #info strong { color: #fff; }\n    #status { white-space: pre-wrap; margin-top: 6px; }\n</style>\n</head>\n<body>\n<div id="info">\n    <strong>atmosphere schema preview</strong><br>\n    load one 12-field atmosphere json and render it in isolation<br>\n    query params: ?state=sample.json&frame=normal|later|flash\n    <div id="status">loading…</div>\n</div>\n\n<script type="importmap">\n{\n    "imports": {\n        "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",\n        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"\n    }\n}\n</script>\n\n<script type="module">\nimport * as THREE from \'three\';\nimport { OrbitControls } from \'three/addons/controls/OrbitControls.js\';\nimport { Sky } from \'three/addons/objects/Sky.js\';\nimport { ImprovedNoise } from \'three/addons/math/ImprovedNoise.js\';\n\nconst TABLE_SIZE = 10;\nconst FIXED_TABLE_COLOR = 0x777777;\nconst statusEl = document.getElementById(\'status\');\nconst params = new URLSearchParams(window.location.search);\nconst statePath = params.get(\'state\');\nconst frameMode = params.get(\'frame\') || \'live\';\nconst forceStatic = frameMode === \'normal\' || frameMode === \'later\' || frameMode === \'flash\';\nconst snapshotTime = frameMode === \'later\' || frameMode === \'flash\' ? 12.0 : 0.0;\nconst forcedFlashStrength = frameMode === \'flash\' ? 1.0 : 0.0;\n\nwindow.__previewReady = false;\nwindow.__previewState = null;\n\nconst scene = new THREE.Scene();\nconst camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 100);\ncamera.position.set(0, 12, 5);\ncamera.lookAt(0, 0, 0);\n\nconst renderer = new THREE.WebGLRenderer({ antialias: true });\nrenderer.setSize(innerWidth, innerHeight);\nrenderer.setPixelRatio(devicePixelRatio);\nrenderer.shadowMap.enabled = true;\nrenderer.shadowMap.type = THREE.PCFSoftShadowMap;\nrenderer.toneMapping = THREE.ACESFilmicToneMapping;\ndocument.body.appendChild(renderer.domElement);\n\nconst controls = new OrbitControls(camera, renderer.domElement);\ncontrols.enableDamping = true;\ncontrols.target.set(0, 0.4, 0);\ncontrols.enablePan = false;\n\nconst keyLight = new THREE.DirectionalLight(0xffffff, 1.0);\nkeyLight.castShadow = true;\nkeyLight.shadow.camera.left = -TABLE_SIZE;\nkeyLight.shadow.camera.right = TABLE_SIZE;\nkeyLight.shadow.camera.top = TABLE_SIZE;\nkeyLight.shadow.camera.bottom = -TABLE_SIZE;\nkeyLight.shadow.camera.near = 0.5;\nkeyLight.shadow.camera.far = 50;\nkeyLight.shadow.mapSize.set(2048, 2048);\nkeyLight.shadow.bias = -0.001;\nscene.add(keyLight);\n\nfunction setLightAngle(elevationDeg, azimuthDeg) {\n    const dist = TABLE_SIZE * 3;\n    const el = THREE.MathUtils.degToRad(elevationDeg);\n    const az = THREE.MathUtils.degToRad(azimuthDeg);\n    keyLight.position.set(\n        dist * Math.cos(el) * Math.cos(az),\n        dist * Math.sin(el),\n        dist * Math.cos(el) * Math.sin(az)\n    );\n}\n\nconst sky = new Sky();\nsky.scale.setScalar(450000);\nconst skyUniforms = sky.material.uniforms;\nconst skySun = new THREE.Vector3();\n\nfunction setSkySun(elevationDeg, azimuthDeg = 180) {\n    const phi = THREE.MathUtils.degToRad(90 - elevationDeg);\n    const theta = THREE.MathUtils.degToRad(azimuthDeg);\n    skySun.setFromSphericalCoords(1, phi, theta);\n    skyUniforms.sunPosition.value.copy(skySun);\n}\n\nconst environmentScene = new THREE.Scene();\nconst pmrem = new THREE.PMREMGenerator(renderer);\nenvironmentScene.add(sky);\nlet environmentTarget = pmrem.fromScene(environmentScene);\nscene.environment = environmentTarget.texture;\nscene.add(sky);\n\nfunction refreshEnvironment() {\n    if (sky.parent !== environmentScene) environmentScene.add(sky);\n    environmentTarget.dispose();\n    environmentTarget = pmrem.fromScene(environmentScene);\n    scene.environment = environmentTarget.texture;\n    if (sky.parent !== scene) scene.add(sky);\n}\n\nconst tableMat = new THREE.MeshStandardMaterial({ color: FIXED_TABLE_COLOR, roughness: 0.8 });\nconst table = new THREE.Mesh(new THREE.PlaneGeometry(TABLE_SIZE, TABLE_SIZE), tableMat);\ntable.rotation.x = -Math.PI / 2;\ntable.receiveShadow = true;\nscene.add(table);\n\nconst grid = new THREE.GridHelper(TABLE_SIZE, 10, 0x46515a, 0x364049);\ngrid.position.y = 0.012;\nscene.add(grid);\n\nconst cube = new THREE.Mesh(\n    new THREE.BoxGeometry(1.2, 1.2, 1.2),\n    new THREE.MeshStandardMaterial({ color: 0x808080, roughness: 0.75 })\n);\ncube.position.set(1, 0.6, 1);\ncube.castShadow = true;\ncube.receiveShadow = true;\nscene.add(cube);\n\nfunction smoothstep(edge0, edge1, value) {\n    const x = THREE.MathUtils.clamp((value - edge0) / (edge1 - edge0), 0, 1);\n    return x * x * (3 - 2 * x);\n}\n\nfunction makeMistTexture(seed) {\n    const size = 256;\n    const canvas = document.createElement(\'canvas\');\n    canvas.width = canvas.height = size;\n    const ctx = canvas.getContext(\'2d\');\n    const image = ctx.createImageData(size, size);\n    const noise = new ImprovedNoise();\n\n    for (let y = 0; y < size; y++) {\n        const v = y / (size - 1);\n        for (let x = 0; x < size; x++) {\n            const u = x / (size - 1);\n            const px = u * 3.3;\n            const py = v * 3.3;\n\n            const coarse = (noise.noise(px, seed, py) + 1) * 0.5;\n            const mid = (noise.noise(px * 1.9 + 13.2, seed + 7.1, py * 1.9 + 5.8) + 1) * 0.5;\n            const fine = (noise.noise(px * 3.7 + 23.4, seed + 13.7, py * 3.7 + 17.2) + 1) * 0.5;\n            const n = 0.64 * coarse + 0.26 * mid + 0.10 * fine;\n\n            let alpha = smoothstep(0.33, 0.70, n);\n            const edgeX = smoothstep(0, 0.06, u) * smoothstep(0, 0.06, 1 - u);\n            const edgeY = smoothstep(0, 0.06, v) * smoothstep(0, 0.06, 1 - v);\n            alpha *= edgeX * edgeY;\n\n            const i = (y * size + x) * 4;\n            const value = Math.round(alpha * 255);\n            image.data[i] = value;\n            image.data[i + 1] = value;\n            image.data[i + 2] = value;\n            image.data[i + 3] = 255;\n        }\n    }\n\n    ctx.putImageData(image, 0, 0);\n    const texture = new THREE.CanvasTexture(canvas);\n    texture.minFilter = THREE.LinearFilter;\n    texture.magFilter = THREE.LinearFilter;\n    return texture;\n}\n\nconst mistSources = [makeMistTexture(0), makeMistTexture(17), makeMistTexture(41)];\n\nconst mistConfigs = [\n    { y: 0.12, wobble: 0.02, size: 20, opacityA: 0.072, opacityB: 0.055, sourceA: 0, sourceB: 1, speedAX: 0.018, speedAZ: 0.007, speedBX: -0.009, speedBZ: 0.014, rotA: 0.0035, rotB: -0.0025, phase: 0.0 },\n    { y: 0.25, wobble: 0.024, size: 19, opacityA: 0.065, opacityB: 0.050, sourceA: 1, sourceB: 2, speedAX: -0.015, speedAZ: 0.011, speedBX: 0.011, speedBZ: -0.009, rotA: -0.0025, rotB: 0.0035, phase: 0.8 },\n    { y: 0.42, wobble: 0.03, size: 18, opacityA: 0.058, opacityB: 0.045, sourceA: 2, sourceB: 0, speedAX: 0.013, speedAZ: -0.011, speedBX: -0.007, speedBZ: 0.012, rotA: 0.0025, rotB: -0.002, phase: 1.7 },\n    { y: 0.64, wobble: 0.035, size: 17, opacityA: 0.052, opacityB: 0.040, sourceA: 0, sourceB: 2, speedAX: -0.011, speedAZ: -0.008, speedBX: 0.008, speedBZ: 0.010, rotA: -0.002, rotB: 0.003, phase: 2.5 },\n    { y: 0.90, wobble: 0.04, size: 16, opacityA: 0.045, opacityB: 0.034, sourceA: 1, sourceB: 0, speedAX: 0.009, speedAZ: 0.009, speedBX: -0.006, speedBZ: -0.007, rotA: 0.0018, rotB: -0.0026, phase: 3.2 },\n    { y: 1.18, wobble: 0.045, size: 15, opacityA: 0.038, opacityB: 0.029, sourceA: 2, sourceB: 1, speedAX: -0.007, speedAZ: 0.006, speedBX: 0.005, speedBZ: -0.005, rotA: -0.0018, rotB: 0.0022, phase: 3.9 },\n];\n\nfunction makeMistLayer(alphaMap, opacity, size, tint) {\n    const material = new THREE.MeshStandardMaterial({\n        color: tint,\n        roughness: 1,\n        metalness: 0,\n        transparent: true,\n        opacity,\n        alphaMap,\n        depthWrite: false,\n        side: THREE.DoubleSide,\n    });\n\n    const layer = new THREE.Mesh(new THREE.PlaneGeometry(size, size), material);\n    layer.rotation.x = -Math.PI / 2;\n    return layer;\n}\n\nconst mistGroups = mistConfigs.map((config) => {\n    const group = new THREE.Group();\n    const alphaA = mistSources[config.sourceA].clone();\n    alphaA.wrapS = alphaA.wrapT = THREE.RepeatWrapping;\n    alphaA.needsUpdate = true;\n\n    const alphaB = mistSources[config.sourceB].clone();\n    alphaB.wrapS = alphaB.wrapT = THREE.RepeatWrapping;\n    alphaB.needsUpdate = true;\n\n    const layerA = makeMistLayer(alphaA, config.opacityA, config.size, 0xb9c6d6);\n    const layerB = makeMistLayer(alphaB, config.opacityB, config.size * 0.96, 0xc7d2df);\n    layerB.position.y = 0.01;\n    layerB.rotation.z = Math.PI * 0.18;\n\n    group.userData = { config, layerA, layerB };\n    group.add(layerA);\n    group.add(layerB);\n    scene.add(group);\n    return group;\n});\n\nfunction wrapOffset(value) {\n    return ((value % 1) + 1) % 1;\n}\n\nconst RAIN_COUNT = 450;\nconst rainBase = Array.from({ length: RAIN_COUNT }, (_, i) => {\n    const x = ((((i * 73) % 1000) / 1000) - 0.5) * TABLE_SIZE * 1.35;\n    const z = ((((i * 37 + 211) % 1000) / 1000) - 0.5) * TABLE_SIZE * 1.35;\n    const y0 = 0.4 + ((((i * 91 + 17) % 1000) / 1000) * 8.5);\n    const speed = 5.2 + ((((i * 53 + 101) % 1000) / 1000) * 2.8);\n    const length = 0.16 + ((((i * 29 + 401) % 1000) / 1000) * 0.20);\n    return { x, z, y0, speed, length };\n});\n\nconst rainPositions = new Float32Array(RAIN_COUNT * 2 * 3);\nconst rainGeometry = new THREE.BufferGeometry();\nconst rainPositionAttribute = new THREE.BufferAttribute(rainPositions, 3);\nrainPositionAttribute.setUsage(THREE.DynamicDrawUsage);\nrainGeometry.setAttribute(\'position\', rainPositionAttribute);\nconst rainMaterial = new THREE.LineBasicMaterial({\n    color: 0xa9bed0,\n    transparent: true,\n    opacity: 0.0,\n    depthWrite: false,\n});\nconst rain = new THREE.LineSegments(rainGeometry, rainMaterial);\nrain.renderOrder = 30;\nscene.add(rain);\n\nfunction applyRainAtTime(timeSeconds, amount) {\n    const visibleCount = Math.round(RAIN_COUNT * amount);\n    for (let i = 0; i < RAIN_COUNT; i++) {\n        const off = i * 6;\n        if (i >= visibleCount) {\n            rainPositions[off] = rainPositions[off + 1] = rainPositions[off + 2] = 0;\n            rainPositions[off + 3] = rainPositions[off + 4] = rainPositions[off + 5] = 0;\n            continue;\n        }\n        const base = rainBase[i];\n        const span = 9.6;\n        const cycleY = (base.y0 - timeSeconds * base.speed) % span;\n        const y = cycleY < 0 ? cycleY + span : cycleY;\n        rainPositions[off] = base.x;\n        rainPositions[off + 1] = y;\n        rainPositions[off + 2] = base.z;\n        rainPositions[off + 3] = base.x - 0.05;\n        rainPositions[off + 4] = y - base.length;\n        rainPositions[off + 5] = base.z + 0.025;\n    }\n    rainPositionAttribute.needsUpdate = true;\n}\n\nfunction lerpColorHex(a, b, t) {\n    const ca = new THREE.Color(a);\n    const cb = new THREE.Color(b);\n    return ca.lerp(cb, t);\n}\n\nconst defaultState = {\n    sky_elevation: 7,\n    light_elevation: 10,\n    light_azimuth: 225,\n    light_level: 0.88,\n    light_warmth: 0.82,\n    sky_haze: 0.72,\n    mist_amount: 0.15,\n    mist_height: 0.35,\n    mist_motion: 0.15,\n    rain_amount: 0.0,\n    lightning_amount: 0.0,\n    mood: \'sample warm hazy sunset\'\n};\n\nfunction clampState(raw) {\n    return {\n        sky_elevation: THREE.MathUtils.clamp(Number(raw.sky_elevation ?? 45), -12, 90),\n        light_elevation: THREE.MathUtils.clamp(Number(raw.light_elevation ?? 45), 0, 90),\n        light_azimuth: ((Number(raw.light_azimuth ?? 45) % 360) + 360) % 360,\n        light_level: THREE.MathUtils.clamp(Number(raw.light_level ?? 0.65), 0, 1),\n        light_warmth: THREE.MathUtils.clamp(Number(raw.light_warmth ?? 0), -1, 1),\n        sky_haze: THREE.MathUtils.clamp(Number(raw.sky_haze ?? 0.2), 0, 1),\n        mist_amount: THREE.MathUtils.clamp(Number(raw.mist_amount ?? 0), 0, 1),\n        mist_height: THREE.MathUtils.clamp(Number(raw.mist_height ?? 0.35), 0, 1),\n        mist_motion: THREE.MathUtils.clamp(Number(raw.mist_motion ?? 0.25), 0, 1),\n        rain_amount: THREE.MathUtils.clamp(Number(raw.rain_amount ?? 0), 0, 1),\n        lightning_amount: THREE.MathUtils.clamp(Number(raw.lightning_amount ?? 0), 0, 1),\n        mood: String(raw.mood ?? \'neutral\')\n    };\n}\n\nlet activeState = clampState(defaultState);\nlet lastFrameTime = null;\nlet nextFlashAt = 3.5;\nlet flashStartedAt = null;\n\nfunction resetLightningClock() {\n    nextFlashAt = 3.5;\n    flashStartedAt = null;\n}\n\nfunction lightningStrength(timeSeconds) {\n    if (flashStartedAt === null) {\n        if (timeSeconds >= nextFlashAt) flashStartedAt = timeSeconds;\n        else return 0;\n    }\n    const t = timeSeconds - flashStartedAt;\n    if (t < 0.055) return t / 0.055;\n    if (t < 0.115) return 1.0 - (t - 0.055) / 0.060 * 0.82;\n    if (t < 0.180) return 0.18 + (t - 0.115) / 0.065 * 0.62;\n    if (t < 0.340) return 0.80 * (1.0 - (t - 0.180) / 0.160);\n    flashStartedAt = null;\n    nextFlashAt = timeSeconds + 4.0 + 6.0 * 0.5;\n    return 0;\n}\n\nfunction applyMistAtTime(timeSeconds, amount, height, motion) {\n    const baseMinY = 0.08;\n    const baseMaxY = 1.35;\n    const extraHeight = height * 0.9;\n    const motionScale = 0.35 + motion * 1.35;\n    const amountScale = amount;\n\n    mistGroups.forEach((group) => {\n        const { config, layerA, layerB } = group.userData;\n        const normalizedY = (config.y - 0.12) / (1.18 - 0.12);\n        const targetY = THREE.MathUtils.lerp(baseMinY, baseMaxY + extraHeight, normalizedY);\n        const wobble = config.wobble * motionScale;\n\n        group.visible = amount > 0.01;\n        group.position.y = targetY + Math.sin(timeSeconds * 0.22 * motionScale + config.phase) * wobble;\n\n        layerA.rotation.z = timeSeconds * config.rotA * motionScale;\n        layerB.rotation.z = Math.PI * 0.18 + timeSeconds * config.rotB * motionScale;\n        layerA.material.alphaMap.offset.set(\n            wrapOffset(timeSeconds * config.speedAX * motionScale),\n            wrapOffset(timeSeconds * config.speedAZ * motionScale)\n        );\n        layerB.material.alphaMap.offset.set(\n            wrapOffset(timeSeconds * config.speedBX * motionScale),\n            wrapOffset(timeSeconds * config.speedBZ * motionScale)\n        );\n\n        layerA.material.opacity = config.opacityA * amountScale;\n        layerB.material.opacity = config.opacityB * amountScale;\n    });\n}\n\nfunction applyStateToRenderer(state, timeSeconds, flashStrength) {\n    const lightWarmT = (state.light_warmth + 1) * 0.5;\n    const keyColor = lightWarmT < 0.5\n        ? lerpColorHex(0xbcd1f0, 0xffffff, lightWarmT / 0.5)\n        : lerpColorHex(0xffffff, 0xff9f5f, (lightWarmT - 0.5) / 0.5);\n\n    // sky_elevation: where the procedural sky sun sits, range -12..90.\n    // ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js\n    // renderer mapping: low or negative elevation produces sunset/night sky.\n    setSkySun(state.sky_elevation, 180);\n\n    // light_elevation: height of the key light and shadows, range 0..90.\n    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html\n    // renderer mapping: lower values produce longer shadows.\n\n    // light_azimuth: compass direction of the key light, range 0..360.\n    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html\n    // renderer mapping: rotates the key light around the table.\n    setLightAngle(state.light_elevation, state.light_azimuth);\n\n    // light_level: overall key-light strength, range 0..1.\n    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/lights/DirectionalLight.html\n    // renderer mapping: converted to a readable directional-light intensity.\n    const baseIntensity = THREE.MathUtils.lerp(0.45, 6.0, Math.pow(state.light_level, 1.15));\n\n    // light_warmth: cool to warm light colour, range -1..1.\n    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/math/Color.html\n    // renderer mapping: negative values push toward cool moonlight, positive toward sunset warmth.\n    keyLight.color.copy(keyColor);\n    keyLight.intensity = baseIntensity + flashStrength * (3.0 + state.lightning_amount * 5.0);\n\n    // sky_haze: atmospheric haze, range 0..1.\n    // ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/objects/Sky.js\n    // renderer mapping: converted into turbidity and mie scattering parameters.\n    skyUniforms.turbidity.value = THREE.MathUtils.lerp(2.0, 12.0, state.sky_haze);\n    skyUniforms.rayleigh.value = THREE.MathUtils.lerp(1.8, 0.45, state.sky_haze);\n    skyUniforms.mieCoefficient.value = THREE.MathUtils.lerp(0.002, 0.010, state.sky_haze);\n    skyUniforms.mieDirectionalG.value = THREE.MathUtils.lerp(0.80, 0.90, state.sky_haze);\n    refreshEnvironment();\n    scene.environmentIntensity = THREE.MathUtils.lerp(2.4, 0.25, state.light_level);\n\n    // mist_amount: visible density of moving mist, range 0..1.\n    // ref: https://developer.nvidia.com/gpugems/gpugems/part-vi-beyond-triangles/chapter-39-volume-rendering-techniques\n    // renderer mapping: scales the opacity of the approved layered mist slices.\n\n    // mist_height: vertical spread of the mist, range 0..1.\n    // ref: https://developer.nvidia.com/gpugems/gpugems/part-vi-beyond-triangles/chapter-39-volume-rendering-techniques\n    // renderer mapping: lifts the top mist bands higher into the scene.\n\n    // mist_motion: drift and morph activity of the mist, range 0..1.\n    // ref: https://github.com/mrdoob/three.js/blob/r170/examples/jsm/math/ImprovedNoise.js\n    // renderer mapping: scales drift, rotation and wobble speed.\n    applyMistAtTime(timeSeconds, state.mist_amount, state.mist_height, state.mist_motion);\n\n    // rain_amount: rainfall amount, range 0..1.\n    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/objects/LineSegments.html\n    // renderer mapping: controls visible raindrop count and opacity.\n    rain.visible = state.rain_amount > 0.01;\n    rainMaterial.opacity = state.rain_amount * (0.30 + flashStrength * 0.18);\n    applyRainAtTime(timeSeconds, state.rain_amount);\n\n    // lightning_amount: storm-flash strength/frequency control, range 0..1.\n    // ref: https://github.com/mrdoob/three.js/blob/r170/docs/api/en/renderers/WebGLRenderer.html\n    // renderer mapping: boosts key light and exposure during flashes.\n    const baseExposure = THREE.MathUtils.lerp(0.78, 0.48, state.light_level);\n    renderer.toneMappingExposure = baseExposure + flashStrength * 0.30;\n\n    // mood: descriptive label only.\n    // ref: project decision, no renderer preset behaviour.\n    // renderer mapping: shown in the overlay only.\n    statusEl.textContent = [\n        `mood: ${state.mood}`,\n        `frame: ${frameMode}`,\n        statePath ? `state: ${statePath}` : \'state: embedded sample\'\n    ].join(\'\\n\');\n}\n\nasync function loadState() {\n    if (!statePath) return clampState(defaultState);\n    const response = await fetch(statePath, { cache: \'no-store\' });\n    if (!response.ok) throw new Error(`could not load ${statePath}: ${response.status}`);\n    const raw = await response.json();\n    return clampState(raw);\n}\n\nfunction renderStaticFrame() {\n    applyStateToRenderer(activeState, snapshotTime, forcedFlashStrength * activeState.lightning_amount);\n    controls.update();\n    renderer.render(scene, camera);\n    window.__previewReady = true;\n    window.__previewState = activeState;\n}\n\nfunction animate(now) {\n    requestAnimationFrame(animate);\n    const timeSeconds = now * 0.001;\n    const flash = activeState.lightning_amount > 0.01 ? lightningStrength(timeSeconds) * activeState.lightning_amount : 0;\n    applyStateToRenderer(activeState, timeSeconds, flash);\n    controls.update();\n    renderer.render(scene, camera);\n    if (!window.__previewReady) {\n        window.__previewReady = true;\n        window.__previewState = activeState;\n    }\n}\n\nloadState()\n    .then((state) => {\n        activeState = state;\n        resetLightningClock();\n        if (forceStatic) renderStaticFrame();\n        else requestAnimationFrame(animate);\n    })\n    .catch((error) => {\n        statusEl.textContent = `error\\n${error.message}`;\n        console.error(error);\n    });\n\naddEventListener(\'resize\', () => {\n    camera.aspect = innerWidth / innerHeight;\n    camera.updateProjectionMatrix();\n    renderer.setSize(innerWidth, innerHeight);\n    if (forceStatic && window.__previewState) renderStaticFrame();\n});\n</script>\n</body>\n</html>\n'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def strip_think(text):
    # ref: https://huggingface.co/Qwen/Qwen3-8B
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "<think>" in text:
        text = text.split("<think>")[0]
    return text.strip()


def ask_qwen(prompt, current):
    # ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
    user_text = (
        f"Current modifiers: {json.dumps(current)}\n"
        f"User request: {prompt}\n"
        "Return the complete modifier JSON:"
    )
    response = requests.post(
        LMSTUDIO_URL,
        json={
            "model": LMSTUDIO_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{user_text} /no_think"},
            ],
            "temperature": 0.3,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        timeout=60,
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()
    raw = strip_think(raw).replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def validate_schema(state):
    errors = []
    expected = set(MODIFIER_SCHEMA)
    actual = set(state)
    if expected != actual:
        if expected - actual:
            errors.append(f"missing keys: {sorted(expected - actual)}")
        if actual - expected:
            errors.append(f"extra keys: {sorted(actual - expected)}")

    for key, (low, high) in RANGES.items():
        value = state.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{key} is not numeric: {value!r}")
        elif not low <= value <= high:
            errors.append(f"{key} out of range: {value}")

    if not isinstance(state.get("mood"), str) or not state.get("mood", "").strip():
        errors.append("mood must be non-empty text")
    return errors


def choose_frame(state):
    # one screenshot per scene. storm scenes use a flash frame; moving weather
    # uses a later frame; static scenes use the normal frame.
    if state["lightning_amount"] >= 0.15:
        return "flash"
    if state["mist_amount"] >= 0.10 or state["rain_amount"] >= 0.10:
        return "later"
    return "normal"


def start_server(root):
    handler = partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def capture_screenshot(page, url, output_png):
    # ref: https://playwright.dev/python/docs/screenshots
    page.goto(url, wait_until="networkidle")
    page.wait_for_function("window.__previewReady === true", timeout=15000)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.screenshot(path=str(output_png), full_page=False)
    if not output_png.exists() or output_png.stat().st_size < 1000:
        raise RuntimeError("playwright returned without a usable screenshot")


def slug_index(index, name):
    return f"{index:03d}_{name}"



def validate_case(case, current, result, previous=None):
    errors = validate_schema(result)

    for key, bounds in case.get("expect", {}).items():
        value = result.get(key)
        low, high = bounds
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not low <= value <= high:
            errors.append(f"expected {key} in {low}..{high}, got {value!r}")

    for key, expected in case.get("exact", {}).items():
        if result.get(key) != expected:
            errors.append(f"expected {key} exactly {expected!r}, got {result.get(key)!r}")

    for key in case.get("preserve", []):
        if result.get(key) != current.get(key):
            errors.append(f"preservation failed for {key}: expected {current.get(key)!r}, got {result.get(key)!r}")

    for key in case.get("preserve_numeric", []):
        if result.get(key) != current.get(key):
            errors.append(f"numeric preservation failed for {key}: expected {current.get(key)!r}, got {result.get(key)!r}")

    for key in case.get("less_than_current", []):
        if not result.get(key) < current.get(key):
            errors.append(f"expected {key} < current {current.get(key)!r}, got {result.get(key)!r}")

    for key in case.get("greater_than_current", []):
        if not result.get(key) > current.get(key):
            errors.append(f"expected {key} > current {current.get(key)!r}, got {result.get(key)!r}")

    if previous is not None:
        for key in case.get("preserve_previous", []):
            if result.get(key) != previous.get(key):
                errors.append(f"sequence preservation failed for {key}: expected {previous.get(key)!r}, got {result.get(key)!r}")

    return errors


def safe_slug(text, max_words=8):
    words = re.findall(r"[a-z0-9]+", text.lower())[:max_words]
    return "_".join(words) or "experiment"


def write_case_files(case_dir, basename, prompt, current, result=None, errors=None):
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / f"{basename}_prompt.txt").write_text(prompt + "\n")
    (case_dir / f"{basename}_current.json").write_text(json.dumps(current, indent=2))
    if result is not None:
        (case_dir / f"{basename}.json").write_text(json.dumps(result, indent=2))
    if errors:
        (case_dir / f"{basename}_errors.txt").write_text("\n".join(errors) + "\n")


def screenshot_result(page, port, output_root, case_dir, basename, result):
    schema_errors = validate_schema(result)
    if schema_errors:
        return None, schema_errors

    frame = choose_frame(result)
    state_path = case_dir / f"{basename}.json"
    state_rel = state_path.relative_to(output_root).as_posix()
    url = (
        f"http://127.0.0.1:{port}/_preview.html"
        f"?state={quote(state_rel, safe='/')}&frame={frame}"
    )
    png = case_dir / f"{basename}.png"
    capture_screenshot(page, url, png)
    return {"file": str(png.relative_to(output_root)), "frame": frame}, []


def category_summary(records):
    totals = {}
    for record in records:
        category = record["category"]
        bucket = totals.setdefault(category, {"passed": 0, "total": 0})
        bucket["total"] += 1
        if record["status"] == "pass":
            bucket["passed"] += 1
    return totals


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = Path(f"atmosphere_visual_deep_{timestamp}").resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    (output_root / "_preview.html").write_text(PREVIEW_HTML)

    strict_root = output_root / "strict"
    review_root = output_root / "review"
    sequence_root = output_root / "sequences"
    repeat_root = output_root / "repeatability"

    total_calls = (
        len(STRICT_TESTS)
        + len(REVIEW_CASES)
        + sum(len(sequence["steps"]) for sequence in SEQUENCES)
        + len(REPEATABILITY_CASES) * REPEAT_RUNS
    )

    print("tangible worlds deep visual atmosphere test")
    print(f"model: {LMSTUDIO_MODEL}")
    print(f"strict tests: {len(STRICT_TESTS)}")
    print(f"review-only cases: {len(REVIEW_CASES)}")
    print(f"stateful sequence steps: {sum(len(s['steps']) for s in SEQUENCES)}")
    print(f"repeatability calls: {len(REPEATABILITY_CASES) * REPEAT_RUNS}")
    print(f"total qwen calls: {total_calls}")
    print(f"output: {output_root}")
    print()

    evidence = {
        "model": LMSTUDIO_MODEL,
        "total_qwen_calls": total_calls,
        "strict": [],
        "review": [],
        "sequences": [],
        "repeatability": [],
    }

    screenshot_count = 0
    screenshot_failures = 0
    strict_passed = 0
    sequence_passed = 0
    sequence_total = 0
    repeat_passed = 0
    repeat_total = 0

    server, port = start_server(output_root)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        try:
            print("strict tests")
            for index, case in enumerate(STRICT_TESTS, start=1):
                basename = case["name"]
                case_dir = strict_root / f"{index:03d}_{case['category']}_{basename}"
                current = deepcopy(case.get("current", MODIFIER_SCHEMA))
                result = None
                errors = []
                screenshot = None

                try:
                    result = ask_qwen(case["request"], current)
                    errors = validate_case(case, current, result)
                    status = "pass" if not errors else "fail"
                except Exception as exc:
                    errors = [f"request/error: {exc}"]
                    status = "error"

                write_case_files(case_dir, basename, case["request"], current, result, errors)

                if result is not None and not validate_schema(result):
                    try:
                        screenshot, shot_errors = screenshot_result(page, port, output_root, case_dir, basename, result)
                        if shot_errors:
                            screenshot_failures += 1
                        else:
                            screenshot_count += 1
                    except Exception as exc:
                        screenshot_failures += 1
                        shot_errors = [f"screenshot/error: {exc}"]
                        (case_dir / f"{basename}_screenshot_error.txt").write_text("\n".join(shot_errors) + "\n")

                if status == "pass":
                    strict_passed += 1
                print(f"[{index:02d}/{len(STRICT_TESTS)}] {status.upper()} {case['category']}/{basename} -> {basename}.png")
                if errors:
                    for error in errors:
                        print(f"    - {error}")

                evidence["strict"].append({
                    "category": case["category"],
                    "name": basename,
                    "request": case["request"],
                    "current": current,
                    "result": result,
                    "errors": errors,
                    "status": status,
                    "screenshot": screenshot,
                })

            print("\nreview-only cases")
            for index, case in enumerate(REVIEW_CASES, start=1):
                basename = case["name"]
                case_dir = review_root / f"{index:03d}_{basename}"
                current = deepcopy(case.get("current", MODIFIER_SCHEMA))
                result = None
                errors = []
                screenshot = None

                try:
                    result = ask_qwen(case["request"], current)
                    errors = validate_schema(result)
                except Exception as exc:
                    errors = [f"request/error: {exc}"]

                write_case_files(case_dir, basename, case["request"], current, result, errors)
                if result is not None and not validate_schema(result):
                    try:
                        screenshot, shot_errors = screenshot_result(page, port, output_root, case_dir, basename, result)
                        if shot_errors:
                            screenshot_failures += 1
                        else:
                            screenshot_count += 1
                    except Exception as exc:
                        screenshot_failures += 1
                        (case_dir / f"{basename}_screenshot_error.txt").write_text(f"{exc}\n")

                print(f"[{index:02d}/{len(REVIEW_CASES)}] REVIEW {basename} -> {basename}.png")
                evidence["review"].append({
                    "name": basename,
                    "request": case["request"],
                    "current": current,
                    "result": result,
                    "schema_errors": errors,
                    "screenshot": screenshot,
                })

            print("\nstateful conversational sequences")
            for sequence_index, sequence in enumerate(SEQUENCES, start=1):
                current = deepcopy(sequence["start"])
                seq_dir = sequence_root / f"{sequence_index:02d}_{sequence['name']}"
                seq_record = {"name": sequence["name"], "steps": []}
                print(f"  sequence {sequence_index}: {sequence['name']}")

                for step_index, step in enumerate(sequence["steps"], start=1):
                    sequence_total += 1
                    previous = deepcopy(current)
                    step_slug = safe_slug(step["request"])
                    basename = f"{sequence['name']}_step_{step_index:02d}_{step_slug}"
                    case_dir = seq_dir / f"step_{step_index:02d}_{step_slug}"
                    result = None
                    errors = []
                    screenshot = None

                    try:
                        result = ask_qwen(step["request"], current)
                        errors = validate_case(step, current, result, previous=previous)
                        status = "pass" if not errors else "fail"
                    except Exception as exc:
                        errors = [f"request/error: {exc}"]
                        status = "error"

                    write_case_files(case_dir, basename, step["request"], previous, result, errors)
                    if result is not None and not validate_schema(result):
                        try:
                            screenshot, shot_errors = screenshot_result(page, port, output_root, case_dir, basename, result)
                            if shot_errors:
                                screenshot_failures += 1
                            else:
                                screenshot_count += 1
                        except Exception as exc:
                            screenshot_failures += 1
                            (case_dir / f"{basename}_screenshot_error.txt").write_text(f"{exc}\n")

                    if status == "pass":
                        sequence_passed += 1
                    if result is not None and not validate_schema(result):
                        current = deepcopy(result)

                    print(f"    step {step_index}: {status.upper()} -> {basename}.png")
                    if errors:
                        for error in errors:
                            print(f"      - {error}")

                    seq_record["steps"].append({
                        "step": step_index,
                        "name": basename,
                        "request": step["request"],
                        "previous": previous,
                        "result": result,
                        "errors": errors,
                        "status": status,
                        "screenshot": screenshot,
                    })

                evidence["sequences"].append(seq_record)

            print("\nrepeatability")
            for case_index, case in enumerate(REPEATABILITY_CASES, start=1):
                case_dir_root = repeat_root / f"{case_index:02d}_{case['name']}"
                record = {"name": case["name"], "request": case["request"], "runs": []}
                print(f"  {case['name']}")

                for run_index in range(1, REPEAT_RUNS + 1):
                    repeat_total += 1
                    basename = f"{case['name']}_run_{run_index:02d}"
                    case_dir = case_dir_root / f"run_{run_index:02d}"
                    current = deepcopy(case.get("current", MODIFIER_SCHEMA))
                    result = None
                    errors = []
                    screenshot = None

                    try:
                        result = ask_qwen(case["request"], current)
                        errors = validate_case(case, current, result)
                        status = "pass" if not errors else "fail"
                    except Exception as exc:
                        errors = [f"request/error: {exc}"]
                        status = "error"

                    write_case_files(case_dir, basename, case["request"], current, result, errors)
                    if result is not None and not validate_schema(result):
                        try:
                            screenshot, shot_errors = screenshot_result(page, port, output_root, case_dir, basename, result)
                            if shot_errors:
                                screenshot_failures += 1
                            else:
                                screenshot_count += 1
                        except Exception as exc:
                            screenshot_failures += 1
                            (case_dir / f"{basename}_screenshot_error.txt").write_text(f"{exc}\n")

                    if status == "pass":
                        repeat_passed += 1
                    print(f"    run {run_index}: {status.upper()} -> {basename}.png")
                    if errors:
                        for error in errors:
                            print(f"      - {error}")

                    record["runs"].append({
                        "run": run_index,
                        "name": basename,
                        "current": current,
                        "result": result,
                        "errors": errors,
                        "status": status,
                        "screenshot": screenshot,
                    })

                evidence["repeatability"].append(record)

        finally:
            browser.close()
            server.shutdown()
            server.server_close()

    categories = category_summary(evidence["strict"])
    strict_rate = strict_passed / len(STRICT_TESTS)
    sequence_rate = sequence_passed / sequence_total if sequence_total else 0
    repeat_rate = repeat_passed / repeat_total if repeat_total else 0

    preservation_records = [record for record in evidence["strict"] if record["category"] == "preservation"]
    preservation_passed = sum(record["status"] == "pass" for record in preservation_records)
    preservation_rate = preservation_passed / len(preservation_records) if preservation_records else 0

    schema_failures = 0
    for record in evidence["strict"]:
        result = record.get("result")
        if result is None or validate_schema(result):
            schema_failures += 1
    for record in evidence["review"]:
        result = record.get("result")
        if result is None or validate_schema(result):
            schema_failures += 1
    for sequence in evidence["sequences"]:
        for step in sequence["steps"]:
            result = step.get("result")
            if result is None or validate_schema(result):
                schema_failures += 1
    for record in evidence["repeatability"]:
        for run in record["runs"]:
            result = run.get("result")
            if result is None or validate_schema(result):
                schema_failures += 1

    gate_pass = (
        schema_failures == 0
        and strict_rate >= 0.90
        and preservation_rate == 1.0
        and sequence_rate >= 0.90
        and repeat_rate >= 0.90
        and screenshot_failures == 0
    )

    evidence["summary"] = {
        "strict_passed": strict_passed,
        "strict_total": len(STRICT_TESTS),
        "strict_rate": strict_rate,
        "categories": categories,
        "preservation_passed": preservation_passed,
        "preservation_total": len(preservation_records),
        "preservation_rate": preservation_rate,
        "sequence_passed": sequence_passed,
        "sequence_total": sequence_total,
        "sequence_rate": sequence_rate,
        "repeatability_passed": repeat_passed,
        "repeatability_total": repeat_total,
        "repeatability_rate": repeat_rate,
        "schema_failures": schema_failures,
        "screenshots_saved": screenshot_count,
        "screenshot_failures": screenshot_failures,
        "expected_screenshots": total_calls,
        "gate_pass": gate_pass,
    }

    results_file = output_root / "atmosphere_visual_deep_results.json"
    results_file.write_text(json.dumps(evidence, indent=2))

    print("\ncategory summary")
    for category, counts in categories.items():
        print(f"  {category}: {counts['passed']}/{counts['total']}")

    print("\nfinal summary")
    print(f"  strict: {strict_passed}/{len(STRICT_TESTS)} ({strict_rate:.1%})")
    print(f"  explicit preservation: {preservation_passed}/{len(preservation_records)} ({preservation_rate:.1%})")
    print(f"  stateful sequence steps: {sequence_passed}/{sequence_total} ({sequence_rate:.1%})")
    print(f"  repeatability: {repeat_passed}/{repeat_total} ({repeat_rate:.1%})")
    print(f"  schema/format failures: {schema_failures}")
    print(f"  screenshots: {screenshot_count}/{total_calls}")
    print(f"  screenshot failures: {screenshot_failures}")
    print(f"  integration gate: {'PASS' if gate_pass else 'FAIL'}")
    print(f"  folder: {output_root}")
    print(f"  saved: {results_file}")


if __name__ == "__main__":
    main()
