# Method

Study date: 27 August 2026.

## Boundary

[READ] This continuation concerns semantic classification only. The renderer ladder was not reopened: `handheld=0.35`, `body_scale=0.65`, `room_scale=1.00`, `vehicle_scale=1.35`, `building_scale=1.80`, `infrastructure_scale=2.35`, and `landform_scale=3.00` remain the locked visual result. `micro` and `colossal_scale` remain semantically defined but visually uncalibrated.

[READ] Production files and runtime state were read only. New files were confined to `phase3-tabletop/rendering/scale_classification_study/codex_continuation_20260827/`.

## Pass 1 — audit

[READ] Reviewed the current-state portions of `PROJECT_AUDIT.md`, `RUNBOOK.md`, and `DESIGN_DIARY.md`; the assignment, mesh normalisation, movement, and model-call boundaries in `index.html` and `serve.py`; `scale_test.html`; all saved classifier study artifacts; and the previous Codex renderer-scale report.

[READ] The production boundary is suitable for a future cached field: `/api/assign` creates or replaces an assignment record, while later scene polling moves an existing render group without regenerating its meaning. The renderer currently normalises generated meshes to a common target size and owns that numeric operation.

[READ] The saved 98-case development battery had 98/98 valid enum outputs and 85/98 preregistered acceptable outputs, but only one call per meaning. Its main systematic weakness was modifier handling; its reported case consistency was therefore not repeatability evidence.

## Pass 2 — reproduction

[RAN] Re-ran the seven current anchors once with the existing isolated script and current local runtime. Result: 7/7 valid and 7/7 acceptable. Raw reproduction files are under `reproduction_current/`.

## Pass 3 — frozen candidates

[RAN] Froze three candidates before fresh holdout inference. Their complete prompts, request settings, contracts, and Candidate C grammar are in `candidate_contracts.md`; the executable copies are constants in `evaluate_candidates.py`.

1. A: direct one-call enum classifier.
2. B: one-call strict JSON result containing an observable `scale_basis` and `semantic_scale_class`.
3. C: five general regular-expression relationships producing a scale basis, followed by one enum call.

Candidate C contains no noun-to-class dictionary and no holdout-specific rule. It recognises comparison syntax, `X-sized Y`, full/life-size representations, and small toy/miniature representations. Unmatched meanings pass through unchanged.

## Pass 4 — fresh holdout preregistration

[RAN] Created and froze `holdout_cases.json` before inference. It has 72 meanings, including 36 ordinary concrete nouns across nine physical classes, four abstractions/events, six boundary cases, six creative film/VFX-like meanings, and 20 explicit modifiers/comparisons.

[RAN] Exact string comparison found zero holdout meanings duplicated in the 98-case development battery. Acceptable labels were not widened after inference. Six boundary cases, three modifier cases, and one creative case have two preregistered adjacent acceptable bins where both were judged defensible before calls.

## Pass 5 — inference

[RAN] Used only `qwen/qwen3-8b` through LM Studio at port 1234, temperature 0, thinking disabled, `/no_think`, context-compatible prompts, and serial calls. Candidate B used LM Studio's OpenAI-compatible JSON-schema response format and a local strict parser.

[RAN] Each candidate ran once across all 72 cases. Twelve preregistered cases ran twice more, for 96 calls per candidate and 288 candidate calls total. The subset included eight modifiers and four controls. Every per-call record, raw output, parsed result, scale basis, parser rule, latency, and error is preserved under `raw/` and in `results.json`/`results.csv`.

## Pass 6 — adversarial review

[READ] Reviewed every first-run mismatch without changing the frozen score. Failures were separated into ordinary-bin miscalibration, modifier/comparison failures, ambiguity failures, and post-hoc defensible boundary readings. See `failure_analysis.md`.

## Pass 7 — repeatability

[RAN] Exact three-run agreement was measured only for the preregistered subset. All candidates agreed on all 12 repeated meanings. This does not rescue semantic performance: A repeated three wrong cases consistently, while B and C each repeated two wrong cases consistently.

## Pass 8 — engineering decision

[READ][RAN] The decision uses output validity, ordinary-noun coverage, modifier handling, conservative ambiguity, repeatability, and mechanism simplicity together. No universal threshold was created after results. Because the best candidate failed 22/72 cases, including 7/20 modifiers and severe ordinary room/infrastructure weaknesses, no candidate qualifies.
