# Codex Latency Report

Date: 2026-08-26  
Repository: `~/Documents/UAL/tangible-worlds`  
Write boundary used: `phase3-tabletop/diagnostics/lmstudio_latency/codex_runs/`

## Bottom Line

No Qwen3-8B latency fix qualified for production.

The production MLX path on LM Studio port 1234 reproduced the remaining cold/idle latency problem, but it was the only tested path that returned the exact expected storm JSON. The isolated GGUF/llama.cpp path gave excellent repeated-prompt TTFT when prompt cache was allowed, and lower memory footprint than the MLX worker, but it did not preserve production output semantics and its uncached TTFT remained too high for a live interaction.

No production change was applied.

## Safety Outcome

- I did not call `/api/converse`, `/api/reset`, `/api/mock`, `/api/assign`, or any endpoint that mutates study state.
- I did not edit, format, rename, delete, clean, reset, restore, or overwrite any existing production file, state file, study doc, cache, log, or participant data.
- New repository files were created only under `phase3-tabletop/diagnostics/lmstudio_latency/codex_runs/`.
- The isolated llama.cpp servers were run on port 1235 and were stopped before the after-audit.
- `lms ps --json` after testing showed only the production safetensors model loaded: `qwen/qwen3-8b`, 4bit, context 8192, Parallel 1, idle. The only before/after `lms ps` content difference was `lastUsedTime`, caused by the intentional production control request.
- `iogpu.wired_limit_mb` stayed `0` before and after.
- Git status text was identical before and after.
- Immutable file hash comparison found zero changes.

An official GGUF model was downloaded into LM Studio's model cache for the isolated test:

`~/.lmstudio/models/Qwen/Qwen3-8B-GGUF/Qwen3-8B-Q4_K_M.gguf`

Its SHA-256 matched the official Hugging Face file:

`d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`

It was not loaded into the production LM Studio worker at the end of the run.

## Method

All inference tests used the production request shape from `serve.py`, with only `stream: false` changed to `stream: true` for TTFT measurement. The production control payload hash matched the handoff:

`a74201574636fd0d567ed72e06e3a93c8a00d223fa253dc0cb7f35f976068438`

The test command was `make it stormy`, with the production system prompt, current scene/modifier context, temperature `0.3`, no `max_tokens`, `/no_think`, and `chat_template_kwargs: {"enable_thinking": false}`.

Expected production-equivalent output:

```json
{
  "sky_elevation": 7.0,
  "light_elevation": 15.0,
  "light_azimuth": 45.0,
  "light_level": 0.85,
  "light_warmth": 0.75,
  "sky_haze": 0.6,
  "mist_amount": 0.0,
  "mist_height": 0.35,
  "mist_motion": 0.25,
  "rain_amount": 1.0,
  "lightning_amount": 0.7,
  "mood": "stormy"
}
```

## Results

| Backend | Settings | TTFT seconds | Total seconds | Output correctness | Evidence |
|---|---|---:|---:|---|---|
| Production MLX | LM Studio port 1234, `qwen/qwen3-8b`, Parallel 1 | `19.755`, `1.045`, `0.938` | `31.607`, `12.491`, `12.438` | Exact expected JSON on all 3 requests | `results/mlx_parallel1_control_20260826_173113_+0100.json` |
| GGUF llama.cpp | Q4_K_M, reasoning off, prompt cache default | `11.773`, `0.111`, `0.105` | `24.017`, `12.025`, `11.857` | Valid contract, but `rain_amount: 0.7`, `lightning_amount: 0.5` on all 3 | `results/llamacpp_q4km_default_20260826_174352_+0100.json` |
| GGUF llama.cpp | Q4_K_M, reasoning off, prompt cache disabled | `11.162`, `11.231`, `11.427` | `23.207`, `22.825`, `23.245` | Valid contract, same lower storm values on all 3 | `results/llamacpp_q4km_no_prompt_cache_20260826_174647_+0100.json` |
| GGUF llama.cpp | Q4_K_M, reasoning auto, prompt cache default | `7.713`, `0.058`, `0.065` | `12.806`, `5.144`, `5.138` | Valid contract, values drifted: `0.7/0.3`, `0.7/0.5`, `0.8/0.5` for rain/lightning | `results/llamacpp_q4km_reasoning_auto_20260826_174922_+0100.json` |
| GGUF llama.cpp | Q4_K_M, reasoning auto, prompt cache disabled | `7.623`, `7.508`, `7.513` | `12.684`, `12.568`, `12.549` | Valid contract, but `rain_amount: 0.7`, `lightning_amount: 0.5` on all 3 | `results/llamacpp_q4km_auto_no_prompt_cache_20260826_175059_+0100.json` |

## Memory Behaviour

The production MLX worker showed the previously suspected failure mode clearly.

Before the production control request:

- `footprint --wide` for the LM Studio `llmworker.js` process showed `Footprint: 7760 MB`.
- `IOAccelerator (graphics)` was `7293 MB` dirty and `7293 MB` swapped.
- Total swapped footprint was `7749 MB`.

After the three production control requests:

- `Footprint: 7823 MB`.
- `IOAccelerator (graphics)` was `7297 MB` dirty and `0 B` swapped.
- Total swapped footprint dropped to `428 MB`.

That matches the observed latency shape: request 1 paid a large memory restoration cost before first token, then requests 2 and 3 were warm.

For GGUF/llama.cpp:

- The isolated `llama-server` processes had `Footprint` around `1239-1278 MB`.
- The GGUF file appeared mostly as clean `mapped file` memory, around `3.8-4.3 GB` in later runs.
- `IOAccelerator (graphics)` was only kilobytes to a few megabytes, not the production MLX worker's multi-gigabyte Metal footprint.
- The slow first/full-prompt TTFT was mostly compute, not memory restoration. Server logs showed full prompt evaluation times of about `7.5-11.7 s` for `1773` prompt tokens.
- The sub-100 ms llama.cpp TTFT values happened only when prompt cache reused almost the entire previous prompt and evaluated 1 token.

## Output Correctness

Production MLX returned the exact expected storm values on all 3 requests.

All GGUF variants returned syntactically valid JSON with the correct 12-key atmosphere contract, but none preserved exact production semantics. The stable GGUF result was usually:

```json
{
  "sky_elevation": 7.0,
  "light_elevation": 15.0,
  "light_azimuth": 45.0,
  "light_level": 0.85,
  "light_warmth": 0.75,
  "sky_haze": 0.6,
  "mist_amount": 0.0,
  "mist_height": 0.35,
  "mist_motion": 0.25,
  "rain_amount": 0.7,
  "lightning_amount": 0.5,
  "mood": "stormy"
}
```

The `reasoning auto` variant varied between requests and still did not match the production target exactly.

## Rejected Candidates

- GGUF/llama.cpp Q4_K_M, reasoning off: rejected because exact output semantics failed, and without prompt cache it paid about 11 s TTFT every request.
- GGUF/llama.cpp Q4_K_M, reasoning auto: rejected because exact output semantics failed; uncached TTFT was about 7.5 s every request.
- llama.cpp prompt cache as a "fix": rejected as a production qualification by itself. It can make repeated identical or near-identical prompts look extremely fast, but it is not the same as solving cold/live first-utterance latency and it did not fix output equivalence.
- llama.cpp `mlock` / `mmap+mlock`: not run. The measured GGUF bottleneck was prompt evaluation compute and output mismatch, not swapped GGUF residency. Pinning memory would not correct semantics and would add avoidable memory pressure while the production MLX model remained loaded.
- Parallel changes, production model replacement, warm-up, keep-alive, prompt/schema changes, `max_tokens` changes, and temperature changes: rejected because the handoff explicitly prohibited production changes or semantic drift.

## Recommendation

Do not switch production to the tested GGUF/llama.cpp Qwen3-8B path.

For the study runtime, the safest recommendation is: keep the current production MLX Qwen3-8B path unchanged, document that the cold/idle TTFT issue remains unresolved, and do not apply a backend change until a candidate preserves exact atmosphere output and improves full-prompt latency without relying on prompt-cache or warm-up behaviour.

There is no winning fix qualified by this run.

## Preservation Hashes

Before audit: `results/audit_before_20260826_172835_+0100.json`  
After audit: `results/audit_after_20260826_175208_+0100.json`

| Path | Before SHA-256 | After SHA-256 |
|---|---|---|
| `phase3-tabletop/rendering/serve.py` | `5c00e629ff7723456ee9b946b78de6ba4f83ddfd15eb7e6eecf8e06db4bbbc55` | `5c00e629ff7723456ee9b946b78de6ba4f83ddfd15eb7e6eecf8e06db4bbbc55` |
| `phase3-tabletop/rendering/index.html` | `e399e61904fe0c1c48cf82428eea065a37c153af16ebaf6b8a1fb8f1ca0de843` | `e399e61904fe0c1c48cf82428eea065a37c153af16ebaf6b8a1fb8f1ca0de843` |
| `phase3-tabletop/rendering/voice_capture_worklet.js` | `b334ecd24db7fc4a046a8e35a0bc87dcefb3c2be65945542768f4db967945fbb` | `b334ecd24db7fc4a046a8e35a0bc87dcefb3c2be65945542768f4db967945fbb` |
| `phase3-tabletop/mapping/compute_scene.py` | `a260c346e7dd66e0b98c201d7ba09f4494c2af073e05c8ccfbc0475ace12a695` | `a260c346e7dd66e0b98c201d7ba09f4494c2af073e05c8ccfbc0475ace12a695` |
| `phase3-tabletop/mapping/scene_description.json` | `c8b6287b9ac307c4cb8f397d81d6d9cd10e3b699e9eebdc77cdfb3a5aad3f26c` | `c8b6287b9ac307c4cb8f397d81d6d9cd10e3b699e9eebdc77cdfb3a5aad3f26c` |
| `phase3-tabletop/tracking/track_tabletop.py` | `9dd353ea83ca51c1e392676530294ad0d967953305e189269bd18f49babda05b` | `9dd353ea83ca51c1e392676530294ad0d967953305e189269bd18f49babda05b` |
| `phase3-tabletop/tracking/scene_state.json` | `67195eb8a79b3c4020f5d4d143105bb6800b38125428967e2f0ab05078bfeff9` | `67195eb8a79b3c4020f5d4d143105bb6800b38125428967e2f0ab05078bfeff9` |
| `phase3-tabletop/conversation/converse.py` | `d5746bb21fd121142bfb97bd0eb7b7ac7445c70ebe278ad585edcd148ad4c334` | `d5746bb21fd121142bfb97bd0eb7b7ac7445c70ebe278ad585edcd148ad4c334` |
| `phase3-tabletop/conversation/scene_modifiers.json` | `7208e6516cb5aa6c30108d3a3942d4a98479e50deb3140caf3160a8f6fe18bff` | `7208e6516cb5aa6c30108d3a3942d4a98479e50deb3140caf3160a8f6fe18bff` |
| `phase3-tabletop/conversation/conversation_log.json` | `d12bd5f4dee3f68b29601f4c808fd8b78b5410b25106dd573441eff1caca3bba` | `d12bd5f4dee3f68b29601f4c808fd8b78b5410b25106dd573441eff1caca3bba` |
| `phase3-tabletop/rendering/assignments.json` | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` |
| `phase3-tabletop/rendering/relations.json` | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` |
| `phase3-tabletop/rendering/mesh_rotations.json` | `28ddb3f25d1a491e2413910cbf6fbe3f1ffa8508a82be14260ed33e7aebd0307` | `28ddb3f25d1a491e2413910cbf6fbe3f1ffa8508a82be14260ed33e7aebd0307` |
| `phase3-tabletop/tracking/calibration_trigger.json` | `62546446893683075cb3a3486163606a8162286ba9385c93f752b1b5b07f3e18` | `62546446893683075cb3a3486163606a8162286ba9385c93f752b1b5b07f3e18` |
| `phase3-tabletop/tracking/calibration_state.json` | `94b59479fd7fe7edcf61b8cdbc12e8224a010ec85cda17cabc7e5daf800b5eda` | `94b59479fd7fe7edcf61b8cdbc12e8224a010ec85cda17cabc7e5daf800b5eda` |
| `phase6-voice/transcribe_server.py` | `464e2dcc35b46942d366a9c71391d17c16bee82e451e0722564f44b5a8f1a4a1` | `464e2dcc35b46942d366a9c71391d17c16bee82e451e0722564f44b5a8f1a4a1` |
| `phase2-generation-sdxlturbo/generate_image.py` | `f2a3ab3b18918bd27e4e15d90887d002191907d5d2cdbfe571b0621801b3869e` | `f2a3ab3b18918bd27e4e15d90887d002191907d5d2cdbfe571b0621801b3869e` |
| `phase3-tabletop/PROJECT_AUDIT.md` | `1c722b78f8835c1728b8e65fa52b5ca04d6d87fa7671990ecf05f3550a2e4adf` | `1c722b78f8835c1728b8e65fa52b5ca04d6d87fa7671990ecf05f3550a2e4adf` |
| `phase3-tabletop/RUNBOOK.md` | `87e4d7d6ecfac545d8d33d3f4039bf391626debaf811d987651601faabc534b4` | `87e4d7d6ecfac545d8d33d3f4039bf391626debaf811d987651601faabc534b4` |
| `design-diary/DESIGN_DIARY.md` | `27d8f924de8f714b1057a4917e1189000d9bc1927023ad992d2b5d81ba8a4f07` | `27d8f924de8f714b1057a4917e1189000d9bc1927023ad992d2b5d81ba8a4f07` |

## References

- Official Qwen GGUF repository: [Qwen/Qwen3-8B-GGUF](https://huggingface.co/Qwen/Qwen3-8B-GGUF)
- Official Qwen llama.cpp local-run documentation: [Qwen docs - llama.cpp](https://qwen.readthedocs.io/en/latest/run_locally/llama.cpp.html)
- llama.cpp project: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)
- LM Studio OpenAI-compatible chat completions documentation: [LM Studio chat completions](https://lmstudio.ai/docs/developer/openai-compat/chat-completions)
