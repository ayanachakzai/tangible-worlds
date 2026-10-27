# Publication notes

This repository is the public copy of the Tangible Worlds MSc submission and its
interactive website. It differs from the private originals only as listed here.
The originals are kept, unchanged, outside this repository.

## Not included

| Item | Reason |
|---|---|
| `1. Tangible World Paper.pdf` (original) | Contains a student identifier. The redacted copy is at `website/public/media/doc/tangible-worlds-dissertation.pdf`. |
| `3. Video Tangible World Presentation.mov`, `4. Video Tangible World Working Prototype.mov` | Each exceeds GitHub's 100 MB file limit. Both are public on YouTube (links in `README.md`). |
| `2. Tangible World Presentation.pptx`, `6. Logs.docx`, `7. PORTFOLIO_IMAGES_1020/`, `0. Guide.pdf` | Submission deliverables outside the code package. The slides and logs document embed about 100 images and the portfolio holds 1,022 screenshots, which could not all be checked for on-screen personal or credential information before publication. |
| `evaluation/scale/codex-studies/scale_study_codex_20260827/logs/chrome-profile-shot/` (180 files) | A Chrome browser profile left by an automated screenshot run (login data, cookies, session storage, caches). Not research evidence; no script depends on its contents. |
| `__pycache__/`, `*.pyc` (8 files) and `.DS_Store` (10 files) | Regenerable bytecode and macOS folder metadata. |
| `website/node_modules/`, `website/dist/` | Regenerable with `npm ci` and `npm run build`. |
| The website's local `.claude/` tool settings and `review/` design screenshots | Local tooling and design-process material, not part of the website. |

## Changed for publication

Inside `thesis-submission/`, four kinds of string were replaced, all in recorded logs, reports and one configuration file. No other content was altered,
and every edited JSON file still parses.

- **Local home-directory paths** were replaced with `~` (2,085 full paths and 272 paths truncated by `ps` column widths). They recorded where files sat on the author's laptop.
- **The macOS account name** in recorded `ps` and `lsof` process listings was replaced with `<user>` (660 occurrences). Apple's own `/Users/USER` placeholder in `vmmap` output is unchanged.
- **`api_key=AIza…` values** (594 occurrences, two distinct values) were replaced with `api_key=<redacted: Chrome built-in Google API key>`. They appear in recorded process listings as command-line annotations of Chrome's crash handler, not as project credentials.
- **The RunPod endpoint** in `system/rendering/serve.py` (`SPAR3D_POD_URL`, `SDXL_POD_URL`) was replaced with `http://<pod-public-ip>:<external-port>/generate`. As the original README explains, these values change whenever the pod is recreated and must be set for each deployment.

In `website/`, `tools-assets.py` and `tools-encode.sh` locate the thesis repository with `~` instead of an absolute home path. The website's dissertation PDF has its student ID removed, and its `provenance.json` records sources relative to the thesis repository.

### Files edited in `thesis-submission/` (45)

**home path -> ~**

- `evaluation/scale/codex-studies/voice_scaled_alias_study_codex_20260830/production_hashes_after.txt`
- `evaluation/scale/codex-studies/voice_scaled_alias_study_codex_20260830/production_hashes_before.txt`
- `evaluation/scale/codex-studies/voice_scaled_alias_study_codex_20260830/raw/cache_regression.json`
- `logs/lmstudio_latency/codex_runs/CODEX_LATENCY_REPORT.md`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/CODEX_FINAL_MLX_LATENCY_REPORT.md`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/final_mlx_campaign_tool_20260826_v2.py`
- `logs/lmstudio_latency/codex_runs/results/audit_after_20260826_175208_+0100.json`
- `logs/lmstudio_latency/codex_runs/results/audit_before_20260826_172835_+0100.json`
- `logs/lmstudio_latency/codex_runs/results/dry_payload_check_20260826_173058_+0100.json`
- `logs/lmstudio_latency/codex_runs/results/llamacpp_auto_nocache_server_20260826_175214_+0100.log`
- `logs/lmstudio_latency/codex_runs/results/llamacpp_default_server_20260826_174249_+0100.log`
- `logs/lmstudio_latency/codex_runs/results/llamacpp_nocache_server_20260826_174820_+0100.log`
- `logs/lmstudio_latency/codex_runs/results/llamacpp_q4km_auto_no_prompt_cache_20260826_175059_+0100.json`
- `logs/lmstudio_latency/codex_runs/results/llamacpp_q4km_default_20260826_174352_+0100.json`
- `logs/lmstudio_latency/codex_runs/results/llamacpp_q4km_no_prompt_cache_20260826_174647_+0100.json`
- `logs/lmstudio_latency/codex_runs/results/llamacpp_q4km_reasoning_auto_20260826_174922_+0100.json`
- `logs/lmstudio_latency/codex_runs/results/llamacpp_reasoning_auto_server_20260826_175022_+0100.log`
- `logs/lmstudio_latency/codex_runs/results/mlx_parallel1_control_20260826_173113_+0100.json`
- `logs/lmstudio_latency/results/20260826_000546_+0100.json`
- `logs/lmstudio_latency/results/20260826_000739_+0100.json`
- `logs/lmstudio_latency/results/20260826_000922_+0100.json`
- `logs/lmstudio_latency/results/20260826_001155_+0100.json`
- `logs/lmstudio_latency/results/20260826_001213_+0100.json`
- `logs/lmstudio_latency/results/20260826_170814_+0100.json`
- `logs/lmstudio_latency/results/20260826_171454_+0100.json`
- `system/voice/transcribe_server.py`

**home path -> ~ + Chrome API key**

- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/audit_final_after_restore_20260826_182650_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/audit_observe_4096_after_5min_idle_20260826_181708_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/audit_observe_4096_after_second_5min_idle_20260826_182326_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/audit_observe_4096_post_pair1_20260826_181135_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/audit_observe_4096_post_pair2_20260826_181810_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/audit_pre_4096_runtime_change_20260826_180935_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/audit_stage0_before_20260826_180705_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/audit_stage0_before_20260826_180752_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/audit_stage2_4096_loaded_20260826_181000_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/stage1_8192_control_20260826_180809_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/stage2_4096_coldwarm_pair1_20260826_181035_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/stage2_4096_coldwarm_pair2_20260826_181722_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/stage2_4096_coldwarm_pair3_20260826_182339_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/stage2_semantic_01_stormy_20260826_182445_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/stage2_semantic_02_sunset_20260826_182457_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/stage2_semantic_03_moonlit_20260826_182508_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/stage2_semantic_04_mist_preserve_lighting_20260826_182519_+0100.json`
- `logs/lmstudio_latency/codex_runs/final_mlx_campaign/results/stage2_semantic_05_remove_rain_lightning_20260826_182530_+0100.json`

**home path -> ~ + RunPod endpoint**

- `system/rendering/serve.py`

## Known issues

- The code repository link on the dissertation cover points to a UAL-hosted repository that requires a university login.

## Resolved issues

- `website/public/media/video/working-prototype.mp4` previously had decoding errors in about 16% of its frames (an encoding fault in the web copy). It was repaired on 27 October 2026 in commit `98b7a65fdd208ccae428a0247496a8c3c2c6477e`, re-encoded from the intact original MOV recording and verified against it. The repaired video decodes all 6,967 frames with zero errors, keeps the original 232.23-second duration, and passed browser playback and seeking.
