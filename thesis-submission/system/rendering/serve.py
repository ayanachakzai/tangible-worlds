"""
serve.py
--------
server for the rendering layer. serves welcome.html first on port 8080, with\nindex.html as the live study interface, and exposes
fifteen api routes.

GET:
    /api/scene         current scene_description.json, from the mapping layer
    /api/modifiers     current scene_modifiers.json, from the conversation layer
    /api/assignments   meanings assigned to tracked object ids
    /api/relations     proximity relations between objects
    /api/calibration   current table calibration

POST:
    /api/converse      command text to qwen3-8b, returns the 12-field
                       atmosphere modifiers and writes conversation_log.json
    /api/tts           relay to local pocket tts, browser cannot call it
                       directly because of pocket tts's cors origin list
    /api/assign        assign a meaning to an object id
    /api/rotate        set a mesh rotation
    /api/relate        create an interstitial relation
    /api/screenshot    save batched participant scene screenshots
    /api/move_log      append batched object movement events
    /api/calibrate     recalibrate the table plane
    /api/reset         clear scene state
    /api/mock_scene    inject a fake scene for testing without hardware

Usage:
    cd tangible-worlds/phase3-tabletop/rendering
    /opt/anaconda3/bin/python serve.py

    Then open http://localhost:8080 in your browser.

    Voice mode also needs the parakeet asr server on 8090 and pocket tts on 8000. See
    RUNBOOK.md section 1 for the full six-process start order.

References:
    Python http.server:
        https://docs.python.org/3/library/http.server.html
    Pocket TTS server:
        https://github.com/kyutai-labs/pocket-tts/blob/v2.1.0/pocket_tts/main.py
"""
import requests
import http.server
import base64
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

PORT = 8080
SCENE_DESC_PATH = "../mapping/scene_description.json"
MODIFIERS_PATH = "../conversation/scene_modifiers.json"

# phase 6b tts, 25 aug 2026. i keep pocket tts as a separate local cpu service.
# academic ref: rouard et al., "continuous audio language models", iclr 2026.
# https://arxiv.org/abs/2509.06926
# ref: https://github.com/kyutai-labs/pocket-tts/blob/v2.1.0/pocket_tts/main.py#L111-L166
POCKET_TTS_URL = "http://localhost:8000/tts"
POCKET_TTS_VOICE = "alba"

# conversation atmosphere translation, phase 5e, 21 aug 2026.
# the browser posts natural-language requests to /api/converse; qwen3-8b
# returns the semantic atmosphere controls consumed by the renderer.
# MODIFIER_SCHEMA + SYSTEM_PROMPT are deliberately duplicated in converse.py
# because the two scripts have different working-directory assumptions. keep
# both copies identical.
# ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
# ref: https://huggingface.co/Qwen/Qwen3-8B
CONV_LOG_PATH = "../conversation/conversation_log.json"

# object-move event log, sq3. jsonl not json because the browser appends
# batches all session; rewriting a whole json array per batch would grow
# quadratically over a study run.
# academic ref: hilbert & redmiles, acm computing surveys 32(4), 2000.
# https://doi.org/10.1145/371578.371593
# ref: https://jsonlines.org/
MOVE_LOG_PATH = "../conversation/object_moves.jsonl"
SCREENSHOT_ROOT = Path("../conversation/screenshots")

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

# SQ1 test tooling, not a mapping design decision.
# Mock mode writes into the SAME file track_tabletop.py writes into,
# using the same schema (timestamp + objects[{id,label,x,y,depth_m}]).
# compute_scene.py doesn't know or care which process wrote it, so
# the mapping and rendering pipeline gets tested unmodified, without
# Record3D/iPhone connected.
SCENE_STATE_PATH = "../tracking/scene_state.json"

# ── Calibration (12 aug) ──────────────────────────────────────────
# participant-triggered from the browser, not a researcher pressing
# keys. this server's job is just message-passing: POST /api/calibrate
# writes a fresh request_id that track_tabletop.py polls for on its
# next frame (see check_calibration_trigger there), GET /api/calibration
# serves back whatever status it's writing (see calibration_status
# there). CALIBRATION_DURATION_FALLBACK is duplicated from
# track_tabletop.py's CALIBRATION_MIN_SECONDS, same reasoning as
# MODIFIER_SCHEMA being duplicated with converse.py, keep in sync by
# hand if the animation timing changes.
CALIBRATION_TRIGGER_PATH = "../tracking/calibration_trigger.json"
CALIBRATION_STATE_PATH = "../tracking/calibration_state.json"
CALIBRATION_DURATION_FALLBACK = 4.5

# ── Assignment store (SQ1: assignable per-instance meaning) ─────
#
# Core interaction model (Ayan, 5 July): an object's detected label
# (cup, bottle) is just a reference handle, not its meaning. Meaning
# is assigned per physical object instance ("the mug is a mountain"),
# generated ONCE, and cached here. Moving the object only updates its
# position downstream, it never re-triggers generation. This file
# persists assignments across server restarts during testing.
ASSIGNMENTS_PATH = "assignments.json"
_assignments_lock = threading.Lock()

# Participant-authored visual scale uses one reserved terminal suffix:
#   <meaning> [,] scale <tiny|miniature|small|big|large|huge>
# Parse it once when both typed and voice routes meet at /api/assign. The
# renderer receives a cached numeric target; qwen never selects scale.
# Project decision, 30 Aug 2026: a fresh 120-case holdout qualified comma or
# whitespace before terminal "scale" after live typed and spoken comma loss
# (observed under Moonshine, retained under Parakeet).
# Terminal "scaled" was rejected because it misread ordinary VFX descriptions.
# ref: https://docs.python.org/3/library/re.html
MARKED_SCALE_TARGETS = {
    "tiny": ("very_small", 0.35),
    "miniature": ("very_small", 0.35),
    "small": ("small", 0.65),
    "big": ("large", 1.80),
    "large": ("large", 1.80),
    "huge": ("very_large", 3.00),
}
MARKED_SCALE_RE = re.compile(
    r"^(?P<generation>.+?)(?:\s*,\s*|\s+)scale\s+"
    r"(?P<modifier>tiny|miniature|small|big|large|huge)\s*[.!?]*\s*$",
    re.IGNORECASE,
)
MARKED_SCALE_FRAGMENT_RE = re.compile(
    r",\s*(?:scale|scaled|make\s+it)\s+\S+"
    r"|(?:^|\s)(?:scale|scaled|make\s+it)\s+"
    r"(?:tiny|miniature|small|big|large|huge)(?=$|[\s,.!?])",
    re.IGNORECASE,
)


def parse_marked_scale(meaning):
    """Return cached scale fields; ambiguous/unsupported syntax is neutral."""
    neutral = {
        "meaning": meaning,
        "generation_meaning": meaning,
        "explicit_scale_intent": "neutral",
        "target_size": 1.0,
        "scale_source": "neutral_default",
    }
    match = MARKED_SCALE_RE.fullmatch(meaning)
    if not match:
        return neutral

    generation_meaning = match.group("generation").strip()
    if (
        not generation_meaning
        or generation_meaning.endswith((";", ":"))
        or MARKED_SCALE_FRAGMENT_RE.search(generation_meaning)
    ):
        return neutral

    intent, target = MARKED_SCALE_TARGETS[match.group("modifier").lower()]
    return {
        "meaning": meaning,
        "generation_meaning": generation_meaning,
        "explicit_scale_intent": intent,
        "target_size": target,
        "scale_source": "participant_marked",
    }

# Step 1 proved the assignment/caching/render-swap mechanics using a
# fake 3-second delay. This selects the real backend for regular
# object generation. "pod": runpod, needs the pod up, fast (~seconds).
# "local": this Mac, no pod needed, much slower (~1-2min+, see
# _generate_mesh_local), added 14 aug once testing without the pod
# needed to actually produce ready objects, not just fail instantly.
# "fake": 3s stub, no real generation, fast frontend iteration.
GENERATION_BACKEND = "pod"

# ── Real generation pipeline (Step 2a) ───────────────────────────
# two-stage: text-to-image (sdxl turbo) then image-to-3d (spar3d).
# 19 july: stage 2 triposr -> sf3d.
# 26 july: stage 2 sf3d -> spar3d. same PNG ("tree"), sf3d melted the
# canopy into a shard, spar3d gave a coherent tree from every angle.
# 27 july, phase4 A: stage 2 (spar3d) moved off the local cpu subprocess
# onto a runpod 4090, resident in vram via wrapper.py. mesh gen went
# 3-4min cpu -> ~2s gpu.
# 27 july, phase4.1: stage 1 (sdxl turbo) moved onto the SAME pod, a
# second resident service on its own port. both stages are now pod
# calls, no local subprocess left in this pipeline at all.
# pod IP:port changes every deploy, update SPAR3D_POD_URL and
# SDXL_POD_URL below whenever the pod is recreated (check RunPod's
# Connect > Direct TCP ports, the external port also shifts on every
# stop/start, not just on a redeploy).
SPAR3D_POD_URL = "http://<pod-public-ip>:<external-port>/generate"
SDXL_POD_URL = "http://<pod-public-ip>:<external-port>/generate"

# ── Local generation (Phase 5A step 3, 14 aug). Same two stages run on
# this Mac instead of the pod, no runpod needed, much slower. Absolute
# paths, machine-specific, confirmed by hand 14 aug via `find`, not
# guessed, same tolerance as the pod urls above needing manual updates.
# stage 1 timing on this exact machine is unmeasured, generate_image.py
# was a "test candidate", never verified end to end before this. stage
# 2 measured at 35-85s on cpu fallback, 19 july, DESIGN_DIARY.md.
PROJECT_ROOT = "~/Documents/UAL/tangible-worlds"
SDXL_LOCAL_SCRIPT = f"{PROJECT_ROOT}/phase2-generation-sdxlturbo/generate_image.py"
# generate_image.py's own docstring, shares the triposr conda env,
# never got its own. confirmed 14 aug, triposr env still installed.
SDXL_LOCAL_PYTHON = "/opt/anaconda3/envs/triposr/bin/python"
SPAR3D_LOCAL_DIR = f"{PROJECT_ROOT}/phase2-generation-spar3d"
SPAR3D_LOCAL_PYTHON = "/opt/anaconda3/envs/spar3d/bin/python"

# local qwen runtime shared by atmosphere translation, prompt shaping,
# and relation naming. LM Studio exposes an OpenAI-compatible chat endpoint.
# ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
# ref: https://huggingface.co/Qwen/Qwen3-8B
LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
LMSTUDIO_MODEL = "qwen/qwen3-8b"

SHAPE_SYSTEM_PROMPT = """You rewrite a single word or short phrase into an image-generation prompt for a text-to-image model. The image will be fed into a single-image 3D reconstruction model, so the image must show ONE solid object, clearly, from a good angle.

Rules:
- Never change the subject. If the input is "tree", the output describes a tree, not a pine tree, not an oak. Do not add species, materials, colors, or details the input did not state.
- Mention the subject noun exactly once.
- Describe a single centered silhouette, front three-quarter hero view, fully visible, occupying roughly two-thirds of the frame, with generous empty margin surrounding it on every side.
- The background is always a seamless solid mid-gray studio background, no matter what color the subject is.
- Describe one camera exposure, one photograph.
- Style: low-poly 3d model, blender render, sharp flat faces, soft studio lighting, one subtle contact shadow, no scene, no ground plane.
- Output ONLY the final prompt text. No explanation, no quotes, no markdown.

Input: tree
Output: one low-poly tree, front three-quarter hero view, centered silhouette, fully visible, occupying roughly two-thirds of the frame with generous empty margin, seamless solid mid-gray studio background, soft lighting, one subtle contact shadow, blender render, sharp flat faces, no scene, no ground

Input: red sports car
Output: one low-poly red sports car, front three-quarter hero view, centered silhouette, entire car visible from front bumper to rear bumper, occupying roughly two-thirds of the frame with generous empty margin, seamless solid mid-gray studio background, soft lighting, one subtle contact shadow, blender render, sharp flat faces, no scene, no ground"""

GENERATED_MESH_DIR = Path("generated_meshes")
GENERATED_MESH_DIR.mkdir(exist_ok=True)

# Python's default mimetypes doesn't know .glb. Registering it
# so the browser gets a sane Content-Type when it fetches a mesh.
http.server.SimpleHTTPRequestHandler.extensions_map[".glb"] = "model/gltf-binary"


def _load_assignments():
    try:
        with open(ASSIGNMENTS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_assignments(data):
    with open(ASSIGNMENTS_PATH, "w") as f:
        json.dump(data, f, indent=2)


_assignments = _load_assignments()

# ── Per-meaning rotation cache ────────────────────────────────────
# 6 July finding, orientation correction belongs to the
# GENERATED ASSET (keyed by meaning/slug), not to a specific object
# instance. Without this, correcting "jeep" once wouldn't help the
# next object also assigned "jeep", making manual correction repeat
# forever instead of being a one-time cost per vocabulary word.
# 19 july note: sf3d auto-orients better than triposr did, so a lot of
# meanings should need no correction at all now. cache stays anyway,
# first-time words can still land off.
MESH_ROTATIONS_PATH = "mesh_rotations.json"


def _load_mesh_rotations():
    try:
        with open(MESH_ROTATIONS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_mesh_rotations(data):
    with open(MESH_ROTATIONS_PATH, "w") as f:
        json.dump(data, f, indent=2)


_mesh_rotations = _load_mesh_rotations()

# ── Relations store (Phase 5A, 13 aug: candidate 3 "interstitial"
# locked). Keyed by a PAIR of meanings, not by object_key, because the
# interstitial thing belongs to the relationship between two physical
# objects, not to either one alone. Reuses _assignments_lock below
# rather than adding a new lock, same as _mesh_rotations does.
RELATIONS_PATH = "relations.json"


def _load_relations():
    try:
        with open(RELATIONS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_relations(data):
    with open(RELATIONS_PATH, "w") as f:
        json.dump(data, f, indent=2)


_relations = _load_relations()


def _slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "asset"


def _pair_slug(meaning_a, meaning_b):
    """Order-independent pair identity. car+house and house+car must
    hit the same cache entry."""
    return "__".join(sorted([_slugify(meaning_a), _slugify(meaning_b)]))


def _mark(object_key, meaning, **fields):
    with _assignments_lock:
        current = _assignments.get(object_key)
        if current and current["meaning"] == meaning:
            current.update(fields)
            _save_assignments(_assignments)


def _fake_generate(object_key, meaning, generation_meaning=None):
    """STUBBED generation. Kept for fast frontend iteration, see
    GENERATION_BACKEND above."""
    time.sleep(3)
    _mark(object_key, meaning, status="ready", generation_stage="complete", cache_hit=False)


def _strip_think(text):
    # qwen3 can use explicit thinking mode; strip any thinking block before
    # parsing or forwarding the model's answer.
    # ref: https://huggingface.co/Qwen/Qwen3-8B
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "<think>" in text:
        text = text.split("<think>")[0]
    return text.strip()


def shape_prompt(meaning):
    """
    rewrite a raw meaning into a stage 1 prompt via qwen3 (LM Studio).
    faithful framing only, never recasts the subject. returns the shaped
    string, or the raw meaning unchanged if the call fails, so generation
    still runs on a bad llm day (degrade, don't break).
    26 july, phase 3.4 job 1. replaces the fixed suffix in
    generate_image.py, the llm owns framing now.
    """
    # ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
    # ref: https://huggingface.co/Qwen/Qwen3-8B
    try:
        resp = requests.post(LMSTUDIO_URL, json={
            "model": LMSTUDIO_MODEL,
            "messages": [
                {"role": "system", "content": SHAPE_SYSTEM_PROMPT},
                {"role": "user", "content": f"{meaning} /no_think"},
            ],
            "temperature": 0.3,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }, timeout=60)  # 27 july, bumped from 30. 9/9 timeouts during the
        # lock-in battery, same batch that hit "no space left on device" on
        # wooden chair, points to disk-full/resource pressure dragging down
        # a normally sub-second call, not a real LM Studio problem. wider
        # margin costs nothing on a healthy machine.
        if resp.status_code != 200:
            print(f"[shape] LM Studio returned {resp.status_code}, using raw meaning")
            return meaning
        shaped = _strip_think(resp.json()["choices"][0]["message"]["content"])
        if not shaped:
            print("[shape] empty after strip, using raw meaning")
            return meaning
        print(f"[shape] '{meaning}' -> '{shaped}'")
        return shaped
    except requests.RequestException as e:
        print(f"[shape] LM Studio unreachable ({e}), using raw meaning")
        return meaning


COMBINE_SYSTEM_PROMPT = """You are given two things a person has placed near each other on a table. Name ONE single physical object that would plausibly sit in the space between them.

Rules:
- Output a short noun phrase, 2-5 words. Nothing else, no explanation, no punctuation beyond what the phrase needs.
- The object must be a single, solid, physically connective thing, something like a road, a fence, a bridge, a path, a wire, a doorway. Not a scene, not a crowd, not a texture like "grass" or "trees", those fail later in the pipeline.
- The object must be solid and touchable. Never light, shadow, fire, smoke, mist, or weather. If a torch, campfire, or candle is involved, name what holds or channels it (a bracket, a stand, a fire pit), never the flame or light itself.
- Never name an environment, area, or scene (a battlefield, a shoreline, a clearing). Name one specific object that would sit within that space instead.
- The object must be a genuinely separate third thing. Never just restate or lightly modify one of the two inputs (if given "a knight" and "a horse", do not answer "a mounted knight", that's the knight, not something new).
- Prefer literal, physical plausibility over metaphor. If the two things share an obvious real-world connector, name that.
- If nothing obvious connects them, invent the most physically reasonable single object anyway. Never refuse, never say "nothing connects these."

- Never answer with a path, trail, or road word that implies a wide landscape shot ("a hiking trail", "a winding road"), those render as full scenes, not single objects, same failure class as the forbidden environment answers above. A bounded marker or structure is fine ("a stone cairn", "a wooden signpost", "a gravel driveway").

Input: a car, a house
Output: a gravel driveway

Input: a mountain, a small tent
Output: a stone cairn

Input: a cave, a torch
Output: an iron torch bracket

Input: a knight, a horse
Output: a wooden hitching post
"""


def combine_prompt(meaning_a, meaning_b):
    """
    Phase 5A, 13 aug: what belongs between two arbitrary meanings.
    Prompt + temperature 0.3 locked after a 90-pair standalone test
    battery (see DESIGN_DIARY.md), not guessed. No pod call, LM
    Studio only. Unlike shape_prompt, returns None on failure rather
    than falling back to a raw value, there is no sensible default
    for an invented third concept, caller marks the relation failed
    instead of faking a result.
    """
    # ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
    # ref: https://huggingface.co/Qwen/Qwen3-8B
    try:
        resp = requests.post(LMSTUDIO_URL, json={
            "model": LMSTUDIO_MODEL,
            "messages": [
                {"role": "system", "content": COMBINE_SYSTEM_PROMPT},
                {"role": "user", "content": f"{meaning_a}, {meaning_b} /no_think"},
            ],
            "temperature": 0.3,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }, timeout=60)
        if resp.status_code != 200:
            print(f"[combine] LM Studio returned {resp.status_code}")
            return None
        invented = _strip_think(resp.json()["choices"][0]["message"]["content"])
        if not invented:
            print("[combine] empty after strip")
            return None
        print(f"[combine] '{meaning_a}' + '{meaning_b}' -> '{invented}'")
        return invented
    except requests.RequestException as e:
        print(f"[combine] LM Studio unreachable: {e}")
        return None


def _generate_mesh_local(meaning, work_dir, stage_callback=None):
    """
    Phase 5A step 3, 14 aug. Same two stages _real_generate runs
    against the pod, run here as local subprocesses instead, no
    runpod needed. Factored out as its own function so it can be
    reused for regular object generation later without duplicating
    the subprocess logic, though only the interstitial path
    (_generate_relation below) actually calls it right now, regular
    per-object assignment is untouched, still pod-only.

    Writes work_dir/source.png and work_dir/0/mesh.glb on success.
    Returns True/False. Doesn't touch _relations, _assignments, or
    any cache dict, that's the caller's job, same division of labour
    as _real_generate.
    """
    # ref: https://huggingface.co/stabilityai/sdxl-turbo
    # ref: https://github.com/Stability-AI/stable-point-aware-3d/blob/main/run.py
    work_dir.mkdir(parents=True, exist_ok=True)
    # 14 aug, caught on first real test. stage 2 below runs with
    # cwd=SPAR3D_LOCAL_DIR, a different directory than serve.py's own,
    # so a relative work_dir resolves against the wrong base there and
    # the image "doesn't exist" even though stage 1 wrote it fine.
    # absolute makes it unambiguous regardless of which subprocess's
    # cwd is active.
    work_dir = work_dir.absolute()
    image_path = work_dir / "source.png"

    # 14 aug, caught on first real test. this was handing the raw
    # meaning straight to sdxl, skipping shape_prompt entirely, unlike
    # the pod path below which always shapes first. same framing bug
    # class as the pre-26-july fixed-suffix problem, just reintroduced
    # in a new code path. fixed here, not worked around.
    shaped = shape_prompt(meaning)

    # Participant-facing status mirrors actual pipeline boundaries. Relations
    # reuse this function without a callback, so their behaviour is unchanged.
    # project decision: 1 Sep 2026.
    if stage_callback:
        stage_callback("image")

    print(f"[local] stage 1: generating image for '{meaning}'")
    t0 = time.time()
    try:
        result = subprocess.run(
            [SDXL_LOCAL_PYTHON, SDXL_LOCAL_SCRIPT, shaped, str(image_path)],
            capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        print(f"[local] stage 1 TIMED OUT for '{meaning}'")
        return False
    print(f"[local] stage 1 took {time.time() - t0:.1f}s")
    if result.returncode != 0 or not image_path.exists():
        print(f"[local] stage 1 FAILED for '{meaning}' (exit {result.returncode}):")
        print(result.stderr[-1500:])
        return False

    if stage_callback:
        stage_callback("mesh")

    print(f"[local] stage 2: reconstructing mesh for '{meaning}'")
    t1 = time.time()
    try:
        # --device cpu forced: mps ooms on this model class at this
        # model size, same finding sf3d and spar3d both hit in july,
        # DESIGN_DIARY.md 6 july and 26 july. no --no-remove-bg, same
        # run.py defaults the pod wrapper already relies on.
        result = subprocess.run(
            [SPAR3D_LOCAL_PYTHON, "run.py", str(image_path),
             "--device", "cpu", "--output-dir", str(work_dir)],
            cwd=SPAR3D_LOCAL_DIR,
            capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        print(f"[local] stage 2 TIMED OUT for '{meaning}'")
        return False
    print(f"[local] stage 2 took {time.time() - t1:.1f}s")
    if result.returncode != 0:
        print(f"[local] stage 2 FAILED for '{meaning}' (exit {result.returncode}):")
        print(result.stderr[-1500:])
        return False

    glb_files = list(work_dir.rglob("*.glb"))
    if not glb_files:
        print(f"[local] stage 2 produced no .glb for '{meaning}'")
        return False

    print(f"[local] done: '{meaning}' -> {glb_files[0]}")
    return True

def _generate_mesh_pod(meaning, work_dir):
    """
    run the same two-stage generation pipeline on runpod:
    sdxl turbo -> spar3d.

    writes work_dir/source.png and work_dir/0/mesh.glb.
    returns true/false and does not touch assignments or relations.

    # 15 aug. shared pod helper so regular objects and
    # interstitial objects can use the same generation backend.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    work_dir = work_dir.absolute()
    image_path = work_dir / "source.png"

    shaped = shape_prompt(meaning)

    print(f"[pod] stage 1: generating image for '{meaning}'")
    t0 = time.time()

    try:
        resp = requests.post(
            SDXL_POD_URL,
            json={"prompt": shaped},
            timeout=60,
        )
    except requests.RequestException as e:
        print(f"[pod] stage 1 unreachable for '{meaning}': {e}")
        return False

    if resp.status_code != 200:
        print(
            f"[pod] stage 1 error {resp.status_code} "
            f"for '{meaning}':\n{resp.text[:1500]}"
        )
        return False

    image_path.write_bytes(resp.content)
    print(f"[pod] stage 1 took {time.time() - t0:.1f}s")

    print(f"[pod] stage 2: reconstructing mesh for '{meaning}'")
    t1 = time.time()

    try:
        resp = requests.post(
            SPAR3D_POD_URL,
            data=image_path.read_bytes(),
            headers={"Content-Type": "application/octet-stream"},
            timeout=120,
        )
    except requests.RequestException as e:
        print(f"[pod] stage 2 unreachable for '{meaning}': {e}")
        return False

    if resp.status_code != 200:
        print(
            f"[pod] stage 2 error {resp.status_code} "
            f"for '{meaning}':\n{resp.text[:1500]}"
        )
        return False

    out_dir = work_dir / "0"
    out_dir.mkdir(parents=True, exist_ok=True)
    mesh_path = out_dir / "mesh.glb"
    mesh_path.write_bytes(resp.content)

    if not mesh_path.exists() or mesh_path.stat().st_size == 0:
        print(f"[pod] stage 2 produced no mesh for '{meaning}'")
        return False

    print(f"[pod] stage 2 took {time.time() - t1:.1f}s")
    print(f"[pod] done: '{meaning}' -> {mesh_path}")
    return True

def _generate_relation(pair_slug, meaning_a, meaning_b):
    """
    Phase 5A step 3: invents what belongs between two meanings via
    qwen3 (step 2, unchanged), then generates a real mesh for it
    locally (step 3, new). Same GENERATED_MESH_DIR cache as regular
    objects, keyed by the invented word's own slug, so if the same
    phrase ever comes up again, object or relation, it's an instant
    cache hit either way.
    """
    invented = combine_prompt(meaning_a, meaning_b)
    if invented is None:
        with _assignments_lock:
            current = _relations.get(pair_slug)
            if current:
                current["status"] = "failed"
                _save_relations(_relations)
        return

    slug = _slugify(invented)
    cached = GENERATED_MESH_DIR / f"{slug}.glb"

    if cached.exists():
        print(f"[relate] cache hit for invented meaning '{invented}'")
    else:
        work_dir = GENERATED_MESH_DIR / slug
        if not _generate_mesh_pod(invented, work_dir):
            with _assignments_lock:
                current = _relations.get(pair_slug)
                if current:
                    current["status"] = "failed"
                    _save_relations(_relations)
            return
        glb_files = list(work_dir.rglob("*.glb"))
        shutil.copy(glb_files[0], cached)

    # same mtime-versioning as _real_generate below, a regenerated
    # file needs a new url or the browser's gltfCache never re-fetches.
    mesh_url = f"/{GENERATED_MESH_DIR.name}/{cached.name}?v={int(cached.stat().st_mtime)}"
    with _assignments_lock:
        current = _relations.get(pair_slug)
        if current:
            current["meaning"] = invented
            current["status"] = "ready"
            current["mesh_url"] = mesh_url
            _save_relations(_relations)


def _real_generate(object_key, meaning, generation_meaning=None):
    """
    Runs the real two-stage pipeline, both stages now pod calls:
    text-to-image (sdxl turbo, pod port 7862) then image-to-3D
    (spar3d, pod port 7860). Caches by meaning, not by object, so
    two different objects assigned the same meaning share one generated
    asset instead of generating it twice.
    """
    generation_meaning = generation_meaning or meaning
    slug = _slugify(generation_meaning)
    cached = GENERATED_MESH_DIR / f"{slug}.glb"

    if cached.exists():
        print(f"[generate] cache hit for '{meaning}'")
        # 27 july. append mtime as a version param, otherwise the
        # browser's gltfCache (keyed on this exact url string) never
        # re-fetches a regenerated mesh, even after the cache file on
        # disk is deleted and rebuilt. same url, stale mesh forever,
        # confirmed on the red pickup truck retest. mtime changes only
        # when the file actually changes, so a real cache hit (same
        # content) still gets the same url, no needless reloads.
        mesh_url = f"/{GENERATED_MESH_DIR.name}/{cached.name}?v={int(cached.stat().st_mtime)}"
        _mark(object_key, meaning, status="ready", generation_stage="complete", cache_hit=True,
              mesh_url=mesh_url,
              rotation=dict(_mesh_rotations.get(slug, {"x": 0, "y": 0, "z": 0})))
        return

    work_dir = GENERATED_MESH_DIR / slug
    work_dir.mkdir(parents=True, exist_ok=True)
    image_path = work_dir / "source.png"

    print(f"[generate] stage 1: POSTing to pod for '{meaning}'")
    t0 = time.time()
    shaped = shape_prompt(generation_meaning)  # control suffix never reaches generation.
    print(f"[generate] shape_prompt took {time.time() - t0:.1f}s")
    _mark(object_key, meaning, generation_stage="image")
    # 27 july, phase4.1. stage 1 moved off local cpu subprocess to
    # the same runpod 4090, sdxl turbo resident on port 7862 (7861 was
    # taken pod-wide by runpod's own nginx). pod url changes every
    # deploy, update alongside SPAR3D_POD_URL above.
    t1 = time.time()
    try:
        resp = requests.post(SDXL_POD_URL, json={"prompt": shaped}, timeout=60)
    except requests.RequestException as e:
        print(f"[generate] stage 1 POD UNREACHABLE for '{meaning}': {e}")
        _mark(object_key, meaning, status="failed", generation_stage="failed")
        return

    if resp.status_code != 200:
        print(f"[generate] stage 1 POD ERROR {resp.status_code} for '{meaning}':\n{resp.text[:1500]}")
        _mark(object_key, meaning, status="failed", generation_stage="failed")
        return

    image_path.write_bytes(resp.content)
    print(f"[generate] SDXL pod call took {time.time() - t1:.1f}s")

    _mark(object_key, meaning, generation_stage="mesh")
    print(f"[generate] stage 2: POSTing to pod for '{meaning}'")
    # 27 july, phase4 A. stage 2 moved off local cpu subprocess to
    # the runpod 4090 wrapper (spar3d resident in vram, ~2s/gen vs 3-4min
    # cpu). i POST source.png raw, get mesh.glb bytes back, write them to
    # <work_dir>/0/mesh.glb so the existing rglob/copy path below is
    # untouched. pod does bg-removal + foreground crop + run_image with the
    # same run.py defaults, verified by hand against backpack source.png.
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                SPAR3D_POD_URL,
                data=f.read(),
                headers={"Content-Type": "application/octet-stream"},
                timeout=120,
            )
    except requests.RequestException as e:
        print(f"[generate] stage 2 POD UNREACHABLE for '{meaning}': {e}")
        _mark(object_key, meaning, status="failed", generation_stage="failed")
        return

    if resp.status_code != 200:
        print(f"[generate] stage 2 POD ERROR {resp.status_code} for '{meaning}':\n{resp.text[:1500]}")
        _mark(object_key, meaning, status="failed", generation_stage="failed")
        return

    # write returned glb where the old subprocess would have, so the
    # rglob("*.glb") below still finds it with zero other changes.
    out_dir = work_dir / "0"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mesh.glb").write_bytes(resp.content)

    glb_files = list(work_dir.rglob("*.glb"))
    if not glb_files:
        print(f"[generate] stage 2 produced no .glb for '{meaning}'")
        _mark(object_key, meaning, status="failed", generation_stage="failed")
        return

    shutil.copy(glb_files[0], cached)
    # 27 july, same mtime-versioning as the cache-hit branch above.
    # this is the path that actually mattered for the retest: a deleted
    # and regenerated file needs a new url or the browser's gltfCache
    # never asks the server for it.
    mesh_url = f"/{GENERATED_MESH_DIR.name}/{cached.name}?v={int(cached.stat().st_mtime)}"
    _mark(object_key, meaning, status="ready", generation_stage="complete", cache_hit=False, mesh_url=mesh_url,
          rotation=dict(_mesh_rotations.get(slug, {"x": 0, "y": 0, "z": 0})))
    print(f"[generate] done: '{meaning}' -> {mesh_url}")


def _local_generate_object(object_key, meaning, generation_meaning=None):
    """
    Local backend for regular per-object generation. 14 aug, added
    alongside the interstitial local path, after discovering assigning
    any NEW (uncached) meaning was impossible with the pod down, only
    already-cached meanings could ever reach "ready". Mirrors
    _real_generate's cache check and _mark calls exactly, but runs
    both stages on this Mac via _generate_mesh_local. _real_generate
    itself is completely untouched, this is a fully separate function,
    zero risk to the proven pod path.
    """
    generation_meaning = generation_meaning or meaning
    slug = _slugify(generation_meaning)
    cached = GENERATED_MESH_DIR / f"{slug}.glb"

    if cached.exists():
        print(f"[local] cache hit for '{meaning}'")
        mesh_url = f"/{GENERATED_MESH_DIR.name}/{cached.name}?v={int(cached.stat().st_mtime)}"
        _mark(object_key, meaning, status="ready", generation_stage="complete", cache_hit=True, mesh_url=mesh_url,
              rotation=dict(_mesh_rotations.get(slug, {"x": 0, "y": 0, "z": 0})))
        return

    work_dir = GENERATED_MESH_DIR / slug

    def mark_stage(stage):
        _mark(object_key, meaning, generation_stage=stage)

    if not _generate_mesh_local(generation_meaning, work_dir, mark_stage):
        _mark(object_key, meaning, status="failed", generation_stage="failed")
        return

    glb_files = list(work_dir.rglob("*.glb"))
    shutil.copy(glb_files[0], cached)
    mesh_url = f"/{GENERATED_MESH_DIR.name}/{cached.name}?v={int(cached.stat().st_mtime)}"
    _mark(object_key, meaning, status="ready", generation_stage="complete", cache_hit=False, mesh_url=mesh_url,
          rotation=dict(_mesh_rotations.get(slug, {"x": 0, "y": 0, "z": 0})))
    print(f"[local] done: '{meaning}' -> {mesh_url}")


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves static files + API endpoints for scene and modifiers."""

    def do_GET(self):
        # The study always enters through the participant onboarding page.
        # The live renderer remains available explicitly at /index.html.
        path_only = self.path.split("?", 1)[0]
        if path_only == "/":
            original_path = self.path
            self.path = "/welcome.html"
            try:
                return super().do_GET()
            finally:
                self.path = original_path

        # Scene description endpoint
        if self.path == "/api/scene":
            self._serve_json(SCENE_DESC_PATH, fallback={
                "objects": [], "relationships": [], "clusters": [], "layout": {}
            })
            return

        # Scene modifiers endpoint
        if self.path == "/api/modifiers":
            self._serve_json(MODIFIERS_PATH, fallback={})
            return

        # Assignment store endpoint (what does each object mean, and
        # is its generation ready yet)
        if self.path == "/api/assignments":
            with _assignments_lock:
                data = json.dumps(_assignments)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode())
            return

        # Relations store endpoint (Phase 5A). What's generating or
        # ready between which meaning-pairs.
        if self.path == "/api/relations":
            with _assignments_lock:
                data = json.dumps(_relations)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode())
            return

        # Calibration status (12 aug). Polled by the browser while the
        # scan animation plays. Fallback matches the shape
        # track_tabletop.py's calibration_status() actually writes,
        # so the browser never has to special-case "file doesn't exist
        # yet" (e.g. tracker hasn't started) vs "status is idle".
        if self.path == "/api/calibration":
            self._serve_json(CALIBRATION_STATE_PATH, fallback={
                "status": "idle", "elapsed": 0,
                "duration": CALIBRATION_DURATION_FALLBACK,
                "noise_mm": 0, "thresh_mm": 0,
            })
            return

        # Everything else: serve static files (index.html etc)
        return super().do_GET()

    def do_POST(self):
        # i relay tts through this server because pocket tts v2.1.0 does not
        # allow http://localhost:8080 in its cors origins. the browser can then
        # use the same origin as the rest of tangible worlds.
        # academic ref: rouard et al., "continuous audio language models", iclr 2026.
        # https://arxiv.org/abs/2509.06926
        # ref: https://github.com/kyutai-labs/pocket-tts/blob/v2.1.0/pocket_tts/main.py#L43-L53
        # ref: https://github.com/kyutai-labs/pocket-tts/blob/v2.1.0/pocket_tts/main.py#L111-L166
        if self.path == "/api/tts":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                text = str(body.get("text", "")).strip()
            except json.JSONDecodeError:
                text = ""

            if not text:
                self.send_response(400)
                self.end_headers()
                return

            # project tuning: i use 15s to leave headroom over the sub-second local test.
            try:
                resp = requests.post(
                    POCKET_TTS_URL,
                    data={"text": text, "voice_url": POCKET_TTS_VOICE},
                    timeout=15,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"[tts] pocket tts error: {e}")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "ok": False, "error": "pocket tts unreachable"
                }).encode())
                return

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(resp.content)))
            self.end_headers()
            self.wfile.write(resp.content)
            return

        # Mock scene endpoint (Phase 1 test harness, see SQ1 notes).
        # Lets index.html act as a stand-in for track_tabletop.py so
        # the mapping + rendering pipeline can be exercised without
        # Record3D/iPhone connected. Writes the exact scene_state.json
        # schema the real tracker produces.
        # Ref: Python http.server request body handling
        # https://docs.python.org/3/library/http.server.html
        if self.path == "/api/mock_scene":
            length = int(self.headers.get("Content-Length", 0))
            try:
                raw = self.rfile.read(length) if length else b"{}"
                body = json.loads(raw)
                objects = body.get("objects", [])
            except json.JSONDecodeError:
                objects = []

            state = {"timestamp": time.time(), "objects": objects}
            with open(SCENE_STATE_PATH, "w") as f:
                json.dump(state, f, indent=2)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(
                json.dumps({"ok": True, "count": len(objects)}).encode()
            )
            return

        # Calibration trigger (12 aug). Participant clicks a button in
        # the browser, this writes a fresh request_id that
        # track_tabletop.py picks up on its next frame. No body
        # needed, a NEW id in the file is the whole signal, see
        # check_calibration_trigger there for why that's idempotent
        # against being read multiple times before the tracker acts.
        if self.path == "/api/calibrate":
            request_id = time.time()
            try:
                with open(CALIBRATION_TRIGGER_PATH, "w") as f:
                    json.dump({"request_id": request_id}, f)
            except OSError as e:
                print(f"[calibrate] failed to write trigger: {e}")
                self.send_response(500)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "request_id": request_id}).encode())
            return

        # Reset scene to default (study infra, 19 july). Clears
        # assignments, mood modifiers, and mock objects so a participant
        # starts on a clean table. Does NOT touch generated_meshes/ or
        # mesh_rotations.json, re-assigning a known meaning stays instant.
        if self.path == "/api/reset":
            with _assignments_lock:
                _assignments.clear()
                _save_assignments(_assignments)
                # 14 aug. /api/reset predates the relations store
                # (19 july vs phase 5a), so it never cleared it, leaving
                # stale fake-era "ready" records with no meaning behind
                # them alive across a reset. same lock, same clear.
                _relations.clear()
                _save_relations(_relations)

            # mood back to plain day: wipe the modifiers file the
            # atmosphere poll reads. empty {} -> applyModifiers no-ops
            # and the frontend falls back to its default lighting.
            try:
                with open(MODIFIERS_PATH, "w") as f:
                    json.dump({}, f)
            except OSError:
                pass

            # clear mock objects too, empty table for the next run.
            state = {"timestamp": time.time(), "objects": []}
            with open(SCENE_STATE_PATH, "w") as f:
                json.dump(state, f, indent=2)
            # also wipe the mapping output the browser actually reads
            # from (/api/scene serves this, not scene_state.json). without
            # this, stale computed objects survive a reset. 19 july.
            empty_scene = {"timestamp": 0, "objects": [], "relationships": [],
                           "clusters": [], "layout": {}}
            try:
                with open(SCENE_DESC_PATH, "w") as f:
                    json.dump(empty_scene, f, indent=2)
            except OSError:
                pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
            return

        # live browser atmosphere translation. reads scene context and the
        # current modifier state, asks qwen3-8b for the complete semantic
        # modifier object, writes scene_modifiers.json, then the browser's
        # /api/modifiers poll applies it.
        # ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
        # ref: https://huggingface.co/Qwen/Qwen3-8B
        # Note: this call blocks while the model thinks (a few seconds),
        # and the server is single-threaded, so other polls wait during
        # that window. Fine for a single-user study session, watch it.
        if self.path == "/api/converse":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                body = {}

            command = str(body.get("command", "")).strip()
            if not command:
                self.send_response(400)
                self.end_headers()
                return

            # scene context for the LLM, same summary converse.py builds
            scene_context = "No scene data available."
            try:
                with open(SCENE_DESC_PATH) as f:
                    sd = json.load(f)
                objs = sd.get("objects", [])
                if objs:
                    labels = [o["label"] for o in objs]
                    layout = sd.get("layout", {})
                    scene_context = (
                        f"Objects on table: {', '.join(labels)}. "
                        f"Spread: {layout.get('spread', 0):.2f}. "
                        f"Clusters: {len(sd.get('clusters', []))}."
                    )
                else:
                    scene_context = "No objects on the table."
            except (FileNotFoundError, json.JSONDecodeError):
                pass

            # preserve the current atmosphere between conversational edits.
            # whitelist the final phase 5e schema so obsolete pre-5e fields
            # cannot survive in scene_modifiers.json during migration.
            try:
                with open(MODIFIERS_PATH) as f:
                    saved_modifiers = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                saved_modifiers = {}

            current_modifiers = dict(MODIFIER_SCHEMA)
            current_modifiers.update({
                key: value for key, value in saved_modifiers.items()
                if key in MODIFIER_SCHEMA and value is not None
            })

            prompt = (f"Current scene objects: {scene_context}\n"
                      f"Current modifiers: {json.dumps(current_modifiers)}\n"
                      f"User request: {command}\n"
                      f"Return the modifier JSON:")

            # measure only the qwen request, not browser, stt or tts time.
            # perf_counter is monotonic and intended for short elapsed durations.
            # academic ref: hilbert & redmiles, acm computing surveys 32(4), 2000.
            # https://doi.org/10.1145/371578.371593
            # ref: https://docs.python.org/3/library/time.html#time.perf_counter
            model_started = time.perf_counter()
            try:
                # same request shape qualified in the 106-call phase 5e test.
                # ref: https://lmstudio.ai/docs/developer/openai-compat/chat-completions
                # ref: https://huggingface.co/Qwen/Qwen3-8B
                resp = requests.post(LMSTUDIO_URL, json={
                    "model": LMSTUDIO_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"{prompt} /no_think"},
                    ],
                    "temperature": 0.3,
                    "stream": False,
                    "chat_template_kwargs": {"enable_thinking": False},
                }, timeout=60)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"[converse] LM Studio error: {e}")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "LM Studio unreachable"}).encode())
                return

            model_latency_s = time.perf_counter() - model_started

            # strip qwen3 thinking text before JSON parsing.
            # ref: https://huggingface.co/Qwen/Qwen3-8B
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            raw = _strip_think(raw)
            raw = raw.replace("```json", "").replace("```", "").strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[converse] bad json from model: {raw[:200]}")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "bad json, try again"}).encode())
                return

            # preserve unrelated current values, but only accept keys from the
            # final 12-field phase 5e schema and ignore nulls.
            merged = dict(current_modifiers)
            merged.update({
                key: value for key, value in parsed.items()
                if key in MODIFIER_SCHEMA and value is not None
            })

            with open(MODIFIERS_PATH, "w") as f:
                json.dump(merged, f, indent=2)

            # keep study input metadata on the same accepted interaction event.
            # existing log fields stay unchanged; speech-only fields are null/empty
            # for typed turns. rejected voice transcripts arrive in attempts.
            # academic ref: hilbert & redmiles, acm computing surveys 32(4), 2000.
            # https://doi.org/10.1145/371578.371593
            log_timestamp = time.time()
            try:
                try:
                    with open(CONV_LOG_PATH) as f:
                        log = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    log = []
                log.append({
                    "timestamp": log_timestamp,
                    "command": command,
                    "scene_context": scene_context,
                    "modifiers_applied": merged,
                    "participant_id": body.get("participant_id"),
                    "condition": body.get("condition"),
                    "input_modality": body.get("input_modality"),
                    "raw_transcript": body.get("raw_transcript"),
                    "final_text": command,
                    "transcript_attempts": body.get("transcript_attempts", []),
                    "retry_count": body.get("retry_count", 0),
                    "confirmation_transcript": body.get("confirmation_transcript"),
                    "stt_s": body.get("stt_s"),
                    "model_latency_s": model_latency_s,
                    # browser time from command finished to post, plus qwen time.
                    # this is the number that makes typed and spoken comparable,
                    # since only the voice condition pays for confirmation.
                    "pre_model_s": body.get("pre_model_s"),
                    "total_command_s": None if body.get("pre_model_s") is None
                        else round(body["pre_model_s"] + model_latency_s, 3),
                })
                with open(CONV_LOG_PATH, "w") as f:
                    json.dump(log, f, indent=2)
            except OSError:
                pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "modifiers": merged, "log_timestamp": log_timestamp}).encode())
            return
        
        # Scene screenshots, batched by the browser so large JPEG posts do not
        # compete with every polling request. Each participant folder also gets a
        # jsonl index whose timestamp exactly matches the JPEG filename prefix.
        if self.path == "/api/screenshot":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                screenshots = body.get("screenshots", [])
            except json.JSONDecodeError:
                screenshots = []

            written = 0
            failed = 0
            if isinstance(screenshots, list):
                for shot in screenshots:
                    try:
                        participant = str(shot.get("participant_id") or "UNSET")
                        participant = re.sub(r"[^A-Za-z0-9_-]+", "_", participant)
                        timestamp = str(shot.get("timestamp") or "").strip()
                        reason = re.sub(r"[^A-Za-z0-9_-]+", "_",
                                        str(shot.get("reason") or "scene"))
                        image = str(shot.get("image") or "")
                        if not timestamp or not image.startswith("data:image/jpeg;base64,"):
                            failed += 1
                            continue

                        folder = SCREENSHOT_ROOT / participant
                        folder.mkdir(parents=True, exist_ok=True)
                        filename = f"{timestamp}_{reason}.jpg"
                        path = folder / filename
                        if path.exists():
                            continue
                        raw = base64.b64decode(image.split(",", 1)[1], validate=True)
                        path.write_bytes(raw)

                        entry = {k: v for k, v in shot.items() if k != "image"}
                        entry["filename"] = filename
                        with open(folder / "screenshots.jsonl", "a") as f:
                            f.write(json.dumps(entry) + "\n")
                        written += 1
                    except (OSError, ValueError, base64.binascii.Error) as e:
                        failed += 1
                        print(f"[screenshot] failed to write one image: {e}")

            self.send_response(500 if failed else 200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": failed == 0, "written": written, "failed": failed}).encode())
            return

        # object-move events, batched by the browser once a second. the browser
        # is the only place that knows participant_id and condition, so it owns
        # detection and this only appends. the single-threaded HTTPServer
        # serialises requests, so no lock is needed here.
        # academic ref: hilbert & redmiles, acm computing surveys 32(4), 2000.
        # https://doi.org/10.1145/371578.371593
        if self.path == "/api/move_log":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                events = body.get("events", [])
            except json.JSONDecodeError:
                events = []

            written = 0
            failed = 0
            if isinstance(events, list) and events:
                try:
                    with open(MOVE_LOG_PATH, "a") as f:
                        for event in events:
                            f.write(json.dumps(event) + "\n")
                            written += 1
                except OSError as e:
                    failed = len(events) - written
                    print(f"[move_log] failed to append: {e}")

            self.send_response(500 if failed else 200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": failed == 0, "written": written, "failed": failed}).encode())
            return

        # Assignment endpoint. Body: {"object_key": "4", "meaning": "a mountain"}
        # 17 aug 2026. object_key is the numeric tracker id as a
        # string. it used to be "label-id"; the yolo label flipped frame
        # to frame and orphaned assignments. serve.py treats this as an
        # opaque string and does not parse it, so no logic changed here.
        # Reassignment is allowed by default (Ayan: undecided, defaulting
        # to allow since it's the simpler behaviour and easy to lock
        # down later if the study protocol needs assignments frozen).
        if self.path == "/api/assign":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                object_key = str(body.get("object_key", "")).strip()
                meaning = str(body.get("meaning", "")).strip()
            except json.JSONDecodeError:
                object_key, meaning = "", ""

            if not object_key or not meaning:
                self.send_response(400)
                self.end_headers()
                return

            with _assignments_lock:
                existing = _assignments.get(object_key)
                if existing and existing["meaning"] == meaning:
                    # Same meaning already assigned or in progress: no-op.
                    record = existing
                else:
                    # New assignment, or a changed one: (re)generate.
                    record = {
                        **parse_marked_scale(meaning),
                        "status": "generating",
                        "generation_stage": "preparing",
                        "cache_hit": False,
                        "rotation": {"x": 0, "y": 0, "z": 0},
                    }
                    _assignments[object_key] = record
                    _save_assignments(_assignments)
                    if GENERATION_BACKEND == "local":
                        target = _local_generate_object
                    elif GENERATION_BACKEND == "fake":
                        target = _fake_generate
                    else:
                        target = _real_generate
                    threading.Thread(
                        target=target,
                        args=(object_key, meaning, record["generation_meaning"]),
                        daemon=True,
                    ).start()

            # i keep assignments in the same study timeline because they are
            # language interactions too. generation continues asynchronously, so
            # why model_latency_s and total_command_s are not claimed here.
            # academic ref: hilbert & redmiles, acm computing surveys 32(4), 2000.
            # https://doi.org/10.1145/371578.371593
            final_text = str(body.get("final_text") or
                             f"object {object_key} is {meaning}").strip()
            log_timestamp = time.time()
            try:
                try:
                    with open(CONV_LOG_PATH) as f:
                        log = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    log = []
                log.append({
                    "timestamp": log_timestamp,
                    "command": final_text,
                    "scene_context": None,
                    "modifiers_applied": None,
                    "participant_id": body.get("participant_id"),
                    "condition": body.get("condition"),
                    "input_modality": body.get("input_modality"),
                    "raw_transcript": body.get("raw_transcript"),
                    "final_text": final_text,
                    "transcript_attempts": body.get("transcript_attempts", []),
                    "retry_count": body.get("retry_count", 0),
                    "confirmation_transcript": body.get("confirmation_transcript"),
                    "stt_s": body.get("stt_s"),
                    "model_latency_s": None,
                    "pre_model_s": body.get("pre_model_s"),
                    "total_command_s": None,
                    "interaction_type": "assignment",
                    "object_key": object_key,
                    "meaning": meaning,
                })
                with open(CONV_LOG_PATH, "w") as f:
                    json.dump(log, f, indent=2)
            except OSError:
                pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({**record, "log_timestamp": log_timestamp}).encode())
            return

        # Rotation correction endpoint (5-6 July finding: generated
        # meshes have no canonical orientation). Body:
        # {"object_key": "...", "axis": "x"|"y"|"z", "delta": 90}
        if self.path == "/api/rotate":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                object_key = str(body.get("object_key", "")).strip()
                axis = str(body.get("axis", "")).strip().lower()
                delta = float(body.get("delta", 0))
            except (json.JSONDecodeError, ValueError):
                object_key, axis, delta = "", "", 0

            if not object_key or axis not in ("x", "y", "z"):
                self.send_response(400)
                self.end_headers()
                return

            with _assignments_lock:
                record = _assignments.get(object_key)
                if record:
                    record.setdefault("rotation", {"x": 0, "y": 0, "z": 0})
                    record["rotation"][axis] = (record["rotation"][axis] + delta) % 360
                    _save_assignments(_assignments)

                    # 6 July fix. Save into the shared per-meaning
                    # store too, so the NEXT object assigned this same
                    # meaning inherits the correction instead of
                    # starting back at zero.
                    slug = _slugify(record.get("generation_meaning", record["meaning"]))
                    _mesh_rotations[slug] = dict(record["rotation"])
                    _save_mesh_rotations(_mesh_rotations)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(record or {}).encode())
            return

        # Interstitial relation trigger (Phase 5A step 1, fake gen
        # only, no pod call yet). Body:
        # {"object_key_a": "...", "object_key_b": "..."}.
        # Looks up each object's MEANING here, server-side, not from
        # whatever the browser's local assignments cache says, so a
        # stale poll can't desync the pair from what's actually assigned.
        if self.path == "/api/relate":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                key_a = str(body.get("object_key_a", "")).strip()
                key_b = str(body.get("object_key_b", "")).strip()
            except json.JSONDecodeError:
                key_a, key_b = "", ""

            if not key_a or not key_b:
                self.send_response(400)
                self.end_headers()
                return

            with _assignments_lock:
                rec_a = _assignments.get(key_a)
                rec_b = _assignments.get(key_b)

                if not rec_a or not rec_b or rec_a["status"] != "ready" or rec_b["status"] != "ready":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "reason": "not both ready"}).encode())
                    return

                meaning_a = rec_a.get("generation_meaning", rec_a["meaning"])
                meaning_b = rec_b.get("generation_meaning", rec_b["meaning"])
                pair_slug = _pair_slug(meaning_a, meaning_b)
                existing = _relations.get(pair_slug)
                if existing:
                    record = existing
                else:
                    record = {"status": "generating"}
                    _relations[pair_slug] = record
                    _save_relations(_relations)
                    threading.Thread(
                        target=_generate_relation,
                        args=(pair_slug, meaning_a, meaning_b),
                        daemon=True,
                    ).start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "pair_slug": pair_slug, **record}).encode())
            return

        self.send_response(404)
        self.end_headers()

    def _serve_json(self, filepath, fallback):
        """Read a JSON file and serve it, with a fallback if missing."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            with open(filepath, "r") as f:
                data = f.read()
        except FileNotFoundError:
            data = json.dumps(fallback)

        self.wfile.write(data.encode())

    # Suppress request logging to keep terminal clean
    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print(f"[*] Rendering server at http://localhost:{PORT}")
    print(f"[*] Scene from: {SCENE_DESC_PATH}")
    print(f"[*] Modifiers from: {MODIFIERS_PATH}")
    server = http.server.HTTPServer(("", PORT), Handler)
    server.serve_forever()