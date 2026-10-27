# Codex Final MLX Latency Report

Date: 2026-08-26  
Repository: `~/Documents/UAL/tangible-worlds`  
Allowed write boundary: `phase3-tabletop/diagnostics/lmstudio_latency/codex_runs/final_mlx_campaign/`

## Final Conclusion

**A. QUALIFIED MLX MITIGATION FOUND**

The supported LM Studio configuration that qualified diagnostically is:

```text
model: qwen/qwen3-8b
runtime family: LM Studio MLX, safetensors, 4bit
context length: 4096
Parallel / Max Concurrent Predictions: 1
port: 1234
TTL: null / no --ttl flag
prompt/schema/code: unchanged
```

Exact supported load method used:

```bash
lms unload qwen/qwen3-8b
lms load qwen/qwen3-8b --context-length 4096 --parallel 1 -y
```

This configuration was **not applied to production**. At campaign end I restored the required production runtime to `qwen/qwen3-8b`, context `8192`, Parallel `1`, port `1234`, TTL `null`.

## Safety Outcome

- No existing Tangible Worlds repository file was edited, formatted, renamed, deleted, restored, reset, cleaned, or overwritten.
- New files were created only under `phase3-tabletop/diagnostics/lmstudio_latency/codex_runs/final_mlx_campaign/`.
- No Tangible Worlds state-mutating endpoint was invoked. I did not call `/api/converse`, `/api/reset`, `/api/mock`, `/api/assign`, or other production app mutation routes.
- All inference went directly to LM Studio `/v1/chat/completions`.
- No dependencies, runtimes, packages, or models were installed or downloaded.
- No LM Studio internal files, app files, runtime source, metadata, or cache/config JSON were edited.
- `iogpu.wired_limit_mb` remained `0`.
- No test server remained on port `1235`.

Corrected Stage 0 audit:

`results/audit_stage0_before_20260826_180752_+0100.json`

Final after-restore audit:

`results/audit_final_after_restore_20260826_182650_+0100.json`

Audit comparison:

`results/audit_compare_20260826_182702_+0100.json`

Result:

- immutable hash changes: `[]`
- git porcelain before/after: identical
- final `lms ps --json`: `qwen/qwen3-8b`, `contextLength: 8192`, `parallel: 1`, `ttlMs: null`, `status: idle`
- final `sysctl iogpu.wired_limit_mb`: `0`

An earlier helper/audit attempt had a repository-root bug and was disregarded before any runtime request or load/unload action. The corrected v2 helper and corrected Stage 0 audit are the preservation baseline used here.

## Baseline: Actual 8192

The Stage 0 audit found the production 8192 worker already cold/non-resident:

```text
worker PID: 24252
Footprint: 7760 MB
IOAccelerator (graphics): 7293 MB dirty, 7293 MB swapped
TOTAL swapped: 7749 MB
```

I then ran exactly one production-equivalent streamed diagnostic request, changing only `stream: false -> true`.

Evidence:

`results/stage1_8192_control_20260826_180809_+0100.json`

```text
payload sha256: a74201574636fd0d567ed72e06e3a93c8a00d223fa253dc0cb7f35f976068438
response headers: 0.026 s
first SSE data: 22.352 s
TTFT: 22.874 s
post-first generation: 12.696 s
total: 35.570 s
```

Output correctness passed: valid JSON, exact 12 keys, values in production ranges, and correct storm direction.

After the request:

```text
Footprint: 7767 MB
IOAccelerator (graphics): 7294 MB dirty, 0 B swapped
TOTAL swapped: 420 MB
```

This reproduced the pathological idle-to-request restoration stall. I did not run additional 8192 controls because the handoff permitted exactly one 8192 production-equivalent control when the worker was clearly cold/non-resident. The already established immediate-warm 8192 reference from the preceding evidence remains approximately `1.045 s` and `0.938 s` TTFT.

## Actual 4096 Result

Load method:

`results/runtime_load_4096_20260826_181000_+0100.log`

```bash
lms unload qwen/qwen3-8b
lms load qwen/qwen3-8b --context-length 4096 --parallel 1 -y
```

Final 4096 load state:

```json
{
  "identifier": "qwen/qwen3-8b",
  "contextLength": 4096,
  "parallel": 1,
  "ttlMs": null,
  "status": "idle"
}
```

4096 idle footprint immediately after load:

`results/audit_stage2_4096_loaded_20260826_181000_+0100.json`

```text
Footprint: 4967 MB
IOAccelerator (graphics): 4395 MB dirty, 2084 MB swapped
TOTAL swapped: 2132 MB
```

Gate A comparison:

```text
8192 footprint: 7760 MB
4096 loaded footprint: 4967 MB
delta: -2793 MB
delta percent: -36.0%
```

Gate A passed. The reduction exceeded both `512 MB` and `10%`, and also exceeded the stronger `1 GB` / `15%` materiality band.

The full production payload fit inside context 4096: every exact-payload direct request returned HTTP 200, with the production payload hash unchanged for `make it stormy`.

## 4096 Latency Qualification

All 4096 latency requests used:

```text
model: qwen/qwen3-8b
endpoint: http://127.0.0.1:1234/v1/chat/completions
payload hash for make it stormy: a74201574636fd0d567ed72e06e3a93c8a00d223fa253dc0cb7f35f976068438
stream: true for timing only
```

Cold/non-resident cases were based on measured worker residency, not arbitrary time alone and not artificial memory pressure.

| Case | Pre-request residency | Cold TTFT | Cold total | Warm TTFT | Warm total | Evidence |
|---|---:|---:|---:|---:|---:|---|
| Pair 1 | `2131 MB` swapped | `5.024 s` | `17.099 s` | `1.047 s` | `13.138 s` | `results/stage2_4096_coldwarm_pair1_20260826_181035_+0100.json` |
| Pair 2 | `5282 MB` swapped | `1.612 s` | `13.537 s` | `1.032 s` | `12.884 s` | `results/stage2_4096_coldwarm_pair2_20260826_181722_+0100.json` |
| Pair 3 | `5540 MB` swapped | `1.247 s` | `8.408 s` | `0.715 s` | `7.888 s` | `results/stage2_4096_coldwarm_pair3_20260826_182339_+0100.json` |

4096 cold TTFT range:

```text
1.247 s to 5.024 s
```

4096 warm TTFT range:

```text
0.715 s to 1.047 s
```

No observed 4096 cold case produced a `10-30 s` pathological TTFT. The first cold case was just above the preferred `<5 s` band, but the two fully swapped later cases were under `2 s`. This qualifies as reliable participant-responsive behaviour in this bounded campaign.

## KV-Cache Exposure Result

**MLX KV CACHE QUANTISATION: IMPLEMENTED UPSTREAM, NOT SAFELY EXPOSED IN CURRENT LM STUDIO SURFACE**

Local evidence:

`results/stage3_kv_exposure_discovery_20260826_182700_+0100.log`

- `lms load --help` exposes `--gpu`, `--context-length`, `--parallel`, `--ttl`, speculative decoding flags, `--identifier`, and `--estimate-only`.
- It does not expose `kv_bits`, `kv_group_size`, `quantized_kv_start`, or equivalent MLX KV-cache quantisation flags.
- `/api/v1/models` reported only `context_length`, `parallel`, and `reasoning_budget_message` for the loaded MLX instance.
- LM Studio REST load docs list `context_length`; the cache/offload parameters shown there are documented as llama.cpp-only.

Official upstream `mlx-engine` source does implement KV-cache quantisation parameters in `ModelKit` (`kv_bits`, `kv_group_size`, `quantized_kv_start`), and the standalone demo exposes `--kv-bits`, `--kv-group-size`, and `--quantized-kv-start`. The handoff forbids using those internals as a replacement runtime or hacking hidden parameters into LM Studio.

No KV-cache quantisation footprint or latency test was run.

## Combination Result

No combination test was run.

Reason: the only independent supported mitigation found was context `4096`. KV-cache quantisation was not safely exposed through the installed LM Studio CLI/API surface, so there was no supported second mitigation to combine.

## Semantic Sanity Result

Because the 4096 latency candidate reached qualification, I ran the five-command semantic sanity suite through direct LM Studio requests only.

| Command | TTFT | Contract | Range | Semantic Direction | Parsed summary | Evidence |
|---|---:|---|---|---|---|---|
| `make it stormy` | `1.276 s` | pass | pass | pass | rain `1.0`, lightning `0.6`, mood `stormy` | `results/stage2_semantic_01_stormy_20260826_182445_+0100.json` |
| `make it a warm hazy sunset` | `1.054 s` | pass | pass | pass | warmth `0.75`, haze `0.6`, low light elevation `15.0` | `results/stage2_semantic_02_sunset_20260826_182457_+0100.json` |
| `make it a clear dry moonlit night, no mist, no rain and no lightning` | `1.649 s` | pass | pass | pass | sky `-6.0`, cool warmth `-0.35`, no mist/rain/lightning | `results/stage2_semantic_03_moonlit_20260826_182508_+0100.json` |
| `make the mist much thicker and more active, but keep the lighting exactly as it is` | `1.035 s` | pass | pass | pass | mist `0.82`, motion `0.72`, lighting preserved | `results/stage2_semantic_04_mist_preserve_lighting_20260826_182519_+0100.json` |
| `remove the rain and lightning` | `0.986 s` | pass | pass | pass | rain `0.0`, lightning `0.0`, unrelated fields preserved | `results/stage2_semantic_05_remove_rain_lightning_20260826_182530_+0100.json` |

Note: the helper's generic range table incorrectly flagged the moonlit command because it assumed `light_warmth` was `0..1`. The production schema in `serve.py` states `light_warmth: -1..1`, and the production prompt includes the exact moonlit example with `light_warmth: -0.35`. Manual review therefore marks this semantic check as pass.

## Decision Table

| Candidate | Footprint | Delta vs 8192 | Cold TTFT Range | Warm TTFT Range | Swap Restoration Observed | Semantic Pass | Status |
|---|---:|---:|---:|---:|---|---|---|
| 8192 baseline | `7760 MB` | baseline | `22.874 s` | established prior: about `0.94-1.05 s` | yes, `7749 MB -> 420 MB` swapped | yes | REJECTED as latency baseline |
| 4096 context, Parallel 1 | `4967 MB` loaded idle; `~5552-5587 MB` active | `-2793 MB` loaded idle; about `-2173 MB` active | `1.247-5.024 s` | `0.715-1.047 s` | yes, but no pathological TTFT | yes | QUALIFIED |
| MLX KV-cache quantisation | not tested | not tested | not tested | not tested | not tested | not tested | NOT SAFELY TESTABLE |
| 4096 + KV-cache quantisation | not tested | not tested | not tested | not tested | not tested | not tested | NOT SAFELY TESTABLE |

## Preservation Hashes

All audited immutable files had identical before/after SHA-256 hashes.

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

## Sources

- LM Studio CLI `lms load` docs: [https://lmstudio.ai/docs/cli/local-models/load](https://lmstudio.ai/docs/cli/local-models/load)
- LM Studio REST model load docs: [https://lmstudio.ai/docs/developer/rest/load](https://lmstudio.ai/docs/developer/rest/load)
- LM Studio MLX engine `ModelKit`: [https://raw.githubusercontent.com/lmstudio-ai/mlx-engine/main/mlx_engine/model_kit/model_kit.py](https://raw.githubusercontent.com/lmstudio-ai/mlx-engine/main/mlx_engine/model_kit/model_kit.py)
- LM Studio MLX engine standalone demo: [https://raw.githubusercontent.com/lmstudio-ai/mlx-engine/main/demo.py](https://raw.githubusercontent.com/lmstudio-ai/mlx-engine/main/demo.py)
- LM Studio MLX context-fit issue #366: [https://github.com/lmstudio-ai/mlx-engine/issues/366](https://github.com/lmstudio-ai/mlx-engine/issues/366)
