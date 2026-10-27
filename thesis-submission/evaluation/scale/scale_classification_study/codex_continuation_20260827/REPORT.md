# Tangible Worlds Qwen semantic-scale classification continuation

Study date: 27 August 2026.

## Final decision

**Qwen semantic-scale classification does not qualify for production yet.** [READ][RAN]

The best frozen candidate achieved 50/72 preregistered acceptable results (69.4%) on a fresh holdout. It was perfectly valid and exactly repeatable on the selected subset, but modifier and ordinary-bin failures were systematic. The simplest defensible alternative is a cached participant-selected scale band at assignment time, with no Qwen scale call. [RAN]

## What was read and what was run

[READ] Reviewed the authoritative project docs, current production assignment/renderer boundary, isolated scale page, all existing classifier evidence, and the previous autonomous visual-scale study. The current production flow already separates semantic assignment from physical movement, and the renderer owns mesh normalisation.

[RAN] Saved protected production hashes and Git status before study writes. Reproduced the seven current anchor classifications at 7/7 valid and acceptable. Froze three candidates and a fresh 72-case holdout. Ran 288 candidate calls, retained raw outputs, audited all failures, and repeated 12 preregistered meanings three times per candidate.

## Exact candidates and contracts

All calls used local `qwen/qwen3-8b`, LM Studio port 1234, temperature 0, thinking disabled, and `/no_think`. The complete exact shared system prompt, suffixes, request contracts, and Candidate C regular expressions were frozen in `candidate_contracts.md` and executed from `evaluate_candidates.py`. [RAN]

Candidate A user turn and output contract:

```text
Assigned semantic meaning: "<meaning>"
Classify the intended represented real-world scale. /no_think
```

Output: one exact approved enum, no other text.

Candidate B user turn and strict output contract:

```text
Assigned semantic meaning: "<meaning>"
Identify the observable scale basis and classify the intended represented real-world scale. /no_think
```

```json
{"scale_basis":"<short observable physical size reference>","semantic_scale_class":"<approved enum>"}
```

Candidate C user turn and output contract:

```text
Assigned semantic meaning: "<meaning>"
Deterministically extracted intended scale basis: "<basis>"
Classify the physical extent expressed by the scale basis. /no_think
```

Output: one exact approved enum. The deterministic pass recognises five general relationships: comparison with `as`, `the size of`, `X-sized Y`, full/life-size model/replica, and miniature/toy representation. It has no noun-specific class mapping.

## Fresh holdout

[RAN] `holdout_cases.json` was frozen before inference and has no exact phrase reused from the 98-case development battery. Its 72 cases comprise 36 ordinary concrete meanings across nine physical bins, four abstractions/events, six adjacent-bin boundaries, six creative/VFX-like meanings, and 20 fresh explicit modifiers/comparisons. Up to two acceptable adjacent classes were recorded before calls only where genuinely defensible.

## Quantitative results

First-run holdout results:

| candidate | valid contract | acceptable overall | ordinary concrete | modifiers | ambiguous/events | boundaries | creative |
|---|---:|---:|---:|---:|---:|---:|---:|
| A direct enum | 72/72 (100%) | 43/72 (59.7%) | 21/36 (58.3%) | 12/20 (60.0%) | 3/4 | 3/6 | 4/6 |
| B structured basis | 72/72 (100%) | 50/72 (69.4%) | 28/36 (77.8%) | 13/20 (65.0%) | 2/4 | 3/6 | 4/6 |
| C modifier pre-parser | 72/72 (100%) | 48/72 (66.7%) | 24/36 (66.7%) | 13/20 (65.0%) | 4/4 | 3/6 | 4/6 |

Ordinary concrete results by bin:

| group (4 each) | A | B | C |
|---|---:|---:|---:|
| micro | 3 | 4 | 3 |
| handheld | 4 | 4 | 4 |
| body | 2 | 2 | 2 |
| room | 0 | 2 | 1 |
| vehicle | 4 | 4 | 4 |
| building | 2 | 4 | 3 |
| infrastructure | 0 | 1 | 0 |
| landform | 4 | 4 | 4 |
| colossal | 2 | 3 | 3 |

Candidate B improved development-set-looking headline accuracy but still failed the engineering requirement: ordinary room and infrastructure meanings were not robust, modifiers missed 7/20, and ambiguity was not conservative.

## Modifier-specific findings

[RAN] Decomposition was not enough. Candidate B returned reasonable bases such as `suspension bridge`, `mountain`, `office tower height`, `passenger train length`, and `garden shed`, yet mapped them respectively to `building_scale`, `colossal_scale`, `colossal_scale`, `room_scale`, and `building_scale`.

[RAN] Candidate C fixed `mountain-sized robot` and the miniature space-station model, but lost other cases and finished at the same 13/20 modifier score as B. Passing extracted bases such as `an airport terminal` and `a passenger train` still produced `room_scale`. A larger rule set would become the brittle noun-specific parser the study prohibited.

## Repeatability

[RAN] All three candidates achieved exact agreement on all 12 preregistered repeat cases (36 calls each). A had 9/12 acceptable repeated meanings; B and C had 10/12. Candidate A returned the same wrong `colossal_scale` output three times for both `mountain-sized robot` and `tree as tall as an office tower`; B did the same. Repeatability is therefore strong, but it exposes deterministic semantic errors rather than resolving them.

## Failure review

[READ] Clear failures include `portable toilet cubicle -> handheld`, `motorway interchange -> room_scale`, `Buddhist temple -> body_scale`, `miniature model of a space station -> building_scale`, and passenger-train comparison -> `room_scale`. [RAN]

[READ] A few outputs have defensible post-hoc readings—especially a supernatural doorway as `ambiguous`, a settled mobile home as `building_scale`, or a country as `landform_scale`. They remain mismatches because those labels were not preregistered. They do not account for the systematic room, infrastructure, and modifier failures. Full detail is in `failure_analysis.md`.

## Open vocabulary and model adequacy

[READ][RAN] Open vocabulary is not credible for this exact role. The anchor reproduction and development battery overstate robustness because the fresh nouns changed the failure distribution sharply. Qwen3-8B is adequate at output-contract following and deterministic local inference, but not at this project-specific compressed semantic mapping. The model's ordinary physical knowledge does not align reliably with the custom bins, even when it identifies the controlling comparison noun.

[READ][RAN] None of the tested automatic mechanisms is simple enough and accurate enough to defend as a production classifier in the dissertation. Candidate B is simple, but wrong too often. Candidate C adds mechanism without material gain. Further tuning would invite observed-case patches.

## Micro and colossal separation

[RAN] Semantic results show that Candidate B identified 4/4 fresh micro cases and 3/4 fresh colossal cases; this is not enough to qualify the full classifier. Separately, the renderer still has no visually calibrated values for either `micro` or `colossal_scale`. No numeric values were invented in this study.

Any future semantic record may retain those enums, but production rendering must use an explicit neutral fallback or wait for a later isolated visual calibration. This semantic limitation and renderer-calibration limitation are independent.

## Limitations

- This is a project-specific technical evaluation, not human-subject validation.
- The 72-case holdout is fresh relative to saved development phrases, but it cannot establish universal semantic scale.
- Acceptable labels encode design judgments for compressed visual bins, not metric truth.
- Exact repeatability was tested on 12 preregistered cases, not all 72.
- The model/runtime was intentionally fixed; no claim is made about other models.
- The visual ladder remains supported only for the seven previously tested renderer classes.

## Selected architecture and next action

No automatic candidate is selected. The negative-result architecture is: assigned meaning -> participant selects one human-readable calibrated scale band -> cache `semantic_scale_class` with `semantic_scale_source: "participant_selected"` -> renderer owns the numeric mapping -> movement changes position only. “Not sure” stores `ambiguous` and renders at neutral 1.00. [READ]

**Exactly one recommended next production action:** add that assignment-time scale-band selector and cached fields; do not add a Qwen scale-classification call. No production change was applied in this run.
