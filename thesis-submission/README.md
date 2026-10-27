# Tangible Worlds

Physical arrangement as spatial prompting for generative 3D environments.

MSc Applied Machine Learning for Creatives, UAL Creative Computing Institute,
September 2026. Muhammad Ayan Achakzai. Supervisor Terence Broad.

This repository holds the system described in my dissertation, the scripts and
data behind the numbers in Section 5, the prototypes I tested and did not
adopt, and the session records the report quotes.

## What it does

Ordinary props sit on a table. An overhead iPhone streams LiDAR depth to the
laptop. The system fits a plane to the empty table and treats anything above
it as a tracked object with a persistent id. The sensing layer records
geometry and nothing else. It never decides what a prop means.

Meaning is assigned separately, by typing or speaking. A local Qwen3-8B shapes
that meaning into a prompt, SDXL Turbo generates a source image, and SPAR3D
reconstructs it as a mesh. The mesh is cached against the meaning, so moving a
prop moves its object without generating it again.

Hands set spatial structure. Words set semantics.

## Folders

`system/` is the artefact. It is what Section 4 describes and what runs.

`evaluation/` holds the scripts and frozen data behind the numbers in Section
5. Tracking evidence is in `evaluation/tracking/`, the scale studies in
`evaluation/scale/`, the speech work in `evaluation/speech/`, the generation
battery in `evaluation/generation/`, and the atmosphere tests in
`evaluation/atmosphere/`.

`prototypes/` holds directions I built and did not adopt. The tracker variants
are in `prototypes/tracker_variants/`, terrain in `prototypes/terrain/` and
`prototypes/mesa/`, and the depth probe from Section 5.1.2 in
`prototypes/depth_probe/`.

`logs/` holds the session records the report quotes, including the frozen
tracker session of 1,039 seconds and 26,503 frames.

Two things to know when matching files to the text. Section 5.1.6 names four
low-profile alternatives but there are three scripts here, because the RC5RGB
diagnostic covers two of them, static RGB background subtraction and RGB-depth
fusion. And `evaluation/scale/` holds six frozen studies rather than one,
because the explicit grammar and the voice alias were qualified separately.

## Running it

I verified the system in this folder structure on 12 September 2026: the server, mapping layer and renderer all resolve their paths and a two-object mock scene renders with its proximity relation.

Six processes, each in its own terminal, all left running.

First, LM Studio serving `qwen/qwen3-8b` on port 1234. `serve.py` calls
`http://127.0.0.1:1234/v1/chat/completions`. I ran the `@4bit` MLX variant
with context 4096, parallel 1 and TTL null, which is what the reported
latencies were measured on.

Then speech recognition:

    cd system/voice
    python transcribe_server.py

This serves Parakeet TDT 0.6B v3 through NeMo-Speech.cpp. The browser talks to
port 8090 and a private backend runs on 8091. The model file is not in this
repository, see the last section.

Then speech synthesis, `uvx pocket-tts serve`, on port 8000.

Then the server and renderer:

    cd system/rendering
    python serve.py

This runs on port 8080 and serves the interface along with `/api/converse`,
`/api/relate` and `/api/tts`.

Then the mapping layer:

    cd system/mapping
    python compute_scene.py

It reads the tracker's scene state, computes the spatial relations and writes
the scene description the renderer consumes. It takes an optional participant
id as its first argument, which tags its own movement log.

Last, connect the iPhone over USB with Record3D streaming, and run:

    cd system/tracking
    python track_tabletop.py

Draw the usable region on the RGB preview, keep the table empty while it
calibrates, then place props once calibration has succeeded.

Open `http://localhost:8080/`.

## Object generation

Everything above runs without object generation: tracking, mapping, the
renderer, atmosphere, voice and the conversational layer all work on their
own. Generating a mesh for an assigned meaning is the one part that needs
extra setup, and `GENERATION_BACKEND` near the top of `serve.py` selects
which way it runs.

### On a rented GPU

This is how the submitted system ran, and `GENERATION_BACKEND = "pod"` is the
shipped value. Both stages sit on one RunPod RTX 4090 as resident services, so
a warm request returns a mesh in about two seconds instead of the minutes a
local run takes.

The pod I used was `runpod/pytorch:2.1.0-py3.10-cuda11.8` with a 40 GB
container disk. Twenty was not enough, SPAR3D's install filled it. It also
needs a persistent network volume mounted at `/workspace`, which survives
stopping and starting the pod but not terminating it.

Open ports 22, 7860, 7861, 7862, 7863 and 7864 in a single edit when the pod
is created. Every pod edit triggers a full root disk wipe, so doing this once
saves rebuilding the environment. SPAR3D runs on 7860 and SDXL Turbo on 7862.
Port 7861 is skipped because RunPod's own nginx already holds it.

Keep the model weights on the volume rather than the root disk by setting
`HF_HOME=/workspace/hf-cache`. Keep the virtual environments on the root disk
instead, since the network volume is slow enough to make installs painful.

`system/generation/pod/` holds `setup.sh`, which rebuilds everything in one
command, `sdxl_wrapper.py`, which keeps SDXL Turbo resident and runs four
inference steps against five in the local script, and `spar3d-packages.txt`.
The session start is:

    bash /workspace/setup.sh

then start both wrappers, in separate terminals, and wait for each to print
that its model is resident:

    cd ~/workspace/stable-point-aware-3d && python wrapper.py
    source ~/workspace/sdxl-env/bin/activate && python /workspace/sdxl_wrapper.py

The first time only, run `huggingface-cli login` before starting them. Because
`HF_HOME` points at the volume, the token is written to `/workspace/hf-cache`
alongside the downloaded weights, and both survive stopping and starting the
pod. It only asks again if the pod is terminated rather than stopped, or if a
new pod is created without attaching the same volume.

The part that catches people out is the addresses. Under Connect and then
Direct TCP Ports, RunPod maps the internal 7860 and 7862 to external ports on
the pod's public IP. **Those external port numbers change every time the pod
stops and starts, not only when it is edited.** Check them at the start of
every session and update both URLs near the top of `serve.py`:

    SPAR3D_POD_URL = "http://<pod-ip>:<external-port-for-7860>/generate"
    SDXL_POD_URL   = "http://<pod-ip>:<external-port-for-7862>/generate"

The addresses currently in the file point at the pod I rented, which is no
longer running. Confirm a pod is reachable before assuming the pipeline is
broken:

    curl http://<pod-ip>:<external-port>/health

Each service returns `{"status": "ok"}` when its model is resident.

### On the same machine

Set `GENERATION_BACKEND = "local"`. This needs no GPU rental but is much
slower. One local SPAR3D run took 138.9 seconds of compute and 177.5 seconds
of wall time, against 35 to 85 seconds for SF3D before it.

It also needs two conda environments and the vendored SPAR3D source, neither
of which is in this repository. The four paths are absolute and
machine-specific, sitting just below the pod URLs in `serve.py`:

    PROJECT_ROOT         the repository root
    SDXL_LOCAL_SCRIPT    generate_image.py, in system/generation/
    SDXL_LOCAL_PYTHON    a conda env with torch and diffusers
    SPAR3D_LOCAL_DIR     a checkout of stable-point-aware-3d
    SPAR3D_LOCAL_PYTHON  a conda env with the SPAR3D requirements

`system/generation/pod/spar3d-packages.txt` lists what that second
environment needs.

### Without either

Set `GENERATION_BACKEND = "fake"`. Assignment waits three seconds and marks
the object ready without generating anything, so it renders as a placeholder
rather than a generated mesh. Everything else behaves normally: tracking,
assignment, caching, atmosphere and voice all run. This is how the assignment
and render-swap mechanics were first tested, and it is the easiest way to see
the interaction working without a GPU.

## Notes on the interface

The interface URL accepts `?input=text|voice` and `?participant=`. That is
instrumentation from a comparison study I designed and built but did not run,
as explained in Section 3. It stays because it is part of the submitted
artefact. No participant data exists anywhere here. Every identifier in
`logs/` is from my own development and pilot sessions.

## Reproducing two of the tables

Table 5.2, the refusal thresholds:

    cd evaluation/tracking
    python threshold_reanalysis.py features.csv

This scores the 986-row four-prop capture with the same nearest-centroid
classifier the tracker uses, and prints all four thresholds. It also prints
the shipped `CLASS_SCALE` next to the measured spread of the capture, which is
the normalisation caveat I state in Section 5.1.4.

The atmosphere repeatability check in Section 5.6.4:

    cd evaluation/atmosphere
    python atmosphere_repeatability.py 05_battery_repeatability

This compares the three runs of each of the five commands pixel by pixel.
Differences sit in a narrow band at the top of the frame where the caption is
drawn. Everywhere else the runs are identical.

## What is not here

Model weights, which are large and downloadable. Parakeet TDT 0.6B v3 is at
huggingface.co/nvidia/parakeet-tdt-0.6b-v3 and runs through
github.com/NVIDIA/NeMo-Speech.cpp. SDXL Turbo is at
huggingface.co/stabilityai/sdxl-turbo. Qwen3-8B is at
huggingface.co/Qwen/Qwen3-8B and I ran it through LM Studio. SPAR3D is
Stability AI's stable-point-aware-3d. Record3D is an iPhone app with Python
bindings. Three.js 0.170.0 and its loaders, and the `ldrs` 1.1.9 loading
animations, are all fetched from jsDelivr inside `index.html`.

Generation ran on a rented RTX 4090. `system/generation/pod/` holds the
wrapper and setup I used there. `system/generation/generate_image.py` is the
local fallback, which uses five inference steps against the pod's four, as in
Table 5.3.

Also not here: the vendored source for the reconstruction models, the runtime
mesh and screenshot caches, the full tracker debug image set, and the image
portfolio and design log, which are separate submission items. Superseded
versions the report does not cite are excluded too. The prototypes that are
here are the ones the report treats as evidence.